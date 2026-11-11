"""Run import and the model gate over ArchiMate exchange files this repository did not write.

Every model the tooling had been run on was written by its own author: the worked example,
the golden cases, the fixtures. This is the first evidence about models written by other
people, for other purposes, in other tools. Each source below is an openly licensed public
repository (MIT or Apache-2.0), read at a pinned commit; the files are downloaded into a
scratch directory and **never committed** -- the manifest is what is committed, so the run
can be repeated.

Per file: does `import` refuse it, crash, or land it in staging; what does `validate
--zone staging` then find, by rule code; how long did each take. A crash is the finding
that matters most -- a gate that crashes reports nothing -- and the rule distribution is the
first picture of what other people's models look like to this gate.

EAModelSet (me-big-tuwien-ac-at), the largest public ArchiMate corpus, is deliberately
absent: its repository carries no licence (checked 2026-11-11), and the plan required the
licence first.

    python tools/corpus_run.py <scratch-dir> [--json report.json]

Network only to fetch the pinned files (raw.githubusercontent.com); standard library plus
the tooling itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# (repository, commit, licence, paths). Licences read from the GitHub API on 2026-11-11.
MANIFEST: list[tuple[str, str, str, list[str]]] = [
    ("canada-ca/architecture", "422feb5de1ce", "MIT", ["archimate_exchange_files/"]),
    ("GfSE/SpecIF-Examples-and-Test-cases", "fc5663625635", "Apache-2.0", ["Archimate-3/"]),
    ("ThomasRohde/archimate-renderer", "1fb9fefaa245", "MIT", ["examples/"]),
    ("borkdominik/CM2KG", "961d32b33b2d", "MIT", ["TestInstances/Archi/"]),
    ("abcoates/archi-xml-excel-converter", "bcbac07e2230", "Apache-2.0", [""]),
    ("dclnbrght/archiscribe-mcp", "e1249d8f2e26", "MIT", ["data/"]),
    ("tommimarkus/dediren", "862af74e7fe2", "MIT", ["fixtures/"]),
    ("StevenBtw/anywidget-archimate", "9149cc3401c6", "Apache-2.0", ["examples/"]),
    ("cgbarlow/iris", "a0f8781f0441", "Apache-2.0", ["docs/reference/ArchiMate/"]),
    # master on 2026-11-11 (committed 2026-11-09): the commit the first run read, now pinned.
    ("archimatetool/archi", "d605afada2ad", "MIT", ["tests/org.opengroup.archimate.xmlexchange.tests/testdata/"]),
]
NAMESPACE = b"opengroup.org/xsd/archimate"


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "corpus-run"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def fetch(scratch: Path) -> tuple[list[tuple[str, str, Path]], list[str]]:
    """Download every exchange file under the manifest's paths.

    Returns ``(files, failures)``: (repo, licence, local path) per file, and one line per
    repository or file that could not be fetched -- a network error costs that file, never
    the run.
    """
    found: list[tuple[str, str, Path]] = []
    failures: list[str] = []
    for repo, commit, licence, prefixes in MANIFEST:
        try:
            tree = json.loads(_get(f"https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1"))
        except (OSError, ValueError) as exc:
            failures.append(f"{repo}@{commit}: tree not fetched -- {exc}")
            continue
        for entry in tree.get("tree", []):
            path = entry.get("path", "")
            if entry.get("type") != "blob" or not path.lower().endswith(".xml"):
                continue
            if not any(path.startswith(prefix) for prefix in prefixes):
                continue
            try:
                body = _get(f"https://raw.githubusercontent.com/{repo}/{commit}/{urllib.parse.quote(path)}")
            except OSError as exc:
                failures.append(f"{repo}@{commit}/{path}: not fetched -- {exc}")
                continue
            if NAMESPACE not in body[:4000]:
                continue
            target = scratch / "files" / repo.replace("/", "__") / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            found.append((repo, licence, target))
    return found, failures


def run_one(scratch: Path, source: Path) -> dict:
    # Named by the file's whole path, shortened: two sources may share a file name, and
    # Windows paths have a length limit the repository's own layout already spends.
    relative = source.relative_to(scratch / "files").as_posix()
    root = scratch / "repos" / f"{source.stem[:40]}-{hashlib.sha256(relative.encode()).hexdigest()[:8]}"
    if root.exists():
        shutil.rmtree(root)
    (root / "model").mkdir(parents=True)
    (root / "ea.config.yaml").write_text("name: Corpus probe\n", encoding="utf-8")
    entry: dict = {"file": str(source.relative_to(scratch / "files")), "bytes": source.stat().st_size}
    started = time.perf_counter()
    imported = subprocess.run(
        [sys.executable, "-m", "easkills", "import", "--root", str(root), "--file", str(source), "--json", str(root / "import.json")],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
    )
    entry["importSeconds"] = round(time.perf_counter() - started, 2)
    entry["importExit"] = imported.returncode
    if "Traceback" in imported.stderr:
        entry["crash"] = imported.stderr.strip().splitlines()[-1][:300]
        return entry
    if imported.returncode != 0:
        entry["refused"] = (imported.stdout.strip().splitlines() or [""])[-1][:300]
        return entry
    report = json.loads((root / "import.json").read_text(encoding="utf-8"))
    counts = report.get("counts") or {}
    entry["elements"], entry["relationships"], entry["views"] = counts.get("elements"), counts.get("relationships"), counts.get("views")
    entry["skipped"] = len(report.get("skipped", []))
    started = time.perf_counter()
    validated = subprocess.run(
        [sys.executable, "-m", "easkills", "validate", "--root", str(root), "--zone", "staging", "--json", str(root / "validate.json")],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
    )
    entry["validateSeconds"] = round(time.perf_counter() - started, 2)
    entry["validateExit"] = validated.returncode
    if "Traceback" in validated.stderr:
        entry["crash"] = validated.stderr.strip().splitlines()[-1][:300]
        return entry
    if not (root / "validate.json").is_file():  # refused before it judged anything: a finding, not a crash of this tool
        entry["refused"] = ((validated.stdout + validated.stderr).strip().splitlines() or ["no output"])[-1][:300]
        return entry
    findings = json.loads((root / "validate.json").read_text(encoding="utf-8"))["findings"]
    entry["codes"] = dict(Counter(f["code"] for f in findings if f["severity"] in {"error", "warning"}))
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("scratch", type=Path)
    parser.add_argument("--json", dest="json_out", type=Path)
    args = parser.parse_args(argv)
    args.scratch.mkdir(parents=True, exist_ok=True)
    files, fetch_failures = fetch(args.scratch)
    results = [dict(run_one(args.scratch, path), repo=repo, licence=licence) for repo, licence, path in files]
    totals = Counter()
    for result in results:
        totals.update(result.get("codes", {}))
    summary = {
        "files": len(results),
        "fetchFailures": fetch_failures,
        "crashes": [r for r in results if "crash" in r],
        "refusals": [r for r in results if "refused" in r],
        "elements": sum(r.get("elements") or 0 for r in results),
        "relationships": sum(r.get("relationships") or 0 for r in results),
        "codes": dict(totals.most_common()),
        "slowest": max((r.get("importSeconds", 0) + r.get("validateSeconds", 0) for r in results), default=0),
        "results": results,
    }
    if args.json_out:
        args.json_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        f"{summary['files']} files, {summary['elements']} elements, {summary['relationships']} relationships; "
        f"{len(summary['crashes'])} crash(es), {len(summary['refusals'])} refusal(s); slowest {summary['slowest']:.1f} s"
    )
    for code, count in summary["codes"].items():
        print(f"  {code:10s} {count}")
    for crash in summary["crashes"]:
        print(f"  CRASH {crash['file']}: {crash['crash']}")
    for refusal in summary["refusals"]:
        print(f"  refused {refusal['file']}: {refusal['refused']}")
    for failure in fetch_failures:
        print(f"  NOT FETCHED {failure}")
    return 1 if summary["crashes"] or fetch_failures else 0


if __name__ == "__main__":
    sys.exit(main())
