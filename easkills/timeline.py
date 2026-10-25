"""KPI snapshots and the trend across them.

``kpi`` answers "how is the model today"; nobody could answer "is it getting better",
because yesterday's answer was printed and gone. A snapshot is that answer kept: the
exact ``kpi --json`` output on one date, committed under ``governance-log/metrics/`` and
named by the date, so the series is reviewable in the same diffs as the model it
measures (D9).

Three rules. A snapshot is a **record**: taking one again on the same date with an
unchanged model is a no-op, and with a changed model it is refused -- rewriting what the
estate looked like on a past date is not a measurement. The date is always an explicit
``--as-of``, never the wall clock, because the file name *is* the date. And ``trend``
reads only what was committed: it never recomputes a past value from today's model,
which would silently answer a different question.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from . import genschema, ui

METRICS_DIR = Path("governance-log") / "metrics"


class TimelineError(RuntimeError):
    pass


@dataclass(frozen=True)
class Metric:
    """One line of the trend: where it sits in a snapshot, and which way is better.

    ``better`` is ``up``, ``down`` or empty. Empty is a statement, not an omission: the
    model growing is neither good nor bad, and an open dispensation is a legitimate
    record -- calling a rise in either a regression would push people to delete things to
    clear a report, the incentive the register rules (``REG003``) were written to avoid.
    """

    key: str
    label: str
    path: tuple[str, ...]
    better: str = ""
    share: bool = False
    counted: bool = False  # the snapshot holds a list of ids; the trend counts them


METRICS: tuple[Metric, ...] = (
    Metric("elements", "Elements", ("size", "elements")),
    Metric("relationships", "Relationships", ("size", "relationships")),
    Metric("facts", "Facts", ("size", "facts")),
    Metric("evidenced", "Evidenced", ("evidence", "evidencedShare"), "up", share=True),
    Metric("assumed", "Assumptions", ("evidence", "assumed"), "down"),
    Metric("owned", "Owned", ("governance", "ownedShare"), "up", share=True),
    Metric("stale", "Stale or unreviewed", ("governance", "staleShare"), "down", share=True),
    Metric("dispensations", "Open dispensations", ("governance", "openDispensations")),
    Metric("time-classified", "TIME-classified", ("portfolio", "timeClassifiedShare"), "up", share=True),
    Metric("obsolescence", "Obsolescence exposure", ("portfolio", "obsolescenceExposure"), "down", counted=True),
    Metric("unsupported", "Unsupported capabilities", ("capabilities", "unsupported"), "down", counted=True),
    Metric("orphans", "Orphans", ("quality", "orphans"), "down", counted=True),
    Metric("unheld", "Unheld concerns", ("documentation", "unheldConcerns"), "down", counted=True),
    Metric("unframed", "Unframed concerns", ("documentation", "unframedConcerns"), "down", counted=True),
    Metric("open-requests", "Open requests", ("service", "open")),
    Metric("sla-breaches", "SLA breaches", ("service", "slaBreaches"), "down", counted=True),
    Metric("open-questions", "Open questions", ("questions", "open")),
    Metric("oldest-question", "Oldest open question (days)", ("questions", "oldestOpenDays"), "down"),
)


def snapshot_path(root: Path, as_of: str) -> Path:
    return root / METRICS_DIR / f"{as_of}.json"


def serialise(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_snapshot(root: Path, data: dict[str, Any]) -> tuple[Path, bool]:
    """Write ``data`` as the snapshot for its ``asOf``. Returns (path, written).

    ``written`` is False when an identical snapshot is already there. A *different* one
    for the same date is refused: the record of a past date is not overwritten by a
    re-run against a model that has since changed.
    """
    path = snapshot_path(root, data["asOf"])
    text = serialise(data)
    if path.exists():
        if path.read_text(encoding="utf-8") == text:
            return path, False
        raise TimelineError(
            f"{path.relative_to(root).as_posix()} already records {data['asOf']} with different values -- "
            "a snapshot is a record of that date, not a cache. If the record itself is wrong, "
            "delete it deliberately (the commit says why) and take it again"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path, True


def load_snapshots(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Every readable snapshot in date order, and a named error for every unreadable one."""
    directory = root / METRICS_DIR
    if not directory.is_dir():
        return [], []
    validator = Draft202012Validator(genschema.load_metrics_schema())
    snapshots: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in sorted(p for p in directory.iterdir() if p.is_file() and p.suffix == ".json"):
        relative = path.relative_to(root).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append({"file": relative, "message": f"not readable as JSON: {exc}"})
            continue
        problems = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
        if problems:
            first = problems[0]
            where = "/".join(str(part) for part in first.absolute_path) or "(top level)"
            errors.append({"file": relative, "message": f"not a KPI snapshot at {where}: {first.message}"})
            continue
        if data["asOf"] != path.stem:
            errors.append(
                {
                    "file": relative,
                    "message": f"named {path.stem} but records asOf {data['asOf']} -- the name is the date",
                }
            )
            continue
        snapshots.append(data)
    snapshots.sort(key=lambda d: d["asOf"])
    return snapshots, errors


def value(snapshot: dict[str, Any], metric: Metric) -> float | int | None:
    current: Any = snapshot
    for part in metric.path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if metric.counted:
        return len(current) if isinstance(current, list) else None
    return current if isinstance(current, (int, float)) and not isinstance(current, bool) else None


def _direction(metric: Metric, before: float | int | None, after: float | int | None) -> str:
    if not metric.better or before is None or after is None or before == after:
        return ""
    rose = after > before
    return "improved" if rose == (metric.better == "up") else "regressed"


def trend(root: Path, last: int | None = None) -> dict[str, Any]:
    snapshots, errors = load_snapshots(root)
    shown = snapshots[-last:] if last else snapshots
    rows: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    for metric in METRICS:
        values = [value(s, metric) for s in snapshots]
        if all(v is None for v in values):
            continue  # a section this repository never had (questions, for most)
        rows.append(
            {
                "key": metric.key,
                "label": metric.label,
                "better": metric.better,
                "share": metric.share,
                "values": values[-len(shown):] if shown else [],
            }
        )
        if len(snapshots) >= 2:
            before, after = values[-2], values[-1]
            verdict = _direction(metric, before, after)
            if verdict:
                (regressions if verdict == "regressed" else improvements).append(
                    {"key": metric.key, "label": metric.label, "from": before, "to": after, "share": metric.share}
                )
    return {
        "snapshots": [s["asOf"] for s in shown],
        "total": len(snapshots),
        "previous": snapshots[-2]["asOf"] if len(snapshots) >= 2 else None,
        "latest": snapshots[-1]["asOf"] if snapshots else None,
        "metrics": rows,
        "regressions": regressions,
        "improvements": improvements,
        "errors": errors,
    }


def _cell(raw: float | int | None, share: bool) -> str:
    if raw is None:
        return "—"
    if share:
        return f"{raw:.0%}"
    return f"{raw:g}" if isinstance(raw, float) else str(raw)


def render_trend(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for error in data["errors"]:
        lines.append(f"{ui.red(ui.bold('ERROR'))}   {error['file']}: {error['message']}")
    if not data["total"]:
        if lines:
            lines.append("")
        lines.append(
            f"No readable KPI snapshot under {METRICS_DIR.as_posix()}/ -- take one with "
            "`kpi --snapshot --as-of <date>` and commit it."
        )
        return "\n".join(lines)
    if lines:
        lines.append("")
    hidden = data["total"] - len(data["snapshots"])
    lines.append(
        ui.bold(f"KPI trend over {data['total']} snapshot(s)")
        + (ui.dim(f" -- the last {len(data['snapshots'])} shown") if hidden else "")
    )
    lines.append("")
    width = max(len(row["label"]) for row in data["metrics"]) + 2
    header = " " * width + "".join(f"{day:>12}" for day in data["snapshots"])
    lines.append(ui.dim(header))
    for row in data["metrics"]:
        cells = "".join(f"{_cell(v, row['share']):>12}" for v in row["values"])
        lines.append(f"{row['label']:<{width}}{cells}")
    lines.append("")
    if data["total"] < 2:
        lines.append("One snapshot is a point, not a trend; the next one gives this report something to compare.")
        return "\n".join(lines)
    span = f"{data['previous']} {ui.arrow()} {data['latest']}"
    if data["regressions"]:
        lines.append(ui.yellow(f"Regressed since the previous snapshot ({span}):"))
        for item in data["regressions"]:
            lines.append(f"  {item['label']}: {_cell(item['from'], item['share'])} {ui.arrow()} {_cell(item['to'], item['share'])}")
    else:
        lines.append(f"{ui.green(ui.check())} Nothing regressed since the previous snapshot ({span}).")
    if data["improvements"]:
        lines.append("Improved: " + ", ".join(
            f"{item['label']} {_cell(item['from'], item['share'])} {ui.arrow()} {_cell(item['to'], item['share'])}"
            for item in data["improvements"]
        ))
    return "\n".join(lines)
