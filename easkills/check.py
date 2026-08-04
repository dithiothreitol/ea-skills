"""Deterministic EA-compliance lint *inside a consuming repository* (AD-09).

This is the narrow start the blueprint asked for, and the narrowness is the design:

* **No integration manifest.** Full model-element ↔ code-artifact correspondence is a
  CMDB-class problem and, worse, a convention every consuming team would have to adopt.
  Here a consuming repository declares nothing: its CI passes ``--scope <element-id>``,
  one argument, and everything else is read from the EA repository.
* **Detection is declared by the standard, not guessed.** A SIB entry may carry
  ``detect:`` rules naming the dependency that evidences it (``pg`` in a
  ``package.json``, ``org.postgresql:postgresql`` in a ``pom.xml``). A standard with no
  rules is simply not checkable here, and says so by staying silent -- the tooling never
  infers that a library "is" a standard.
* **Version ranges are deliberately absent.** Matching is by dependency name; the
  observed version is reported, never interpreted. Range logic would need a semver
  dependency and would produce confident answers about questions it cannot settle.

What it catches is the thing the model already knows and the code cannot see: the
lifecycle of the standards a system is built on, and whether an exception was filed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from lxml import etree

from . import dsl, govern, ui
from .validate import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING, Finding

MANIFEST_KINDS = ("package.json", "pom.xml", "requirements.txt")

# Directories that hold *installed* or built code rather than declared dependencies.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "site-packages",
        "target",
        "venv",
    }
)

_REQUIREMENT_RE = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*(?:\[[^\]]*\])?\s*(.*)$")


@dataclass(frozen=True)
class Dependency:
    """One declared dependency, with the manifest that declared it."""

    name: str
    version: str
    manifest: str  # one of MANIFEST_KINDS
    file: str  # repository-relative path


@dataclass
class CheckReport:
    ea_root: Path
    repo: Path
    scope: str
    findings: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == SEVERITY_WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "eaRoot": str(self.ea_root),
            "repo": str(self.repo),
            "scope": self.scope,
            "ok": self.ok,
            "counts": self.counts,
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "info": sum(1 for f in self.findings if f.severity == SEVERITY_INFO),
            },
            "findings": [f.as_dict() for f in self.findings],
        }

    def render(self) -> str:
        lines = [
            ui.bold(f"EA compliance check of {self.repo}"),
            ui.dim(
                f"scope '{self.scope}' in the approved model at {self.ea_root}; "
                f"{self.counts.get('manifests', 0)} manifest(s), "
                f"{self.counts.get('dependencies', 0)} declared dependencies, "
                f"{self.counts.get('governed', 0)} governed by a standard"
            ),
            "",
        ]
        if not self.findings:
            lines.append(ui.dim("No findings."))
        else:
            for finding in self.findings:
                lines.append(finding.render())
        lines += ["", ui.verdict(self.ok, len(self.errors), len(self.warnings))]
        return "\n".join(lines)


def _rel(repo: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def normalize(name: str, manifest: str) -> str:
    """Compare dependency names the way each ecosystem does."""
    if manifest == "requirements.txt":  # PEP 503-ish
        return re.sub(r"[-_.]+", "-", name).strip().lower()
    if manifest == "pom.xml":
        return name.strip().lower()
    return name.strip()  # npm names are case-sensitive by convention


def _package_json(path: Path, repo: Path) -> tuple[list[Dependency], str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        return [], str(exc)
    if not isinstance(data, dict):
        return [], "top level of package.json must be an object"
    found: list[Dependency] = []
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        for name, version in sorted(block.items()):
            found.append(
                Dependency(str(name), str(version), "package.json", _rel(repo, path))
            )
    return found, ""


def _requirements_txt(path: Path, repo: Path) -> tuple[list[Dependency], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return [], str(exc)
    found: list[Dependency] = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):  # -r includes, -e editables: not declarations
            continue
        match = _REQUIREMENT_RE.match(line)
        if match:
            found.append(
                Dependency(match.group(1), match.group(2).strip(), "requirements.txt", _rel(repo, path))
            )
    return found, ""


def _pom_xml(path: Path, repo: Path) -> tuple[list[Dependency], str]:
    try:
        root = etree.parse(str(path)).getroot()
    except (etree.XMLSyntaxError, OSError) as exc:
        return [], str(exc)
    found: list[Dependency] = []
    # Namespace-agnostic: POMs declare the Maven namespace, generated ones sometimes do not.
    for node in root.iter():
        if etree.QName(node).localname != "dependency":
            continue
        parts = {etree.QName(child).localname: (child.text or "").strip() for child in node}
        group, artifact = parts.get("groupId", ""), parts.get("artifactId", "")
        if group and artifact:
            found.append(
                Dependency(f"{group}:{artifact}", parts.get("version", ""), "pom.xml", _rel(repo, path))
            )
    return found, ""


_READERS = {
    "package.json": _package_json,
    "pom.xml": _pom_xml,
    "requirements.txt": _requirements_txt,
}


def read_dependencies(repo: Path) -> tuple[list[Dependency], list[Finding], int]:
    """Every declared dependency in the repository, plus findings for what would not read."""
    dependencies: list[Dependency] = []
    findings: list[Finding] = []
    manifests = 0
    candidates = sorted(
        path
        for path in repo.rglob("*")
        if path.is_file()
        and path.name in MANIFEST_KINDS
        and not (SKIP_DIRS & set(path.relative_to(repo).parts))
    )
    for path in candidates:
        manifests += 1
        found, problem = _READERS[path.name](path, repo)
        if problem:
            findings.append(
                Finding(
                    "CHK000",
                    SEVERITY_ERROR,
                    f"cannot read manifest: {problem} -- an unreadable manifest cannot be "
                    "declared compliant, so the check refuses rather than skipping it",
                    file=_rel(repo, path),
                )
            )
            continue
        dependencies.extend(found)
    return dependencies, findings, manifests


def check(ea_root: Path, repo: Path, scope: str, today: date | None = None) -> CheckReport:
    """Check one consuming repository against the standards its EA element claims."""
    today = today or date.today()
    model, _documents, _config = dsl.load(ea_root, "approved")
    governance = govern.load(ea_root)

    dependencies, findings, manifests = read_dependencies(repo)
    report = CheckReport(ea_root=ea_root, repo=repo, scope=scope)

    element = model.elements.get(scope)
    if element is None:
        findings.append(
            Finding(
                "CHK001",
                SEVERITY_ERROR,
                f"scope '{scope}' is not an element in the approved model at {ea_root} -- "
                "check the id, or model this system before governing it",
                concept=scope,
            )
        )
        report.findings = findings
        report.counts = {"manifests": manifests, "dependencies": len(dependencies), "governed": 0}
        return report

    if not manifests:
        findings.append(
            Finding(
                "CHK007",
                SEVERITY_WARNING,
                f"no dependency manifests ({', '.join(MANIFEST_KINDS)}) found in {repo} -- "
                "the check ran but proved nothing about this repository",
                concept=scope,
            )
        )

    claimed = set(element.standards)
    governed: set[tuple[str, str]] = set()  # (standard id, dependency name)

    for dependency in sorted(dependencies, key=lambda d: (d.file, d.manifest, d.name)):
        for standard in sorted(governance.standards.values(), key=lambda s: s.id):
            if not _detects(standard, dependency):
                continue
            governed.add((standard.id, dependency.name))
            where = f"{dependency.name} {dependency.version}".strip()
            waiver = governance.covering(scope, standard.id, today)
            if standard.lifecycle == "retired" and waiver is None:
                findings.append(
                    Finding(
                        "CHK002",
                        SEVERITY_ERROR,
                        f"'{where}' implements retired standard '{standard.id}'"
                        + (f" (successor: {standard.successor})" if standard.successor else "")
                        + " -- migrate, or file a time-bounded dispensation in the EA repository",
                        file=dependency.file,
                        concept=scope,
                    )
                )
            elif standard.lifecycle in {"retired", "deprecated"} and waiver is not None:
                findings.append(
                    Finding(
                        "CHK004",
                        SEVERITY_INFO,
                        f"'{where}' implements {standard.lifecycle} standard '{standard.id}', "
                        f"covered by dispensation '{waiver.id}' until {waiver.expires} -- "
                        "after that date this becomes an error",
                        file=dependency.file,
                        concept=scope,
                    )
                )
            elif standard.lifecycle == "deprecated":
                findings.append(
                    Finding(
                        "CHK003",
                        SEVERITY_WARNING,
                        f"'{where}' implements deprecated standard '{standard.id}'"
                        + (f" -- plan the migration to '{standard.successor}'" if standard.successor else ""),
                        file=dependency.file,
                        concept=scope,
                    )
                )
            elif standard.id not in claimed:
                findings.append(
                    Finding(
                        "CHK006",
                        SEVERITY_INFO,
                        f"'{where}' implements standard '{standard.id}', which the model does not "
                        f"record for '{scope}' -- add it to the element's 'standards' or explain why",
                        file=dependency.file,
                        concept=scope,
                    )
                )

    detected_standards = {standard_id for standard_id, _ in governed}
    for standard_id in sorted(claimed):
        standard = governance.standards.get(standard_id)
        if standard is None or not _detect_rules(standard):
            continue  # unknown standards are the model gate's business (STD001); undetectable ones stay silent
        if standard_id not in detected_standards and manifests:
            findings.append(
                Finding(
                    "CHK005",
                    SEVERITY_WARNING,
                    f"the model says '{scope}' follows '{standard_id}', but nothing in this "
                    "repository evidences it -- the claim is unverified here",
                    concept=scope,
                )
            )

    severity_rank = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}
    findings.sort(key=lambda f: (severity_rank.get(f.severity, 3), f.code, f.file, f.concept))
    report.findings = findings
    report.counts = {
        "manifests": manifests,
        "dependencies": len(dependencies),
        "governed": len(governed),
    }
    return report


def _detect_rules(standard: govern.Standard) -> list[dict[str, str]]:
    return standard.detect


def _detects(standard: govern.Standard, dependency: Dependency) -> bool:
    for rule in _detect_rules(standard):
        if rule.get("manifest") != dependency.manifest:
            continue
        declared = normalize(str(rule.get("dependency", "")), dependency.manifest)
        if declared and declared == normalize(dependency.name, dependency.manifest):
            return True
    return False
