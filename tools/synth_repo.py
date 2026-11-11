"""A deterministic synthetic architecture repository, for measuring the gates at scale.

The worked example has 17 elements, and nothing in the test suite had ever run a gate on
more. The first measurement (2026-11-10) found ``validate`` superlinear -- 1.9 s at 300
elements, 66.9 s at 3000 -- and the cause was a constant factor nobody could have seen
at 17. This script makes that measurement repeatable: it copies the worked example and
adds ``n`` application components, ``2n`` flow relationships and one view, every concept
quote-verified against one synthetic inventory.

Same input, same bytes: no randomness, no clock. ``tests/test_scale.py`` uses it small,
to assert operation counts; run it large by hand to time the gates::

    python tools/synth_repo.py <out-dir> 3000 --view 300
    python -m easkills validate --root <out-dir>

Standard library only, and it only writes inside ``<out-dir>``, which it refuses to
overwrite unless it already holds a synthetic repository.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "eval" / "example"
MARKER = ".synthetic-repository"
SOURCE = "facts/sources/synthetic-inventory.md"


def _sentence(i: int) -> str:
    return f"System number {i:05d} handles workload stream {i * 7919 % 100003} for the regional unit."


def build(out: Path, n: int, view_size: int = 0) -> Path:
    """Write the repository into ``out`` and return it."""
    if out.exists():
        if not (out / MARKER).is_file():
            raise SystemExit(f"{out} exists and is not a synthetic repository; refusing to overwrite it")
        shutil.rmtree(out)
    # Unsealed on purpose: the synthetic file was never promoted, and a scale probe is not a
    # signature.
    shutil.copytree(EXAMPLE, out, ignore=shutil.ignore_patterns("docs", "build", "approvals"))
    (out / MARKER).write_text("written by tools/synth_repo.py\n", encoding="utf-8", newline="\n")

    lines = ["# Synthetic inventory", ""]
    for i in range(n):
        lines += [_sentence(i), ""]
    (out / SOURCE).write_text("\n".join(lines), encoding="utf-8", newline="\n")

    def provenance(i: int) -> list[str]:
        return [
            "    owner: synthetic@aurorafoods.example",
            "    lastReviewed: 2026-06-30",
            "    provenance:",
            f"      - file: {SOURCE}",
            f"        quote: {_sentence(i)}",
        ]

    out_lines = ["elements:"]
    for i in range(n):
        out_lines += [
            f"  - id: app-syn-{i:05d}",
            "    type: ApplicationComponent",
            f"    name: Synthetic System {i:05d}",
            *provenance(i),
        ]
    out_lines.append("relationships:")
    for i in range(n):
        for step in (1, 17):
            out_lines += [
                f"  - id: rel-syn-{i:05d}-{step}",
                "    type: Flow",
                f"    source: app-syn-{i:05d}",
                f"    target: app-syn-{(i + step) % n:05d}",
                *provenance(i),
            ]
    shown = min(view_size, n)
    if shown:
        out_lines += [
            "views:",
            "  - id: synthetic-landscape",
            "    name: Synthetic Landscape",
            "    viewpoint: Layered",
            "    concerns: [concern-ordering-availability]",
            "    documentation: Synthetic scale probe.",
            "    include:",
            *(f"      - app-syn-{i:05d}" for i in range(shown)),
        ]
    (out / "model" / "approved" / "synthetic.yaml").write_text(
        "\n".join(out_lines) + "\n", encoding="utf-8", newline="\n"
    )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("out", type=Path, help="directory to write (refused unless empty or synthetic)")
    parser.add_argument("n", type=int, help="number of application components (relationships: 2n)")
    parser.add_argument("--view", type=int, default=0, help="elements in one generated view (default: none)")
    args = parser.parse_args(argv)
    if args.n < 2:
        parser.error("n must be at least 2")
    build(args.out, args.n, args.view)
    print(f"wrote {args.out}: {args.n} elements, {2 * args.n} relationships, view of {min(args.view, args.n)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
