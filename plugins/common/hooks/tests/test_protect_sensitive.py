"""Tests for protect-sensitive.py hook."""

import importlib.util
import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

HOOKS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "protect_sensitive", HOOKS_DIR / "protect-sensitive.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["protect_sensitive"] = _mod
_spec.loader.exec_module(_mod)

check_protected = _mod.check_protected
check_content_sensitive = _mod.check_content_sensitive


def run_main(input_data: dict) -> int:
    """Run main() with given stdin JSON, return the exit code."""
    stdin_text = json.dumps(input_data)
    with patch("sys.stdin", StringIO(stdin_text)):
        try:
            _mod.main()
        except SystemExit as e:
            return e.code
    return 0


class TestCheckProtected:
    def test_env_file_blocked(self):
        blocked, msg = check_protected(".env")
        assert blocked
        assert msg

    def test_env_local_blocked(self):
        blocked, _ = check_protected(".env.local")
        assert blocked

    def test_env_production_blocked(self):
        blocked, _ = check_protected(".env.production")
        assert blocked

    def test_secrets_dir_blocked(self):
        blocked, _ = check_protected("/app/secrets/db.json")
        assert blocked

    def test_credential_file_blocked(self):
        blocked, _ = check_protected("/home/user/credentials.json")
        assert blocked

    def test_ssh_dir_blocked(self):
        blocked, _ = check_protected("/home/user/.ssh/id_rsa")
        assert blocked

    def test_aws_config_blocked(self):
        blocked, _ = check_protected("/home/user/.aws/credentials")
        assert blocked

    def test_pem_file_blocked(self):
        blocked, _ = check_protected("/certs/server.pem")
        assert blocked

    def test_npmrc_blocked(self):
        blocked, _ = check_protected("/home/user/.npmrc")
        assert blocked

    def test_token_file_blocked(self):
        blocked, _ = check_protected("/config/api_token.json")
        assert blocked

    def test_password_file_blocked(self):
        blocked, _ = check_protected("/config/my_password.txt")
        assert blocked

    def test_normal_python_file_allowed(self):
        blocked, _ = check_protected("/app/src/main.py")
        assert not blocked

    def test_normal_json_file_allowed(self):
        blocked, _ = check_protected("/app/config/settings.json")
        assert not blocked

    def test_readme_allowed(self):
        blocked, _ = check_protected("/app/README.md")
        assert not blocked

    def test_secrets_dir_in_path_but_not_secrets_subdir(self):
        # "secrets" substring in non-directory context
        blocked, _ = check_protected("/app/src/secrets_manager.py")
        # "secret" pattern — this contains "secret" so should be blocked
        # secrets_manager.py matches the secret pattern (but not secrets dir)
        # The pattern excludes "secrets/" dir and "secrets." ext, but "secrets_" is included
        assert blocked  # "secret" literal is present without exclusion match

    def test_kube_config_blocked(self):
        blocked, _ = check_protected("/home/user/.kube/config")
        assert blocked


class TestCheckContentSensitive:
    def test_sk_api_key_blocked(self):
        sensitive, msg = check_content_sensitive("my key is sk-abcdefghij1234567890xyz")
        assert sensitive
        assert "API 키" in msg

    def test_aws_access_key_blocked(self):
        sensitive, _ = check_content_sensitive("AKIAIOSFODNN7EXAMPLE here")
        assert sensitive

    def test_github_token_blocked(self):
        sensitive, _ = check_content_sensitive("token: ghp_" + "a" * 36)
        assert sensitive

    def test_ssh_private_key_blocked(self):
        sensitive, _ = check_content_sensitive("-----BEGIN RSA PRIVATE KEY-----")
        assert sensitive

    def test_postgres_url_with_creds_blocked(self):
        sensitive, _ = check_content_sensitive("postgres://user:pass@localhost/db")
        assert sensitive

    def test_password_literal_blocked(self):
        sensitive, _ = check_content_sensitive("password=supersecret123")
        assert sensitive

    def test_jwt_blocked(self):
        # Minimal valid-looking JWT
        header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        payload = "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0"
        sig = "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        sensitive, _ = check_content_sensitive(f"{header}.{payload}.{sig}")
        assert sensitive

    def test_clean_content_allowed(self):
        sensitive, _ = check_content_sensitive("Hello world, here is my code review.")
        assert not sensitive

    def test_empty_content_allowed(self):
        sensitive, _ = check_content_sensitive("")
        assert not sensitive


class TestMainIntegration:
    def test_edit_env_file_blocked(self):
        code = run_main({"tool_name": "Edit", "tool_input": {"file_path": ".env"}})
        assert code == 2

    def test_write_env_file_blocked(self):
        code = run_main(
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/.env"}}
        )
        assert code == 2

    def test_read_normal_file_allowed(self):
        code = run_main(
            {"tool_name": "Read", "tool_input": {"file_path": "/app/main.py"}}
        )
        assert code == 0

    def test_other_tool_allowed(self):
        code = run_main({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert code == 0

    def test_message_with_secret_blocked(self):
        code = run_main(
            {
                "tool_name": "message",
                "tool_input": {"content": "my key sk-abcdefghij1234567890xyz"},
            }
        )
        assert code == 2

    def test_message_without_secret_allowed(self):
        code = run_main(
            {"tool_name": "message", "tool_input": {"content": "Hello agent, proceed."}}
        )
        assert code == 0

    def test_malformed_json_allows(self):
        with patch("sys.stdin", StringIO("not valid json")):
            try:
                _mod.main()
            except SystemExit as e:
                assert e.code == 0

    def test_missing_file_path_allows(self):
        code = run_main({"tool_name": "Edit", "tool_input": {}})
        assert code == 0
