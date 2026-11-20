"""Check a git diff against the active CIF guard rules in cif_rules.json.

Uses the guard-rule evaluator from the Context Intelligence Framework (CIF),
https://github.com/nagarwal00/context-engine-prototype-, checked out locally.

Usage:
    python tools/cif_guard.py --engine PATH_TO_CIF --base BASE_SHA --head HEAD_SHA [--rules cif_rules.json]
    python tools/cif_guard.py --engine PATH_TO_CIF --diff-file change.diff

Exit codes: 0 no violations, 1 violations found, 2 usage or evaluation error.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git_diff(base: str, head: str) -> str:
    result = subprocess.run(
        ["git", "diff", f"{base}...{head}"],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    return result.stdout


def changed_files(diff_text: str) -> list:
    return [line[6:].strip() for line in diff_text.splitlines() if line.startswith("+++ b/")]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engine", required=True, help="path to a checkout of the CIF repository")
    parser.add_argument("--rules", default=os.path.join(REPO_ROOT, "cif_rules.json"))
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--diff-file", help="read the diff from a file instead of git")
    args = parser.parse_args(argv)

    engine = os.path.abspath(args.engine)
    if not os.path.isfile(os.path.join(engine, "backend", "engine", "guard_rules.py")):
        print(f"[cif-guard] not a CIF checkout: {engine}", file=sys.stderr)
        return 2
    sys.path.insert(0, engine)
    from backend.engine.guard_rules import check_diff_against_guard_rules_with_report

    if args.diff_file:
        with open(args.diff_file, encoding="utf-8") as fh:
            diff_text = fh.read()
    elif args.base and args.head:
        diff_text = git_diff(args.base, args.head)
    else:
        print("[cif-guard] give --base and --head, or --diff-file", file=sys.stderr)
        return 2

    with open(args.rules, encoding="utf-8") as fh:
        rules = [r for r in json.load(fh) if r.get("status") == "active"]
    files = changed_files(diff_text)
    print(f"[cif-guard] {len(rules)} active rule(s); changed files: {files or 'none'}")

    report = check_diff_against_guard_rules_with_report(rules, files, diff_text)
    for err in report["errors"]:
        print(f"[cif-guard] ERROR {err['rule_id']}: {err['message']}", file=sys.stderr)
    if report["errors"]:
        return 2

    if not report["violations"]:
        print("[cif-guard] PASS: no architectural decision violated")
        return 0

    print(f"[cif-guard] FAIL: {len(report['violations'])} violation(s)")
    for v in report["violations"]:
        print(f"  - {v['file']}: {v['line']}")
        print(f"    {v['message']}")
        print(f"    {v['citation']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
