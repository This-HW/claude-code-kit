#!/usr/bin/env python3
"""
PreToolUse Hook: 민감한 파일 보호 + 메시지 콘텐츠 스캔

Edit/Write/Read 도구가 민감한 파일에 접근하려 할 때 차단합니다.
Agent Teams 모드에서 message/broadcast 콘텐츠에 민감 정보가 포함되면 차단합니다.

차단되는 파일:
- .env* (환경 변수)
- **/secrets/** (시크릿 디렉토리)
- **/*credential* (인증 정보)
- **/*secret* (시크릿)
- ~/.ssh/** (SSH 키)
- ~/.aws/** (AWS 인증)

메시지 콘텐츠 스캔 (Agent Teams, S-C-08):
- API 키 패턴 (sk-, pk_, AKIA 등)
- 비밀번호/토큰 리터럴
- SSH 개인키 블록
- 데이터베이스 연결 문자열

사용법:
  settings.json에서 PreToolUse hook으로 등록

종료 코드:
  0: 허용
  2: 차단 (Claude에게 피드백)
"""

import json
import os
import re
import sys

# 공통 유틸리티 import (스크립트 위치 기반 동적 경로)
hook_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, hook_dir)
try:
    from utils import debug_log, is_debug_mode
except ImportError:

    def debug_log(msg, error=None):
        pass

    def is_debug_mode():
        return False


# 보호할 패턴 (정규식)
PROTECTED_PATTERNS = [
    # 환경 변수
    r"\.env($|\.)",  # .env, .env.local, .env.production 등
    # 시크릿/인증 디렉토리
    r"/secrets/",  # secrets 디렉토리
    r"credential",  # credential 포함 파일
    r"secrets?(?=[._/\d-]|$)",  # 'secret(s)' 토큰: mysecret.txt·secrets_manager·api_secret 포함, 'secretary' 제외
    # SSH
    r"\.ssh/",  # SSH 키 디렉토리
    r"id_rsa",  # SSH 개인키
    r"id_ed25519",  # SSH 개인키
    r"id_ecdsa",  # SSH 개인키
    r"known_hosts",  # SSH known hosts
    # 클라우드 설정
    r"\.aws/",  # AWS 설정
    r"\.gcp/",  # GCP 설정
    r"\.azure/",  # Azure 설정
    r"\.kube/config",  # Kubernetes config
    r"\.docker/config\.json",  # Docker credentials
    # 패키지 관리자 토큰
    r"\.npmrc$",  # npm 토큰
    r"\.yarnrc$",  # yarn 설정
    r"\.pypirc$",  # PyPI 토큰
    r"\.netrc$",  # netrc 파일
    # 키 파일
    r"\.pem$",  # 인증서/키 파일
    r"\.key$",  # 키 파일
    r"\.p12$",  # PKCS#12 파일
    r"\.pfx$",  # PFX 파일
    r"private.*key",  # 개인 키
    r".*_rsa$",  # RSA 키
    r".*_ecdsa$",  # ECDSA 키
    # 기타 민감 파일
    r"(^|/|_|-)token($|\.|_|-)",  # api_token, my-token, token.json
    r"(^|/|_|-)tokens($|\.|_|-)",  # api_tokens, my-tokens
    r"(^|/|_|-)password($|\.|_|-)",  # my_password, user-password
    r"(^|/|_|-)passwords($|\.|_|-)",  # my_passwords
    r"\.htpasswd$",  # Apache htpasswd
]

# 메시지 콘텐츠 내 민감 정보 패턴 (Agent Teams S-C-08)
SENSITIVE_CONTENT_PATTERNS = [
    # API 키 패턴
    (r"sk-[a-zA-Z0-9]{20,}", "API 키 (sk-...)"),
    (r"pk_[a-zA-Z0-9]{20,}", "API 키 (pk_...)"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"xoxb-[0-9]{10,13}-[a-zA-Z0-9-]+", "Slack Bot Token"),
    (r"xoxp-[0-9]{10,13}-[a-zA-Z0-9-]+", "Slack User Token"),
    # 비밀번호/토큰 할당 패턴
    (r'(?:password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\']{8,}', "비밀번호 리터럴"),
    (r'(?:api_key|apikey|api-key)\s*[=:]\s*["\']?[^\s"\']{8,}', "API 키 리터럴"),
    (r'(?:secret|token)\s*[=:]\s*["\']?[^\s"\']{16,}', "시크릿/토큰 리터럴"),
    # SSH 개인키 블록
    (r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", "SSH 개인키"),
    (r"-----BEGIN CERTIFICATE-----", "인증서"),
    # 데이터베이스 연결 문자열
    (r"(?:postgres|mysql|mongodb)://\S+:\S+@", "DB 연결 문자열 (인증 정보 포함)"),
    (r"(?:redis|amqp)://:\S+@", "Redis/AMQP 연결 문자열"),
    # JWT 토큰
    (r"eyJ[a-zA-Z0-9_-]{20,}\.eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}", "JWT 토큰"),
]

# 차단 메시지
BLOCK_MESSAGES = {
    "env": "환경 변수 파일은 직접 수정할 수 없습니다. 수동으로 설정하세요.",
    "secrets": "시크릿 파일/디렉토리는 보호됩니다.",
    "credential": "인증 정보 파일은 보호됩니다.",
    "ssh": "SSH 키는 보호됩니다.",
    "key": "개인 키 파일은 보호됩니다.",
    "cloud": "클라우드 설정 파일은 보호됩니다.",
    "token": "토큰/패스워드 파일은 보호됩니다.",
    "package": "패키지 관리자 인증 파일은 보호됩니다.",
}


def check_content_sensitive(content) -> tuple[bool, str]:
    """메시지/broadcast 콘텐츠에 민감 정보가 포함되어 있는지 확인 (S-C-08).

    content가 str이 아니어도(list/dict payload) str()로 강제 직렬화해 스캔한다 —
    구조화 payload에 re.search가 TypeError를 던져 blanket except로 fail-open(스캔 우회)
    되던 문제(적대적 리뷰 P1)를 막는다.
    """
    if not content:
        return False, ""
    if not isinstance(content, str):
        content = str(content)  # list/dict 등도 직렬화해 스캔(우회 차단)

    for pattern, description in SENSITIVE_CONTENT_PATTERNS:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            # 매칭된 값은 마스킹하여 로깅
            matched_text = match.group(0)
            masked = (
                matched_text[:4] + "***" + matched_text[-2:]
                if len(matched_text) > 6
                else "***"
            )
            debug_log(f"Sensitive content detected: {description} ({masked})")
            msg = f"메시지에 민감 정보가 포함되어 있습니다: {description}. 민감 정보를 제거한 후 다시 시도하세요."
            return True, msg

    return False, ""


def check_protected(file_path: str) -> tuple[bool, str]:
    """파일이 보호 대상인지 확인"""
    path_lower = file_path.lower()

    for pattern in PROTECTED_PATTERNS:
        if re.search(pattern, path_lower):
            debug_log(f"Pattern matched: {pattern} for {file_path}")

            # 어떤 유형인지 파악
            if ".env" in path_lower:
                return True, BLOCK_MESSAGES["env"]
            elif "secret" in path_lower:
                return True, BLOCK_MESSAGES["secrets"]
            elif "credential" in path_lower:
                return True, BLOCK_MESSAGES["credential"]
            elif (
                ".ssh" in path_lower
                or "id_rsa" in path_lower
                or "id_ed25519" in path_lower
            ):
                return True, BLOCK_MESSAGES["ssh"]
            elif any(
                k in path_lower for k in [".kube", ".docker", ".aws", ".gcp", ".azure"]
            ):
                return True, BLOCK_MESSAGES["cloud"]
            elif any(
                k in path_lower for k in [".npmrc", ".yarnrc", ".pypirc", ".netrc"]
            ):
                return True, BLOCK_MESSAGES["package"]
            elif any(k in path_lower for k in ["token", "password"]):
                return True, BLOCK_MESSAGES["token"]
            elif any(
                k in path_lower
                for k in [".pem", ".key", ".p12", ".pfx", "private", "_rsa", "_ecdsa"]
            ):
                return True, BLOCK_MESSAGES["key"]
            else:
                return True, "이 파일은 보안상 보호됩니다."

    return False, ""


def main():
    try:
        # stdin이 TTY면(파이프 입력 없음) json.load가 무한 블록한다 — 즉시 통과.
        if sys.stdin.isatty():
            sys.exit(0)
        # stdin에서 JSON 입력 읽기
        input_data = json.load(sys.stdin)

        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Agent Teams 메시지 콘텐츠 스캔 (S-C-08)
        if tool_name in ("message", "broadcast"):
            content = (
                tool_input.get("content", "")
                or tool_input.get("message", "")
                or tool_input.get("prompt", "")
            )
            if not content and isinstance(tool_input, dict):
                # 다양한 필드명에서 콘텐츠 추출 시도
                for key in ("text", "body", "data"):
                    content = tool_input.get(key, "")
                    if content:
                        break

            is_sensitive, msg = check_content_sensitive(content)
            if is_sensitive:
                print(f"🔒 메시지 차단됨: {tool_name}", file=sys.stderr)
                print(f"   {msg}", file=sys.stderr)
                sys.exit(2)

            sys.exit(0)

        # 파일 경로 기반 도구만 검사. MultiEdit/NotebookEdit도 편집 도구이므로 포함해야
        # 시크릿 파일 우회를 막는다(MultiEdit로 .env 편집 우회 방지, 적대적 리뷰 P1).
        if tool_name not in ("Edit", "MultiEdit", "Write", "Read", "NotebookEdit"):
            sys.exit(0)

        # NotebookEdit는 file_path 대신 notebook_path를 쓴다 — 둘 다에서 경로를 취한다.
        file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if not file_path:
            sys.exit(0)

        # 원본 경로부터 검사 — syscall 없는 순수 문자열 검사를 먼저 실행해, 뒤의
        # realpath(syscall)가 ValueError(널바이트 등)로 예외를 던져도 이 게이트가
        # 건너뛰어지지 않게 한다(적대적 리뷰 P2: 순서 fail-open 방지).
        is_protected, message = check_protected(file_path)
        if is_protected:
            print(f"🔒 차단됨: {file_path}", file=sys.stderr)
            print(f"   {message}", file=sys.stderr)
            sys.exit(2)  # 2 = 차단

        # 실제 경로(resolved) 항상 검사 — 중간 경로 symlink 우회 방지 (ATK-007)
        try:
            real_path = os.path.realpath(file_path)
        except (ValueError, OSError):
            real_path = file_path  # realpath 실패 시에도 위 원본 검사는 이미 통과함
        if real_path != os.path.abspath(file_path):
            is_protected_real, message_real = check_protected(real_path)
            if is_protected_real:
                print(
                    f"🔒 차단됨 (심볼릭 링크 대상): {file_path} → {real_path}",
                    file=sys.stderr,
                )
                print(f"   {message_real}", file=sys.stderr)
                sys.exit(2)

        sys.exit(0)  # 0 = 허용

    except json.JSONDecodeError:
        # fail-open: stdin 파싱 실패 시 허용 (Claude Code 런타임 제공 JSON이므로 실제 위험 낮음)
        debug_log("JSON decode error in stdin")
        sys.exit(0)
    except Exception as e:
        # fail-open: 예기치 않은 오류 시 허용 (가용성 우선 설계)
        debug_log(f"Hook error: {e}", e)
        sys.exit(0)


if __name__ == "__main__":
    main()
