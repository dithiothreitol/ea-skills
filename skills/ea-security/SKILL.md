---
name: ea-security
description: Work the security architecture in the existing model - classify data, mark exposure and trust zones, find unguarded paths from the public internet, propose threat assessments for trust-boundary crossings, anchor high-rated systems to a control framework (NIST SP 800-53, SP 800-207, CSF), and check SBOMs against security standards. Use for security architecture reviews, threat modelling, attack-surface or "what could an attacker reach" questions, data classification, zero-trust or control-coverage questions, and SEC001-SEC003 or ALN009 findings.
argument-hint: "[element-id or as-of YYYY-MM-DD]"
allowed-tools:
  - Bash(easkills align *)
  - Bash(easkills check *)
  - Bash(easkills exposure *)
  - Bash(easkills propose *)
  - Bash(easkills validate *)
  - Bash(python -m easkills align *)
  - Bash(python -m easkills check *)
  - Bash(python -m easkills exposure *)
  - Bash(python -m easkills propose *)
  - Bash(python -m easkills validate *)
---

# Security architecture in the existing model

There is no security layer here and none is missing: ArchiMate has none on purpose, and
everything a security architecture consists of already has a governed home --
obligations in the motivation layer, standards in the SIB, accepted risk as dispensations,
control frameworks as reference packs. This skill adds the vocabulary that makes those
homes readable by the tooling, and the three questions it answers.

```bash
easkills validate --root <repo>                                  # SEC001-SEC003 among the rest
easkills exposure --root <repo>                                  # reach from every public element
easkills propose --root <repo> --from threats --as-of <date>     # an assessment per boundary crossing
easkills align --root <repo> --reference nist-sp-800-53-r5       # control gaps, and ALN009
easkills check --root <ea-repo> --repo . --scope <id> --sbom bom.cdx.json
```

## Non-negotiables

* **A classification is a fact about the element, recorded where it lives.** Set
  `dataClassification`, `personalData`, the three `sec*` ratings, `exposure` and
  `trustZone` from evidence -- a data inventory, a DPIA, the owner's word recorded as a
  fact -- never because a system "sounds" sensitive. A guessed rating moves every report
  downstream and nobody can tell it from a real one.
* **Never lower a rating or drop an exposure to clear a finding.** The finding is true.
  The honest exits are a governing obligation, a claimed standard, or accepted risk as a
  dispensation with a named grantor and an expiry.
* **The tooling finds the paths; it does not judge the threats.** `exposure` and
  `propose --from threats` are mechanical. Which STRIDE category applies, and what treats
  it, is the assessment -- written by a person, or by you as a proposal a person signs.
* **Never transcribe a licensed control catalogue** (ISO/IEC 27001 Annex A, CIS
  Controls, PCI DSS). NIST SP 800-53 and SP 800-207 ship in `references/` because they are
  public domain; a licensed catalogue is exported from the organisation's own copy.

## The vocabulary

| Property | Values | Read by |
|---|---|---|
| `dataClassification` | public, internal, confidential, restricted | SEC001 (on the element and on the data it accesses), `exposure` |
| `personalData` | none, personal, special-category | SEC003, `exposure` |
| `secConfidentiality`, `secIntegrity`, `secAvailability` | low, moderate, high (FIPS 199) | ALN009, `exposure` |
| `exposure` | internal, partner, public | SEC001, `exposure` |
| `trustZone` | your own label (dmz, internal, partner-net) | SEC002, `propose --from threats` |

Every rule is silent until the model uses the property it reads. Start where the risk
is: the public elements, the restricted data, the boundaries between zones.

"Governed" has one meaning everywhere: a `Requirement`, `Constraint` or `Principle` binds
the element through `appliesTo`, or the element claims a standard. An `Assessment` does
not govern -- it is the question, not the answer.

## The rules

| Code | Severity | What to do when it fires |
|---|---|---|
| `SEC001` | warning | A public element holds confidential or restricted data -- its own, or a data object it accesses -- and nothing governs it. Bind the control that protects it (authentication, encryption, a WAF policy) as a requirement, or claim the baseline standard it meets. |
| `SEC002` | warning | A relationship crosses trust zones and neither end is governed. Start from a threat assessment (`propose --from threats`); its outcome is a requirement on one end, a standard, or a dispensation. |
| `SEC003` | warning | Personal data outside the GDPR scope. Add `gdpr` to `regulatoryScope` (`ai-act gdpr`, alphabetical, for more than one) so the record of processing activities lists it -- or correct `personalData` if the evidence says otherwise. |
| `ALN009` | warning | An element rated high that no control of a control pack anchors -- directly, or through the requirement that binds it. Map the control in that pack's `mappings.yaml`. |

## Reading the exposure report

`exposure` starts at every `exposure: public` element and walks the paths an attacker
holding it could take, by a declared table (`REACH` in `easkills/security.py`): a
consumer reaches the service it uses (opposite to change impact), an accessor reaches
its data, a flow reaches its destination, wholes and parts reach each other.
`Association` is never walked -- if it matters, it should be a relationship that says how.

For each public element it names the sensitive data, the high-rated elements, the personal
data, the trust boundaries crossed and the **ungoverned** elements in reach. Read the
ungoverned list first: a restricted record two hops from the internet with nothing
governing the hop in between is the finding the report exists to surface. It is a report,
not a gate -- what to do about a path is a decision, and it belongs on the board agenda
(`ea-board`) when it is not cheap.

## Threat assessments

`propose --from threats` writes one `Assessment` skeleton per relationship that crosses a
trust boundary, into `model/staging/proposed-threat-assessments.yaml`, bound to both ends,
with STRIDE in the placeholder. Completing one means, for each of the six categories:
does it apply across this boundary, and if so what treats it -- a requirement bound to an
end, a standard claimed, or accepted risk as a dispensation. A category that does not
apply needs one sentence saying why. Then an owner and a review date, and the promotion
gate takes it like anything else.

A governed crossing still gets a skeleton: `SEC002` asks whether anything governs the
ends, not whether anyone assessed the boundary.

## Control frameworks

* `nist-sp-800-53-r5` -- families and base controls, generated from NIST's OSCAL catalog.
  Controls are answered by local requirements, constraints and principles; map each one
  you meet, and record exclusions with a rationale (out-of-scope inherits down a family).
* `nist-sp-800-207` -- the seven zero-trust tenets, answered by principles.
* `nist-csf-2.0` -- outcomes, for a programme-level view.

Check each pack's NOTICE before leaning on it: two of these are labelled *structure not
yet verified* (generated or extracted mechanically, not yet read by a person). Report each
framework separately; they partition the world differently on purpose.

## SBOMs and the SIB

A security standard a manifest can show belongs in the SIB with a `detect:` rule, and
`ea-check` holds product repositories to it. With an SBOM, name the package by URL
without its version:

```yaml
detect:
  - manifest: sbom
    dependency: pkg:maven/org.apache.logging.log4j/log4j-core
```

Then `easkills check --repo . --scope <id> --sbom bom.cdx.json` reads the CycloneDX or
SPDX document the build already produces. Retiring a standard (a library with a known
vulnerability class) turns every repository still shipping it into a named `CHK002`.

## Reporting back

The exposure verdict first -- which public elements reach sensitive data, through what --
then the SEC and ALN009 findings grouped by treatment (requirement to bind, standard to
claim, assessment to write, dispensation to file), then the threat assessments proposed
and not yet written. Close with what the vocabulary does not cover yet: elements nobody
has classified are not safe, they are unexamined.
