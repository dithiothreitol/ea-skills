"""Command line entry point: ``python -m easkills <command>``.

Commands are the deterministic half of the pipeline -- the part skills call instead
of reasoning about. Exit code 1 means an error-severity finding, so the same
commands work as a CI gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import aoef, facts as facts_mod, genschema, intake, oracle, validate as validate_mod


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    parser.add_argument(
        "--zone",
        choices=["approved", "staging"],
        default="approved",
        help="which zone to read; governance metadata is mandatory in 'approved'",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="easkills", description="Deterministic tooling for the EA skills pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="run the three-layer validator")
    _add_common(p_validate)
    p_validate.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_validate.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as failures too",
    )

    p_compile = sub.add_parser("compile", help="compile the DSL to ArchiMate Open Exchange XML")
    _add_common(p_compile)
    p_compile.add_argument("--out", type=Path, help="output file (default: <root>/build/model.xml)")
    p_compile.add_argument(
        "--skip-validation",
        action="store_true",
        help="compile even if the validator reports errors (not recommended)",
    )

    p_facts = sub.add_parser("validate-facts", help="validate the fact register (facts/register + entities)")
    p_facts.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_facts.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_facts.add_argument("--strict", action="store_true", help="treat warnings as failures too")

    p_chunk = sub.add_parser("chunk", help="split source documents into deterministic extraction chunks")
    p_chunk.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_chunk.add_argument("--file", type=Path, help="one source file (default: every file under facts/sources)")
    p_chunk.add_argument("--max-chars", type=int, default=intake.DEFAULT_MAX_CHARS, help="chunk budget in characters")
    p_chunk.add_argument("--json", dest="json_out", action="store_true", help="print chunks as JSON")

    p_coverage = sub.add_parser("coverage", help="report which parts of the sources produced no facts")
    p_coverage.add_argument("--root", type=Path, default=Path.cwd(), help="model repository root (default: cwd)")
    p_coverage.add_argument("--json", dest="json_out", type=Path, help="also write the report as JSON")
    p_coverage.add_argument(
        "--min-coverage",
        type=float,
        metavar="PCT",
        help="exit 1 if overall coverage falls below this percentage (0-100)",
    )

    sub.add_parser("gen-schema", help="regenerate the JSON Schemas under schema/ from the oracle")
    sub.add_parser("pin-oracle", help="rewrite oracle/SHA256SUMS from the current oracle files")
    sub.add_parser("oracle-info", help="print oracle version and coverage")

    return parser


def cmd_validate(args: argparse.Namespace) -> int:
    report = validate_mod.validate(args.root.resolve(), zone=args.zone)
    print(report.render())
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")
    if not report.ok:
        return 1
    return 1 if args.strict and report.warnings else 0


def cmd_compile(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    if not args.skip_validation:
        report = validate_mod.validate(root, zone=args.zone)
        if not report.ok:
            print(report.render())
            print("\nRefusing to compile a model with validation errors (use --skip-validation to override).")
            return 1
    try:
        result = aoef.compile_model(root, zone=args.zone, out=args.out)
    except aoef.CompileError as exc:
        print(f"ERROR   {exc}")
        return 1
    print(
        f"Compiled {result.elements} elements, {result.relationships} relationships, "
        f"{result.views} view(s) -> {result.path}"
    )
    if result.schema_errors:
        print("\nOpen Exchange XSD validation FAILED:")
        for error in result.schema_errors[:20]:
            print(f"  {error}")
        return 1
    print("Open Exchange XSD validation passed.")
    return 0


def cmd_validate_facts(args: argparse.Namespace) -> int:
    report = facts_mod.validate_facts(args.root.resolve())
    print(report.render())
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")
    if not report.ok:
        return 1
    return 1 if args.strict and report.warnings else 0


def cmd_chunk(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    if args.file:
        path = args.file if args.file.is_absolute() else root / args.file
        if not path.is_file():
            print(f"ERROR   source file not found: {path}")
            return 1
        targets = [path]
    else:
        register, _docs, _entities = facts_mod.load(root)
        targets = facts_mod.iter_source_files(register)
        if not targets:
            print(f"No source files found under {register.sources_dir()}")
            return 1
    chunks: list[intake.Chunk] = []
    for path in targets:
        chunks.extend(intake.chunk_file(path, facts_mod._rel(root, path), max_chars=args.max_chars))
    if args.json_out:
        print(json.dumps([c.as_dict() for c in chunks], indent=2, ensure_ascii=False))
    else:
        print(intake.render_chunks(chunks))
    return 0


def cmd_coverage(args: argparse.Namespace) -> int:
    report = intake.coverage(args.root.resolve())
    print(report.render())
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nJSON report written to {args.json_out}")
    if args.min_coverage is not None and report.ratio * 100 < args.min_coverage:
        print(f"\nCoverage {report.ratio:.0%} is below the required {args.min_coverage:.0f}%")
        return 1
    return 0


def cmd_gen_schema(_args: argparse.Namespace) -> int:
    for path in genschema.write_all_schemas():
        print(f"Wrote {path}")
    print(f"(ArchiMate {oracle.matrix_version()}, {len(oracle.element_types())} element types)")
    return 0


def cmd_pin_oracle(_args: argparse.Namespace) -> int:
    files = sorted(
        p.name
        for p in oracle.ORACLE_DIR.iterdir()
        if p.is_file() and p.suffix in {".xml", ".xsd"}
    )
    lines = [f"{oracle.sha256(oracle.ORACLE_DIR / name)}  {name}" for name in files]
    oracle.CHECKSUMS.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Pinned {len(lines)} oracle file(s) in {oracle.CHECKSUMS}")
    for line in lines:
        print(f"  {line}")
    return 0


def cmd_oracle_info(_args: argparse.Namespace) -> int:
    print(f"ArchiMate version      : {oracle.matrix_version()}")
    print(f"Element types          : {len(oracle.element_types())}")
    print(f"Relationship types     : {len(oracle.relationship_types())}")
    unmapped = oracle.unmapped_layers()
    print(f"Concepts without layer : {', '.join(sorted(unmapped)) if unmapped else 'none'}")
    print("Checksum pins:")
    for result in oracle.verify_checksums():
        status = "OK  " if result.ok else "FAIL"
        print(f"  {status} {result.name}")
    return 0


HANDLERS = {
    "validate": cmd_validate,
    "compile": cmd_compile,
    "validate-facts": cmd_validate_facts,
    "chunk": cmd_chunk,
    "coverage": cmd_coverage,
    "gen-schema": cmd_gen_schema,
    "pin-oracle": cmd_pin_oracle,
    "oracle-info": cmd_oracle_info,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return HANDLERS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
