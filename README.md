# Rings

**Audit and validation tests for the Tiger Style language guides** — every prescription checked against current best practice, aspect by aspect, with citations.

Tiger Style is Qompass AI's house standard for code: seventeen language guides (Bash, C, C++, Go, Kotlin, Lua, Mojo, Nix, Odin, PHP, Python, Rust, Scala, TypeScript, WGSL, Zig, and Aseprite scripting), each pairing an operational skill summary with a full reference guide. Rings is where those guides are themselves held to a standard.

## Charter

> "Adapt what is useful, reject what is useless, and add what is specifically your own."
> — Bruce Lee, on Jeet Kune Do

> "To know ten thousand things, know one well."
> — Miyamoto Musashi, *The Book of Five Rings*

The repo is named for Musashi's *Book of Five Rings* (Go Rin No Sho). The audit runs in its five movements:

- **Earth** — *inventory.* Every guide, every copy, every location, hashed. Know the ground before judging it.
- **Water** — *consistency.* Each guide against itself: the skill summary against the full reference, copy against copy. Drift is a failure.
- **Fire** — *currency.* Version pins, toolchain pairings, and tool recommendations against the tools' current official documentation. Staleness is found, dated, and cited.
- **Wind** — *other traditions.* Each prescription against the language's official best practice. Where the official school is right and the guide is wrong, the finding says so; where the guide is deliberately stricter, the finding says that instead.
- **Void** — *what is our own.* Improvements worth adopting are written up as proposals with evidence. Doctrine changes by decision, never by drift.

## Lineage, held to its own standard

Tiger Style descends from TigerBeetle's [TigerStyle](https://github.com/tigerbeetle/tigerbeetle/blob/main/docs/TIGER_STYLE.md) and, behind it, NASA JPL's [Power of Ten](https://spinroot.com/gerard/pdf/P10.pdf) (Gerard J. Holzmann) — the shared creed being determinism, bounded work, and doing it right the first time. Rings exists because a standard that audits everything else does not get to exempt itself.

<details>
<summary>The aspect matrix</summary>

Every guide is audited on the same ten aspects (defined in `audit/aspects.json`):

| Aspect | What is checked |
|---|---|
| Error handling | The guide's error discipline vs the language's current idiom |
| Bounded work | Loop/recursion/resource bounds and their enforcement story |
| Assertions & contracts | Contract style, assertion policy, what the tooling verifies |
| Memory & ownership | Ownership/allocation discipline vs the language's model |
| Formatting | Formatter pairing and whether the pinned formatter is current |
| Static analysis | Linter/analyzer pairing, rule posture, tool currency |
| Concurrency | The guide's concurrency rules vs current official guidance |
| Testing | The validation/adversarial split and the test tooling named |
| Toolchain pins | Every version pin in the guide vs the current release |
| Security | Security prescriptions vs current official security guidance |

Verdicts per aspect: **holds** · **stale** · **contradicted** · **improved-elsewhere** · **not-addressed** (the aspect does not apply, or the guide is silent) · **unverified** (no primary source could settle it — stated, never guessed).

</details>

<details>
<summary>How an audit runs</summary>

```sh
python3 audit/run_audit.py
```

The runner (stdlib-only Python) performs the mechanical checks — inventory, hashing, copy drift, skill↔guide claim agreement, aspect coverage — merges the per-language research records in `audit/research/<lang>.json` (every currency and contradiction claim carries a primary-source URL and a retrieval date), and writes `results/results.json` plus a console summary. Findings are published in `FINDINGS.md`.

**Rules of engagement**

- Mechanical fixes — stale version pins, dead links, factual errors against official docs — are applied to the canonical guides and listed in `FINDINGS.md` with their evidence.
- Practice-level changes are **proposals** in `FINDINGS.md`, with evidence and a recommendation. They are adopted or rejected by decision; the audit never rewrites doctrine unilaterally.
- A prescription stricter than the official default is not a contradiction. Contradiction means the official source says the guide's approach is wrong, harmful, or deprecated.

</details>

<details>
<summary>Layout</summary>

- `INVENTORY.md` — the guides, their copies, and their drift state (generated).
- `FINDINGS.md` — the current audit: per language, per aspect, with evidence and citations; fixes applied; proposals.
- `audit/` — the framework: `aspects.json` (the matrix), `run_audit.py` (the runner), `research/<lang>.json` (cited research records).
- `results/` — machine-readable audit output (`results.json`).

</details>

## License

Apache-2.0. See `LICENSE`.
