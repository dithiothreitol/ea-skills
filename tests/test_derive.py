"""ArchiMate derivation rules DR1-DR8, one test per rule plus the restrictions.

The rules are quoted from Appendix B.2 of the specification; each test builds the minimal
model the rule talks about and asserts the derived edge appears with the right type and
direction. Direction is the whole game here -- DR3/DR5/DR7 move an endpoint one way along
a structural chain and DR4/DR6 move it the other, and a transcription slip would silently
invent relationships nobody's model implies.
"""

from pathlib import Path

import pytest

from easkills import derive, dsl, oracle, score

REPO_ROOT = Path(__file__).resolve().parents[1]


def model(*, elements: dict[str, str], relationships: list[tuple[str, str, str]]) -> dsl.Model:
    """A throwaway in-memory model: ``{id: type}`` and ``(type, source, target)`` edges."""
    built = dsl.Model(root=Path("."), zone="approved", config={})
    for element_id, element_type in elements.items():
        built.elements[element_id] = dsl.Element(
            id=element_id, type=element_type, name=element_id.replace("-", " ").title()
        )
    for index, (relationship_type, source, target) in enumerate(relationships):
        built.relationships[f"rel-{index}"] = dsl.Relationship(
            id=f"rel-{index}", type=relationship_type, name="", source=source, target=target
        )
    return built


def derived(built: dsl.Model, **kwargs) -> dict[derive.Edge, derive.Derivation]:
    return {
        edge: derivation
        for edge, derivation in derive.closure(built, **kwargs).items()
        if derivation.is_derived
    }


# ------------------------------------------------------------------ one test per rule


def test_dr1_specialization_is_transitive():
    built = model(
        elements={"a": "ApplicationComponent", "b": "ApplicationComponent", "c": "ApplicationComponent"},
        relationships=[("Specialization", "a", "b"), ("Specialization", "b", "c")],
    )
    result = derived(built)
    assert derive.Edge("Specialization", "a", "c") in result
    assert result[derive.Edge("Specialization", "a", "c")].rules == ("DR1",)


def test_dr2_a_structural_chain_becomes_its_weakest_link():
    """Realization (weakest), Assignment, Aggregation, Composition (strongest)."""
    built = model(
        elements={"a": "ApplicationComponent", "b": "ApplicationComponent", "s": "ApplicationService"},
        relationships=[("Composition", "a", "b"), ("Realization", "b", "s")],
    )
    result = derived(built)
    assert derive.Edge("Realization", "a", "s") in result, "the weaker of composition and realization"
    assert derive.Edge("Composition", "a", "s") not in result


def test_dr2_prefers_the_weakest_over_both_inputs():
    built = model(
        elements={"a": "ApplicationComponent", "b": "ApplicationComponent", "c": "ApplicationComponent"},
        relationships=[("Composition", "a", "b"), ("Aggregation", "b", "c")],
    )
    result = derived(built)
    assert derive.Edge("Aggregation", "a", "c") in result
    assert derive.Edge("Composition", "a", "c") not in result


def test_dr3_a_dependency_source_moves_back_along_the_structural_chain():
    built = model(
        elements={"a": "ApplicationComponent", "b": "ApplicationComponent", "p": "BusinessProcess"},
        relationships=[("Composition", "a", "b"), ("Serving", "b", "p")],
    )
    assert derive.Edge("Serving", "a", "p") in derived(built)


def test_dr4_a_dependency_target_moves_back_along_the_structural_chain():
    """The measured case, kept as a named regression.

    A run wrote `SchedPro --Serving--> Weekend Run Planning` and
    `Dispatch --Assignment--> Weekend Run Planning` where gold wrote
    `SchedPro --Serving--> Dispatch`. Every endpoint matched, no relationship did, and the
    category read 0% -- because this rule was missing, not because the run was wrong.
    """
    built = model(
        elements={
            "app-schedpro": "ApplicationComponent",
            "role-dispatch": "BusinessRole",
            "proc-weekend": "BusinessProcess",
        },
        relationships=[
            ("Serving", "app-schedpro", "proc-weekend"),
            ("Assignment", "role-dispatch", "proc-weekend"),
        ],
    )
    result = derived(built)
    edge = derive.Edge("Serving", "app-schedpro", "role-dispatch")
    assert edge in result, "gold's edge is implied by the candidate's two"
    assert result[edge].rules == ("DR4",)
    assert result[edge].via == ("proc-weekend",)
    assert derive.describe(built, result[edge]) == "derived DR4 via Proc Weekend"
    # And nothing in the opposite direction was invented.
    assert derive.Edge("Serving", "role-dispatch", "app-schedpro") not in result


def test_dr5_a_dynamic_source_moves_back_along_the_structural_chain():
    built = model(
        elements={"a": "ApplicationComponent", "b": "ApplicationComponent", "c": "ApplicationComponent"},
        relationships=[("Composition", "a", "b"), ("Triggering", "b", "c")],
    )
    assert derive.Edge("Triggering", "a", "c") in derived(built)


def test_dr6_a_flow_target_moves_back_along_the_structural_chain():
    built = model(
        elements={"a": "ApplicationComponent", "b": "ApplicationComponent", "c": "ApplicationComponent"},
        relationships=[("Composition", "a", "b"), ("Flow", "c", "b")],
    )
    result = derived(built)
    assert derive.Edge("Flow", "c", "a") in result
    assert result[derive.Edge("Flow", "c", "a")].rules == ("DR6",)


def test_dr7_a_triggering_target_moves_forward_into_the_part():
    """DR7 runs the *other* way from DR4/DR6: into the parts, per Example 47."""
    built = model(
        elements={"a": "BusinessProcess", "b": "BusinessProcess", "c": "BusinessProcess"},
        relationships=[("Triggering", "a", "b"), ("Composition", "b", "c")],
    )
    result = derived(built)
    edge = derive.Edge("Triggering", "a", "c")
    assert edge in result and "DR7" in result[edge].rules


def test_dr8_triggering_is_transitive():
    built = model(
        elements={"a": "BusinessProcess", "b": "BusinessProcess", "c": "BusinessProcess"},
        relationships=[("Triggering", "a", "b"), ("Triggering", "b", "c")],
    )
    result = derived(built)
    edge = derive.Edge("Triggering", "a", "c")
    assert edge in result and result[edge].rules == ("DR8",)


def test_rules_combine_across_a_longer_chain():
    """B.2.3: "these rules may be combined with the derivation rule for structural
    relations (DR2)", so a two-hop structural chain still carries the dependency."""
    built = model(
        elements={
            "a": "ApplicationComponent",
            "b": "ApplicationComponent",
            "c": "ApplicationComponent",
            "p": "BusinessProcess",
        },
        relationships=[
            ("Composition", "a", "b"),
            ("Composition", "b", "c"),
            ("Serving", "c", "p"),
        ],
    )
    result = derived(built)
    edge = derive.Edge("Serving", "a", "p")
    assert edge in result
    assert result[edge].depth == 3 and set(result[edge].via) == {"b", "c"}


# ----------------------------------------------------------------- what is not derived


def test_nothing_is_derived_from_a_single_relationship():
    built = model(
        elements={"a": "ApplicationComponent", "p": "BusinessProcess"},
        relationships=[("Serving", "a", "p")],
    )
    assert derived(built) == {}
    assert len(derive.closure(built)) == 1, "the stated edge is still in the closure"


def test_a_stated_edge_is_not_reported_as_derived():
    built = model(
        elements={"a": "ApplicationComponent", "b": "ApplicationComponent", "p": "BusinessProcess"},
        relationships=[("Composition", "a", "b"), ("Serving", "b", "p"), ("Serving", "a", "p")],
    )
    closure = derive.closure(built)
    assert not closure[derive.Edge("Serving", "a", "p")].is_derived
    assert derive.describe(built, closure[derive.Edge("Serving", "a", "p")]) == "stated directly"


def test_a_third_domain_may_not_sit_in_the_middle():
    """B.4: no derivation "through an intermediary c in a domain C distinct from both".

    The derived edge here is legal by the matrix -- association between an application
    component and a business process -- so this isolates the path restriction: the
    capability in the middle is Strategy, and both endpoints are Core.
    """
    built = model(
        elements={
            "app": "ApplicationComponent",
            "cap": "Capability",
            "proc": "BusinessProcess",
        },
        relationships=[("Realization", "app", "cap"), ("Association", "cap", "proc")],
    )
    assert "Association" in oracle.allowed_relationships("ApplicationComponent", "BusinessProcess")
    assert derive.Edge("Association", "app", "proc") not in derived(built)


def test_grouping_and_junction_are_left_alone():
    """B.1: "these derivation rules do not work on relationships with grouping"."""
    built = model(
        elements={"g": "Grouping", "b": "ApplicationComponent", "p": "BusinessProcess"},
        relationships=[("Composition", "g", "b"), ("Serving", "b", "p")],
    )
    assert derive.Edge("Serving", "g", "p") not in derived(built)


def test_no_self_loops_are_derived():
    built = model(
        elements={"a": "ApplicationComponent", "b": "ApplicationComponent"},
        relationships=[("Composition", "a", "b"), ("Serving", "b", "a")],
    )
    assert all(edge.source != edge.target for edge in derive.closure(built))


def test_depth_is_bounded():
    built = model(
        elements={f"e{i}": "BusinessProcess" for i in range(6)},
        relationships=[("Triggering", f"e{i}", f"e{i + 1}") for i in range(5)],
    )
    assert all(d.depth <= 2 for d in derive.closure(built, max_depth=2).values())
    assert derive.Edge("Triggering", "e0", "e2") in derived(built, max_depth=2)
    assert derive.Edge("Triggering", "e0", "e3") not in derived(built, max_depth=2)
    assert derive.Edge("Triggering", "e0", "e3") in derived(built, max_depth=3)


# ------------------------------------------------------- properties over the real models


@pytest.mark.parametrize("case", ["eval/golden/clinic", "eval/golden/contested", "eval/example"])
def test_every_derived_edge_is_a_legal_relationship(case):
    """The matrix filter is where the rest of B.4 lives, so it must never be bypassed."""
    built, _documents, _config = dsl.load(REPO_ROOT / case, "approved")
    for edge, derivation in derive.closure(built).items():
        source = built.elements[edge.source]
        target = built.elements[edge.target]
        assert edge.type in oracle.allowed_relationships(source.type, target.type), (
            f"{derivation.rules} produced an illegal {edge}"
        )


def test_the_closure_is_deterministic():
    built, _documents, _config = dsl.load(REPO_ROOT / "eval" / "example", "approved")
    first = {edge: (d.rules, d.via) for edge, d in derive.closure(built).items()}
    second = {edge: (d.rules, d.via) for edge, d in derive.closure(built).items()}
    assert first == second


def test_derivation_never_changes_a_perfect_self_score():
    """A model implies edges it does not state; that must not become extra credit."""
    for case in ("eval/golden/clinic", "eval/golden/contested", "eval/example"):
        report = score.score(REPO_ROOT / case, REPO_ROOT / case)
        assert report.min_f1 == 1.0, case
        assert report.categories["relationships"].partial == 0, case
