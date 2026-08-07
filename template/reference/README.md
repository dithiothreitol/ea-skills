# `reference/` — the reference models this architecture is measured against

A **reference model** is a yardstick: an industry blueprint's list of the things a
business like yours has, so that "is this layer done?" has an answer that is not a
feeling. `python -m easkills align` reports each node of it as `covered`, `partial`, a
**gap**, or `out-of-scope` *with a rationale you wrote down*.

One directory per reference model:

```
reference/
  <name>/                    # one slug per reference model, yours to choose
    model.yaml               # the taxonomy      -- pinned
    NOTICE.md                # source + licence  -- pinned
    SHA256SUMS               # the pins
    mappings.yaml            # your judgement    -- NOT pinned; this is the file you edit
```

More than one is normal and often right: a capability reference and a control framework
answer different questions about the same model, and `align` reports each separately. Do
not try to reconcile two references — they partition the world differently on purpose.

## Why the content is yours and not shipped with the tooling

The reference models most organisations actually use — **BIAN**, the **APQC Process
Classification Framework**, **eTOM**, **ACORD**, TOGAF's Technical Reference Model — are
licensed works. They may not be redistributed by the ea-skills repository, so the split
is *mechanism there, content here*: the loader, the rules and the reports come from the
tooling, and the taxonomy lives in your repository under the licence your organisation
holds.

That split has a consequence worth stating plainly: **nothing may transcribe a licensed
taxonomy for you.** Not a colleague "typing up the useful bits", and not an agent asked
to "add the BIAN service domains" — an agent reproducing a licensed taxonomy from memory
is both a licence problem and a fabrication problem, since nobody can tell an accurate
transcription from a plausible one. Export it from the source you licensed, or do not
have it.

Openly licensed packs *are* shipped, and are the place to start — `references/` in the
ea-skills repository. Starting there is not a compromise: an open pack you can actually
read beats a licensed one nobody in the room has opened, and the drop-in procedure is
identical, so the first one teaches you the second.

Check each shipped pack's NOTICE for its **verification status** before leaning on it. One
that says *structure not yet verified* is a draft yardstick: useful for producing a gap
list, not for citing as evidence of what the source requires.

**If your licence does not let you commit the taxonomy**, gitignore it and keep the rest:

```gitignore
reference/*/model.yaml
```

`mappings.yaml`, `NOTICE.md` and `SHA256SUMS` stay committed — so your judgement, your
provenance record and the digest the taxonomy must match are all reviewable, and a
colleague with the licensed export can reproduce the pack and have `align` confirm it is
byte-identical to the one your mappings were written against. That is the same bargain the
API key gets: the mechanism in git, the material out of it.

On a checkout where the taxonomy is absent, `align` reports `ALN001` with *missing file*
and refuses the pack. That is the intended outcome: a report that quietly omitted a
reference nobody could load would read as a reference with no gaps.

## Dropping in a shipped pack (do this one first)

```bash
cp -r <path-to-ea-skills>/references/nist-csf-2.0 reference/
python -m easkills align --root . --reference nist-csf-2.0
```

That is the whole procedure when the pack is already pinned. Every node comes back a gap,
which is the honest starting point, and you now have a checklist of security-governance
areas to account for.

## Dropping in one of your own

Same shape, three files instead of a copy. `<name>` is yours — a short slug you will type
in `--reference`.

```bash
# 1. The taxonomy, in the node shape below. Export it from the source you licensed;
#    do not type it from memory, and do not ask an agent to.
mkdir -p reference/<name>
$EDITOR reference/<name>/model.yaml

# 2. The NOTICE: what it is, where it came from, under what licence, what your
#    organisation may do with it -- and whether anyone has verified it against the
#    source yet. A pack without a NOTICE will not load.
$EDITOR reference/<name>/NOTICE.md

# 3. Pin it. From here on an edit to either file is refused (ALN001) until re-pinned.
python -m easkills pin-reference --root . --reference <name>

# 4. See where you stand.
python -m easkills align --root . --reference <name>
```

`model.yaml` — a taxonomy and deliberately nothing more. Nodes carry a `parent` and no
other relation: edges between *architecture* elements belong in `model/`, where the
ArchiMate oracle governs them.

```yaml
name: <the reference model's own name>
version: "<edition>"
source: Licensed copy, exported <date>          # the NOTICE carries the licence terms
nodes:
  - id: ref-customer-management
    name: Customer Management
    kind: domain              # capability | control | process | domain
    externalId: "1.0"         # the code the source publishes; printed in reports
  - id: ref-customer-service
    name: Customer Service
    kind: capability
    parent: ref-customer-management
    externalId: "1.1"
```

## Closing gaps: `mappings.yaml`

```yaml
mappings:
  - ref: ref-customer-service
    status: covered
    elements: [cap-customer-service, app-crm]

  - ref: ref-complaint-handling
    status: partial
    elements: [app-crm]
    note: >
      The CRM logs complaints; adjudication and redress are a manual process nobody has
      modelled yet. Raised as a clarification question, not painted over.

  - ref: ref-human-capital
    status: out-of-scope
    rationale: >
      HR runs on a shared-service provider outside this architecture's remit; the
      decision is the CIO's, recorded 2026-07-14.
```

Three rules that are not negotiable, because the tooling enforces them:

1. **A rationale is mandatory for `out-of-scope`** (`ALN005`). Without one the node is
   reported as a gap — a silent exclusion excludes nothing. The rationale is what lets
   the next reader tell an outsourced capability from a forgotten one.
2. **A coverage claim names real elements** (`ALN003`), and elements that exist only in
   `model/staging/` do not count while you are reading `approved` (`ALN007`). Promotion
   is what closes a gap; a proposal is what *would*.
3. **One node, one entry** (`ALN006`). Two judgements of the same node are a
   disagreement, not a merge.

The judgement itself — which reference to adopt, how coarse a mapping may be before it
stops meaning anything, when a gap is a finding versus a deliberate business choice — is
the `ea-align` skill's subject. Read it before authoring the first mapping.

## Gating on it

```bash
python -m easkills align --strict                  # gaps fail: for a repository that claims completeness
python -m easkills align --min-coverage 80         # a floor, for one that is still filling in
```

Neither belongs in CI on day one. A pack you have just dropped in is 100% gaps by
construction, and a gate that is red from the first commit gets disabled rather than
fixed. Add the gate when the number is one you would defend.
