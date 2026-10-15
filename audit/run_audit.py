#!/usr/bin/env python3
"""Rings audit runner.

Audits the Tiger Style language guides where they live (they are skills in the
estate, not vendored into this repo — vendoring would create one more copy to
drift). Three mechanical check classes run here:

  Earth  inventory   every guide file, every copy, hashed (sha256)
  Water  consistency copy drift + skill-summary vs full-guide claim agreement
                     + per-aspect coverage scan of the full guide
  Fire/Wind          research records (audit/research/<lang>.json) are merged
                     and validated: a stale / contradicted / improved-elsewhere
                     verdict with no primary-source citation is downgraded to
                     "unverified". The audit does not repeat uncited claims.

Usage:  python3 audit/run_audit.py [--guides-root DIR] [--out DIR]
Writes: results/results.json and INVENTORY.md (in the repo root / --out dir).
Exit:   1 if any FAIL-class check fires (canonical vs custom-skills drift on a
        shared file, or a research record fails schema validation), else 0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ASPECTS = [
    "assertions_contracts",
    "bounded_work",
    "concurrency",
    "error_handling",
    "formatting",
    "memory_ownership",
    "security",
    "static_analysis",
    "testing",
    "toolchain_pins",
]

VERDICTS = {
    "contradicted",
    "holds",
    "improved-elsewhere",
    "not-addressed",
    "stale",
    "unverified",
}

CITED_VERDICTS = {"contradicted", "improved-elsewhere", "stale"}

ASPECT_KEYWORDS = {
    "assertions_contracts": ["assert", "contract", "invariant", "postcondition", "precondition"],
    "bounded_work": ["bound", "limit", "maximum", "recursion", "timeout"],
    "concurrency": ["async", "concurren", "mutex", "race", "thread"],
    "error_handling": ["errno", "error", "exception", "panic", "result<", "std::expected"],
    "formatting": ["format", "formatter", "formatting"],
    "memory_ownership": ["allocat", "arena", "borrow", "lifetime", "memory", "ownership"],
    "security": ["injection", "sanitiz", "secret", "security", "threat", "unsafe"],
    "static_analysis": ["analyzer", "clippy", "diagnostic", "lint", "static analysis"],
    "testing": ["adversarial", "test", "validation"],
    "toolchain_pins": [],  # measured by pin extraction, not keywords
}

PIN_PATTERNS = [
    re.compile(r"nightly-\d{4}-\d{2}-\d{2}"),
    re.compile(r"\bC\+\+\d{2}\b"),
    re.compile(r"\bES20\d{2}\b"),
    re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b"),
]

STOPWORDS = {
    "and", "dap", "debugger", "docs", "for", "formatter", "guide", "language",
    "linter", "lsp", "pairing", "server", "the", "toolchain", "with",
}


def normalize_skill(text: str, is_custom: bool) -> str:
    """Registration-format normalization for SKILL.md copies.

    The custom-skills copies are recovered skills: the recovery stripped the
    YAML frontmatter (name/description) and appended an 'Available connectors'
    boilerplate section. Byte drift from those two mechanical causes is a
    format finding, not content drift — so SKILL.md comparisons are made on
    normalized text as well as raw bytes.
    """
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    if is_custom:
        text = re.sub(r"\n## Available connectors\n.*\Z", "", text, flags=re.S)
    return text.strip()


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def list_files(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = p
    return out


def extract_pins(text: str) -> set[str]:
    pins: set[str] = set()
    for pat in PIN_PATTERNS:
        pins.update(m.group(0) for m in pat.finditer(text))
    return pins


GENERIC_TOKENS = {
    "actions", "code", "completions", "dap", "debugging", "diagnostics",
    "for", "formatting", "lsp", "debugging.", "the", "and", "with",
}


def strip_frontmatter(text: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)


def pairing_tokens(skill_text: str) -> set[str]:
    """Tool names on the SKILL.md 'Toolchain pairing:' segment.

    The segment lives in the frontmatter description in these skills. Take the
    text after the marker up to the sentence end, then drop generic role words
    (LSP, diagnostics, formatting, ...) so what remains is tool names.
    """
    idx = skill_text.find("Toolchain pairing:")
    if idx < 0:
        return set()
    seg = skill_text[idx + len("Toolchain pairing:"):]
    seg = re.split(r"\.\s|\"\s|\n", seg, maxsplit=1)[0]
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_+-]*[A-Za-z0-9]|[A-Za-z]{3,}", seg)
    return {t for t in tokens if t.lower() not in GENERIC_TOKENS and t.lower() not in STOPWORDS}


def coverage(guide_text: str) -> dict[str, str]:
    """Keyword-evidence scan: total occurrences of the aspect's vocabulary.

    A signal for human review, not a verdict — a guide can cover an aspect in
    vocabulary this scan does not know (tool names, idioms). The cited research
    record is authoritative; the scan exists to catch guides that are silent.
    """
    low = guide_text.lower()
    cov: dict[str, str] = {}
    for aspect in ASPECTS:
        if aspect == "toolchain_pins":
            cov[aspect] = "covered" if extract_pins(guide_text) else "absent"
            continue
        hits = sum(low.count(kw) for kw in ASPECT_KEYWORDS[aspect])
        cov[aspect] = "covered" if hits >= 5 else ("thin" if hits >= 1 else "absent")
    return cov


def audit_language(lang: str, roots: dict[str, Path], research_dir: Path) -> dict:
    canon_dir = roots["canonical"] / f"tiger-style-{lang}"
    custom_dir = roots["custom"] / f"local-tiger-style-{lang}"
    diver_dir = roots["diver"] / lang / f"tiger-style-{lang}"

    canon = list_files(canon_dir)
    custom = list_files(custom_dir)
    diver = list_files(diver_dir)

    def hashed(files: dict[str, Path]) -> dict[str, dict]:
        return {
            rel: {"bytes": p.stat().st_size, "sha256": sha256_of(p)}
            for rel, p in files.items()
        }

    inventory = {
        "canonical": hashed(canon),
        "custom_skills": hashed(custom),
        "diver": hashed(diver),
    }

    drift: list[dict] = []
    fails: list[str] = []

    # Canonical vs custom-skills: same relative file must be byte-identical.
    for rel in sorted(set(canon) | set(custom)):
        if rel == "skill.yaml":
            continue  # custom-skills registration file; canonical has none
        in_c, in_u = rel in canon, rel in custom
        if in_c and in_u:
            same = inventory["canonical"][rel]["sha256"] == inventory["custom_skills"][rel]["sha256"]
            if same:
                continue
            if rel == "SKILL.md":
                a = normalize_skill(canon[rel].read_text(encoding="utf-8", errors="replace"), False)
                b = normalize_skill(custom[rel].read_text(encoding="utf-8", errors="replace"), True)
                if a == b:
                    drift.append({
                        "pair": "canonical_vs_custom", "file": rel, "state": "FORMAT_DRIFT",
                        "detail": "bytes differ; content identical after registration-format "
                                  "normalization (frontmatter stripped + recovery boilerplate)",
                    })
                    continue
            drift.append({"pair": "canonical_vs_custom", "file": rel, "state": "DRIFT"})
            fails.append(f"{lang}: canonical vs custom-skills DRIFT on {rel}")
        else:
            drift.append({
                "pair": "canonical_vs_custom",
                "file": rel,
                "state": "ONLY_IN_CANONICAL" if in_c else "ONLY_IN_CUSTOM",
            })

    # Diver: record shared-file agreement; diver skills are layered variants
    # (base guide + nested specifics), so drift here is reported, not failed.
    for rel in sorted(set(canon) & set(diver)):
        same = inventory["canonical"][rel]["sha256"] == inventory["diver"][rel]["sha256"]
        drift.append({
            "pair": "canonical_vs_diver",
            "file": rel,
            "state": "MATCH" if same else "DRIFT",
        })

    # Skill <-> guide claim agreement.
    skill_path = canon.get("SKILL.md")
    guide_rel = next((r for r in canon if r.startswith("references/") and r.endswith(".md")), None)
    claims: dict = {}
    cov: dict[str, str] = {}
    if skill_path and guide_rel:
        skill_text = skill_path.read_text(encoding="utf-8", errors="replace")
        guide_text = canon[guide_rel].read_text(encoding="utf-8", errors="replace")
        tokens = pairing_tokens(skill_text)
        missing = sorted(t for t in tokens if t.lower() not in guide_text.lower())
        # Pins are extracted from body text only: frontmatter carries the
        # license line (Apache-2.0), which is not a toolchain pin.
        skill_pins = extract_pins(strip_frontmatter(skill_text))
        guide_pins = extract_pins(strip_frontmatter(guide_text))
        claims = {
            "pairing_tokens_not_in_guide": missing,
            "pins_in_skill_not_in_guide": sorted(skill_pins - guide_pins),
            "pins_in_guide_not_in_skill": sorted(guide_pins - skill_pins),
        }
        cov = coverage(guide_text)

    # Research record: schema + citation integrity.
    research: dict = {"status": "missing"}
    rpath = research_dir / f"{lang}.json"
    if rpath.is_file():
        try:
            rec = json.loads(rpath.read_text(encoding="utf-8"))
            problems: list[str] = []
            aspects = rec.get("aspects", {})
            for aspect in ASPECTS:
                if aspect not in aspects:
                    problems.append(f"missing aspect {aspect}")
                    continue
                a = aspects[aspect]
                v = a.get("verdict")
                if v not in VERDICTS:
                    problems.append(f"{aspect}: bad verdict {v!r}")
                elif v in CITED_VERDICTS and not a.get("citations"):
                    a["verdict"] = "unverified"
                    a["downgrade_note"] = "verdict carried no citation; downgraded by runner"
                    problems.append(f"{aspect}: uncited {v} downgraded to unverified")
            research = {"status": "invalid" if problems else "ok", "problems": problems, "record": rec}
            if problems:
                fails.append(f"{lang}: research record problems: {problems}")
        except json.JSONDecodeError as exc:
            research = {"status": "invalid", "problems": [f"JSON error: {exc}"]}
            fails.append(f"{lang}: research JSON invalid")

    return {
        "language": lang,
        "inventory": inventory,
        "drift": drift,
        "claims": claims,
        "coverage": cov,
        "research": research,
        "fails": fails,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    home = Path.home()
    ap.add_argument("--canonical-root", type=Path, default=home / "workspace/skills")
    ap.add_argument("--custom-root", type=Path, default=home / "workspace/custom-skills")
    ap.add_argument("--diver-root", type=Path, default=home / "workspace/repos/diver/skills")
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    args = ap.parse_args()

    repo: Path = args.repo
    research_dir = repo / "audit" / "research"
    roots = {"canonical": args.canonical_root, "custom": args.custom_root, "diver": args.diver_root}

    langs = sorted(
        d.name.removeprefix("tiger-style-")
        for d in args.canonical_root.iterdir()
        if d.is_dir() and d.name.startswith("tiger-style-")
    )

    results = [audit_language(lang, roots, research_dir) for lang in langs]
    all_fails = [f for r in results for f in r["fails"]]

    verdict_counts: dict[str, int] = {}
    for r in results:
        rec = r["research"].get("record")
        if rec:
            for a in rec.get("aspects", {}).values():
                verdict_counts[a["verdict"]] = verdict_counts.get(a["verdict"], 0) + 1

    payload = {
        "audit": "rings",
        "languages": langs,
        "verdict_counts": verdict_counts,
        "fail_count": len(all_fails),
        "results": results,
    }
    (repo / "results").mkdir(exist_ok=True)
    (repo / "results" / "results.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    # INVENTORY.md
    lines = [
        "# Inventory — Tiger Style guides and their copies",
        "",
        "Generated by `audit/run_audit.py`. Locations: canonical = `~/workspace/skills/tiger-style-<lang>/`; "
        "custom-skills = `~/workspace/custom-skills/local-tiger-style-<lang>/`; diver = `~/workspace/repos/diver/skills/<lang>/tiger-style-<lang>/`. "
        "No copies exist under `/opt/muse/skills` (checked 2026-10-14).",
        "",
        "| Language | Canonical files | Custom-skills | Diver | Drift (canonical vs custom) |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        n_c = len(r["inventory"]["canonical"])
        n_u = len(r["inventory"]["custom_skills"])
        n_d = len(r["inventory"]["diver"])
        dcount = sum(1 for d in r["drift"] if d["pair"] == "canonical_vs_custom" and d["state"] == "DRIFT")
        fcount = sum(1 for d in r["drift"] if d["pair"] == "canonical_vs_custom" and d["state"] == "FORMAT_DRIFT")
        if dcount:
            state = f"**{dcount} CONTENT DRIFT**"
        elif fcount:
            state = "format-only drift (SKILL.md)"
        else:
            state = "identical"
        lines.append(f"| {r['language']} | {n_c} | {n_u} files | {n_d} files | {state} |")
    lines += ["", "Per-file hashes and the full drift list are in `results/results.json`."]
    (repo / "INVENTORY.md").write_text("\n".join(lines) + "\n")

    print(f"languages audited: {len(langs)}")
    print(f"verdict counts: {json.dumps(verdict_counts, sort_keys=True)}")
    print(f"FAIL-class checks: {len(all_fails)}")
    for f in all_fails:
        print(f"  FAIL {f}")
    return 1 if all_fails else 0


if __name__ == "__main__":
    sys.exit(main())
