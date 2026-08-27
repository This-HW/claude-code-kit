This repo's completion gate has **three** checks that ask "does the generated artifact match its
source of truth?" — `AGENTS.md` marker block vs `rules/` (sha256), eval scenarios vs baseline (set
comparison + tier coverage), and target manifests vs the plugin SSOT (existence + content diff).
They look like the same question, but **the input, the pass/fail criteria, and the failure message
are all different for each.**

**They are not merged into one shared abstraction.** A common primitive would have to bend to fit
all three cases — more branching parameters, harder-to-read gate code. A gate only works if
whoever reads a failure trusts it enough to act; a gate nobody can follow gets ignored when it goes
red.

Duplication here is reduced through **convention, not code** — e.g. the path-containment pattern
above, followed the same way in every place a config value becomes a file path, is exactly that.
A fourth "does the generated thing match its source" gate is the point to reconsider this — not
before. Rule-of-three isn't "merge at the third instance," it's "the third instance is still not
necessarily a pattern."
