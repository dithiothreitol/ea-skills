"""`ea-check` runs in a *consuming* repository, so its inputs are someone else's files.

The narrow contract (AD-09): a standard declares how a dependency evidences it, the
check reports lifecycle violations against the element the repository implements, and it
never infers a correspondence nobody declared.
"""

from datetime import date
from pathlib import Path

import pytest

from easkills import check, cli

TODAY = date(2026, 7, 30)


@pytest.fixture(scope="module")
def consumer(repo_root) -> Path:
    return repo_root / "eval" / "fixtures" / "consumer"


@pytest.fixture(scope="module")
def consumer_clean(repo_root) -> Path:
    return repo_root / "eval" / "fixtures" / "consumer-clean"


def _codes(report) -> set[str]:
    return {f.code for f in report.findings}


# ------------------------------------------------------------------------- the rules


def test_retired_standard_in_a_dependency_is_an_error(example_root, consumer):
    """The model knows the lifecycle; the code cannot see it. That is the whole point."""
    report = check.check(example_root, consumer, scope="app-order-portal", today=TODAY)
    assert "CHK002" in _codes(report)
    assert not report.ok


def test_the_same_use_is_information_when_a_dispensation_covers_it(example_root, consumer):
    """`app-erp-core` is covered by disp-onprem-legacy: governance working, not a breach."""
    report = check.check(example_root, consumer, scope="app-erp-core", today=TODAY)
    covered = next(f for f in report.findings if f.code == "CHK004")
    assert "disp-onprem-legacy" in covered.message and "2027-06-30" in covered.message
    assert "CHK002" not in _codes(report)


def test_the_waiver_stops_covering_after_it_expires(example_root, consumer):
    report = check.check(example_root, consumer, scope="app-erp-core", today=date(2027, 7, 15))
    assert "CHK002" in _codes(report), "an expired dispensation must stop excusing the dependency"


def test_deprecated_standard_is_a_warning(broken_root, consumer):
    report = check.check(broken_root, consumer, scope="node-a", today=TODAY)
    assert "CHK003" in _codes(report)


def test_a_governed_dependency_the_model_does_not_record_is_reported(example_root, consumer_clean):
    """Drift the other way: the code follows a standard the model does not know about."""
    report = check.check(example_root, consumer_clean, scope="app-order-portal", today=TODAY)
    assert "CHK006" in _codes(report)
    assert report.ok and not report.warnings, "drift is information, not a build failure"


def test_a_claimed_standard_nothing_evidences_is_a_warning(example_root, consumer_clean):
    report = check.check(example_root, consumer_clean, scope="app-erp-core", today=TODAY)
    assert "CHK005" in _codes(report)


def test_an_unreadable_manifest_is_an_error(example_root, consumer):
    """A manifest that will not parse cannot be declared compliant."""
    report = check.check(example_root, consumer, scope="app-erp-core", today=TODAY)
    unreadable = next(f for f in report.findings if f.code == "CHK000")
    assert unreadable.file == "broken/package.json"


def test_an_unknown_scope_is_an_error(example_root, consumer):
    """Without a scope there is nothing to check against, so no compliance is claimed."""
    report = check.check(example_root, consumer, scope="no-such-system", today=TODAY)
    assert "CHK001" in _codes(report) and not report.ok
    # Manifest reading still reports what it could not read, but no lifecycle verdict
    # is reached -- silence here would read as "compliant".
    assert not {"CHK002", "CHK003", "CHK004", "CHK005", "CHK006"} & _codes(report)


def test_a_repository_with_no_manifests_proves_nothing_and_says_so(example_root, tmp_path):
    report = check.check(example_root, tmp_path, scope="app-erp-core", today=TODAY)
    assert "CHK007" in _codes(report)


# --------------------------------------------------------------------- reading inputs


def test_installed_dependencies_are_not_declared_dependencies(consumer):
    """`node_modules/` is what was installed, not what this repository declares."""
    dependencies, _findings, manifests = check.read_dependencies(consumer)
    assert manifests == 3, "node_modules/pg/package.json must not be read"
    assert all("node_modules" not in d.file for d in dependencies)


def test_dependency_names_are_compared_the_way_each_ecosystem_does():
    assert check.normalize("Psycopg2_Binary", "requirements.txt") == "psycopg2-binary"
    assert check.normalize("org.PostgreSQL:PostgreSQL", "pom.xml") == "org.postgresql:postgresql"
    assert check.normalize("Express", "package.json") == "Express", "npm names are case-sensitive"


def test_every_manifest_kind_can_be_read(tmp_path):
    (tmp_path / "package.json").write_text('{"dependencies": {"pg": "^8.0.0"}}', encoding="utf-8")
    (tmp_path / "requirements.txt").write_text(
        "# comment\npsycopg2-binary==2.9.9\n-r other.txt\nflask[async] >= 3.0\n", encoding="utf-8"
    )
    (tmp_path / "pom.xml").write_text(
        "<project xmlns='http://maven.apache.org/POM/4.0.0'><dependencies><dependency>"
        "<groupId>org.postgresql</groupId><artifactId>postgresql</artifactId>"
        "<version>42.7.1</version></dependency></dependencies></project>",
        encoding="utf-8",
    )
    dependencies, findings, manifests = check.read_dependencies(tmp_path)
    assert manifests == 3 and not findings
    found = {(d.manifest, d.name) for d in dependencies}
    assert found == {
        ("package.json", "pg"),
        ("requirements.txt", "psycopg2-binary"),
        ("requirements.txt", "flask"),
        ("pom.xml", "org.postgresql:postgresql"),
    }, "includes must be skipped and extras stripped"


def test_a_standard_without_detect_rules_stays_silent(example_root, consumer_clean):
    """`std-cloud-hosting` has no rules: not checkable here, and it does not pretend to be."""
    report = check.check(example_root, consumer_clean, scope="app-order-portal", today=TODAY)
    assert all("std-cloud-hosting" not in f.message for f in report.findings)


# ------------------------------------------------------------------------------- CLI


def test_cli_exit_codes(example_root, consumer, consumer_clean, capsys):
    assert cli.main([
        "check", "--root", str(example_root), "--repo", str(consumer_clean),
        "--scope", "app-order-portal", "--as-of", "2026-07-30",
    ]) == 0
    assert cli.main([
        "check", "--root", str(example_root), "--repo", str(consumer),
        "--scope", "app-erp-core", "--as-of", "2026-07-30",
    ]) == 1
    capsys.readouterr()


def test_cli_strict_fails_on_warnings(example_root, consumer_clean, capsys):
    argv = [
        "check", "--root", str(example_root), "--repo", str(consumer_clean),
        "--scope", "app-erp-core", "--as-of", "2026-07-30",
    ]
    assert cli.main(argv) == 0
    assert cli.main(argv + ["--strict"]) == 1
    capsys.readouterr()
