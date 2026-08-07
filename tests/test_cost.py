"""The cost model: exposure the tool derives, rates the operator supplies.

The load-bearing guarantee is negative -- a repository that configures nothing must see
the debt register it saw before this feature existed. Everything else here is arithmetic
against `--as-of` and honesty about what a total left out.
"""

from datetime import date

import pytest
import yaml
from jsonschema import Draft202012Validator

from easkills import cost, genschema, reports, validate

TODAY = date(2026, 7, 30)

MODEL = """\
elements:
  - id: cap-billing
    type: Capability
    name: Billing
  - id: app-legacy
    type: ApplicationComponent
    name: Legacy Suite
    lastReviewed: 2024-01-01
  - id: app-saas
    type: ApplicationComponent
    name: SaaS Platform
relationships:
  - id: rel-legacy-billing
    type: Realization
    source: app-legacy
    target: cap-billing
  - id: rel-saas-billing
    type: Realization
    source: app-saas
    target: cap-billing
"""


def _root(tmp_path, config: dict | None = None, model: str = MODEL):
    approved = tmp_path / "model" / "approved"
    approved.mkdir(parents=True)
    (approved / "m.yaml").write_text(model, encoding="utf-8", newline="\n")
    if config is not None:
        (tmp_path / "ea.config.yaml").write_text(
            yaml.safe_dump(config, sort_keys=True), encoding="utf-8", newline="\n"
        )
    return tmp_path


# ------------------------------------------------------- the unconfigured guarantee


def test_without_a_cost_model_the_register_is_byte_identical(tmp_path):
    """The whole feature is opt-in, and this is the test that says so.

    Not "an empty cost section", not "zeroes": no key in the JSON and not one character
    in the rendered report. Otherwise every existing diff of a debt run becomes
    unreadable for a feature nobody switched on.
    """
    priced = _root(tmp_path / "priced", {"costModel": {"currency": "EUR", "eolElement": 100}})
    plain = _root(tmp_path / "plain")

    plain_data = reports.debt(plain, today=TODAY)
    assert "cost" not in plain_data
    assert "Cost of exposure" not in reports.render_debt(plain_data)

    # ...and the priced one is the same report *plus* the section, so the guarantee is
    # about the section being additive rather than about the queries changing.
    priced_render = reports.render_debt(reports.debt(priced, today=TODAY))
    assert priced_render.startswith(reports.render_debt(plain_data).rstrip())
    assert "Cost of exposure" in priced_render


def test_the_golden_sets_stay_unpriced(repo_root):
    """Gold is scored, not costed. A cost model there would put a number in every
    harness run's report that no candidate could ever be measured against."""
    for case in ("clinic", "contested"):
        assert "cost" not in reports.debt(repo_root / "eval" / "golden" / case, today=TODAY)


def test_a_currency_alone_is_still_a_cost_model(tmp_path):
    """Rates are all optional. Configuring only the currency prices nothing and reports
    every exposure as unpriced -- which is a legitimate first step, and better than the
    alternative of guessing one rate to make the section appear."""
    data = reports.debt(_root(tmp_path, {"costModel": {"currency": "PLN"}}), today=TODAY)
    assert data["cost"]["total"] == "0"
    assert "unsupportedCapability" not in data["cost"]["unpriced"], "zero exposure is not unpriced, it is absent"
    assert "duplicateRealization" in data["cost"]["unpriced"]


def test_a_cost_model_without_a_currency_prices_nothing(tmp_path):
    """An unlabelled number in a board pack is read in whatever currency the reader
    assumes. The schema requires `currency`; this is what the report does when a
    repository ships one the gate already objected to."""
    data = reports.debt(_root(tmp_path, {"costModel": {"eolElement": 100}}), today=TODAY)
    assert "cost" not in data


# ------------------------------------------------------------------ the arithmetic


def test_exposure_counts_days_past_the_threshold_not_days_since_review(tmp_path):
    """`stalenessDays` is the line; the exposure is what lies past it. Counting from the
    review date would price content that is not yet stale."""
    root = _root(tmp_path, {"stalenessDays": 100, "costModel": {"currency": "EUR", "staleElementDay": 2}})
    line = _line(reports.debt(root, today=TODAY), "staleElementDay")
    expected = (TODAY - date(2024, 1, 1)).days - 100
    assert line["quantity"] == expected
    assert line["items"] == [{"id": "app-legacy", "days": expected}]
    assert line["cost"] == str(2 * expected)


def test_every_exposure_moves_with_as_of_and_never_with_the_wall_clock(tmp_path):
    """The standing rule of the repository, and the one a cost figure makes tempting to
    break: a report someone will paste into a board pack has to be reproducible a month
    later."""
    root = _root(tmp_path, {"stalenessDays": 100, "costModel": {"currency": "EUR", "staleElementDay": 2}})
    earlier = _line(reports.debt(root, today=TODAY), "staleElementDay")["quantity"]
    later = _line(reports.debt(root, today=date(2026, 8, 29)), "staleElementDay")["quantity"]
    assert later - earlier == 30


def test_surplus_realizers_are_counted_beyond_the_first(tmp_path):
    """One capability with two realizers is *one* unit of duplication, not two: the first
    realizer is the architecture, the rest is what rationalization would remove."""
    root = _root(tmp_path, {"costModel": {"currency": "EUR", "duplicateRealization": 1000}})
    line = _line(reports.debt(root, today=TODAY), "duplicateRealization")
    assert line["quantity"] == 1
    assert line["items"] == [{"id": "cap-billing", "surplus": 1}]
    assert line["cost"] == "1000"


def test_money_arithmetic_is_exact(tmp_path):
    """0.1 + 0.2 is the one arithmetic error nobody forgives in a board pack, so rates
    go through Decimal(str(value)) rather than float."""
    root = _root(tmp_path, {"stalenessDays": 100, "costModel": {"currency": "EUR", "staleElementDay": 0.1}})
    line = _line(reports.debt(root, today=TODAY), "staleElementDay")
    assert line["cost"] == str(round(0.1 * line["quantity"], 1)) or "." in line["cost"]
    from decimal import Decimal

    assert Decimal(line["cost"]) == Decimal("0.1") * line["quantity"]


def _line(data, key):
    return next(line for line in data["cost"]["lines"] if line["key"] == key)


# --------------------------------------------------------------------- the honesty


def test_an_unpriced_exposure_is_named_beside_the_total(tmp_path):
    """A partial total that looks complete is worse than no total, because it is the
    number that reaches a slide."""
    root = _root(tmp_path, {"stalenessDays": 100, "costModel": {"currency": "EUR", "staleElementDay": 2}})
    data = reports.debt(root, today=TODAY)
    assert data["cost"]["unpriced"] == ["duplicateRealization"]
    assert not data["cost"]["complete"]
    rendered = reports.render_debt(data)
    assert "Not priced: duplicateRealization" in rendered
    assert "only as complete as its rates" in rendered


def test_an_unreviewable_element_is_named_not_priced_at_zero(tmp_path):
    """"We cannot tell" and "it costs nothing" are different answers. An element with no
    review date carries no element-days, and the report says which elements those are --
    otherwise the figure reads as a clean backlog."""
    root = _root(tmp_path, {"stalenessDays": 100, "costModel": {"currency": "EUR", "staleElementDay": 2}})
    data = reports.debt(root, today=TODAY)
    assert data["cost"]["unmeasured"] == ["app-saas", "cap-billing"]
    assert "Not measurable: app-saas, cap-billing" in reports.render_debt(data)


def test_a_long_unmeasurable_list_is_truncated_but_counted(tmp_path):
    """Naming items is the rule; printing forty of them in a summary line is not. The
    count keeps the truncation from reading as the whole list."""
    elements = "elements:\n" + "".join(
        f"  - id: role-{index}\n    type: BusinessRole\n    name: Role {index}\n" for index in range(9)
    )
    root = _root(tmp_path, {"costModel": {"currency": "EUR", "staleElementDay": 2}}, model=elements)
    rendered = reports.render_debt(reports.debt(root, today=TODAY))
    assert "(+4 more)" in rendered


def test_an_unusable_rate_is_dropped_and_reported_rather_than_coerced(tmp_path):
    """The schema rejects these at the gate. The report still has to survive a config the
    gate already objected to -- and must not price the exposure at whatever the value
    happened to coerce to."""
    currency, rates, problems = cost.rates(
        {"costModel": {"currency": "EUR", "eolElement": "lots", "staleElementDay": -3, "eolElemnt": 10}}
    )
    assert currency == "EUR"
    assert rates == {}
    assert len(problems) == 3
    assert any("not a rate this tool knows how to apply" in p for p in problems)
    assert any("negative rate" in p for p in problems)


def test_the_framing_sentence_is_in_the_report_itself(tmp_path):
    """Not only in the docs. The sentence *is* the feature, and the report is what gets
    pasted somewhere the docs are not."""
    root = _root(tmp_path, {"costModel": {"currency": "EUR", "eolElement": 100}})
    assert (
        "the tool computed the exposure, the operator priced it"
        in reports.render_debt(reports.debt(root, today=TODAY))
    )


# ---------------------------------------------------------------------- the schema


def test_every_rate_key_prices_an_exposure_and_every_exposure_has_a_rate_key():
    """One vocabulary. A rate that prices nothing is dead config; an exposure with no
    rate key can never be costed, and both fail silently -- as a zero in a total."""
    assert set(cost.documented_rate_keys()) == {kind.key for kind in cost.KINDS}
    schema_keys = set(genschema.build_config_schema()["properties"]["costModel"]["properties"]) - {"currency"}
    assert schema_keys == {kind.key for kind in cost.KINDS}


@pytest.mark.parametrize(
    "config, expected",
    [
        ({"costModel": {"eolElement": 100}}, "currency"),
        ({"costModel": {"currency": "EUR", "eolElemnt": 100}}, "eolElemnt"),
        ({"costModel": {"currency": "EUR", "eolElement": -1}}, "-1"),
        ({"costModel": {"currency": "EUR", "eolElement": "lots"}}, "lots"),
        ({"stalenessDay": 30}, "stalenessDay"),
    ],
)
def test_the_config_schema_rejects_what_would_otherwise_fail_silently(config, expected):
    """`stalenessDay` is the whole argument for `additionalProperties: false` here: it
    leaves the documented 365-day default in place, and the repository looks fresh
    because nothing said otherwise."""
    errors = list(Draft202012Validator(genschema.build_config_schema()).iter_errors(config))
    assert errors, f"{config} validated cleanly"
    assert any(expected in error.message for error in errors)


def test_the_shipped_configs_satisfy_their_own_schema(repo_root):
    validator = Draft202012Validator(genschema.build_config_schema())
    checked = 0
    for path in repo_root.glob("**/ea.config.yaml"):
        if "fixtures/broken" in path.as_posix():
            continue  # wrong on purpose; see the SCHEMA002 case in the validator tests
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        assert not list(validator.iter_errors(data)), f"{path} does not satisfy the config schema"
        checked += 1
    assert checked >= 4, "the glob stopped finding the shipped configs"


def test_one_typo_produces_one_finding(tmp_path):
    """`config_number` and the schema both police `quoteMatchThreshold`. Reporting it
    twice trains people to skim the finding list, which is how the other one gets missed.
    """
    (tmp_path / "ea.config.yaml").write_text("quoteMatchThreshold: 90\n", encoding="utf-8", newline="\n")
    (tmp_path / "model" / "approved").mkdir(parents=True)
    report = validate.validate(tmp_path, zone="approved", today=TODAY)
    threshold = [f for f in report.findings if f.locator == "quoteMatchThreshold"]
    assert len(threshold) == 1
    assert "usable maximum" in threshold[0].message, "the hand-written message is the more useful one"
