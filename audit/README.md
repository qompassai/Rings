# The Rings audit framework

`run_audit.py` is a stdlib-only Python runner. It audits the Tiger Style guides **where they live** — the guides are skills in the estate (`~/workspace/skills/tiger-style-<lang>/`, with registration copies in `~/workspace/custom-skills/` and layered variants in the diver repo). Rings deliberately does not vendor copies of the guides: a vendored copy would be one more thing to drift.

## Run

```sh
python3 audit/run_audit.py
```

Writes `results/results.json` (machine-readable, full detail) and regenerates `INVENTORY.md`. Exit code 1 means a FAIL-class check fired.

## Check classes

- **Earth — inventory.** Every file of every guide copy is hashed (sha256) and sized.
- **Water — consistency.**
  - *Copy drift:* a file present in both the canonical skill and the custom-skills copy must be byte-identical (`skill.yaml` excepted — it exists only in custom-skills, as the registration file). Drift here is FAIL-class.
  - *Diver variants:* diver skills are layered (a base guide plus nested, language-specific sub-skills), so shared-file agreement with canonical is recorded but drift is reported, not failed.
  - *Claim agreement:* tools named on the SKILL.md "Toolchain pairing" line must appear in the full guide; version pins are extracted from both and set-compared.
  - *Coverage:* the full guide is scanned per aspect (keyword evidence + pin extraction). Coverage is a signal for human review, not a verdict.
- **Fire / Wind — research merge.** Currency and contradiction verdicts live in `research/<lang>.json`, one record per language, produced by cited research against primary sources (official docs and release pages). The runner validates the schema and enforces the citation rule: **a `stale`, `contradicted`, or `improved-elsewhere` verdict with no citation is downgraded to `unverified`.** The audit never repeats an uncited claim.

## Verdicts

`holds` · `stale` · `contradicted` · `improved-elsewhere` · `not-addressed` · `unverified` — per language, per aspect (matrix in `aspects.json`).

A prescription stricter than the official default is not a contradiction; contradiction means the official source says the guide's approach is wrong, harmful, or deprecated. Practice disagreements are proposals in `FINDINGS.md`, decided by a human — the framework never rewrites doctrine.
