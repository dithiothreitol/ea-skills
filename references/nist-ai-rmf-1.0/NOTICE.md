# NOTICE — NIST AI Risk Management Framework 1.0

**Source.** *Artificial Intelligence Risk Management Framework (AI RMF 1.0)*, NIST AI
100-1, National Institute of Standards and Technology, U.S. Department of Commerce,
January 2023. <https://doi.org/10.6028/NIST.AI.100-1>

**Licence / status.** A work of the United States federal government. Under 17 U.S.C.
§105 it is **not subject to copyright protection in the United States** and is in the
public domain. NIST asks that it be cited, which is what this file is for. NIST does
not endorse this repository or any product; "NIST" is used here only to identify the
source of the taxonomy.

**What is transcribed here.** Structure only: the four Functions (GOVERN, MAP, MEASURE,
MANAGE) and their nineteen Categories. The AI RMF publishes no short category names —
the numbered outcome statement *is* the category — so each node's name carries that
statement verbatim. Subcategories and the Playbook's suggested actions are **not**
included, and nothing is paraphrased: the Framework's own text is the authority on what
each Category requires.

**Verification status: structure not yet verified.** The Functions and Categories were
transcribed from the Framework's text as published by NIST (the AI RMF Core, via NIST's
AI Resource Center rendering of NIST AI 100-1), not written from memory — but no human
has yet walked `model.yaml` against the cited edition and confirmed identifiers, wording
and parentage, which is the reading this repository requires before a pack stops being a
draft yardstick. Until that reading happens and this section becomes a dated statement
of it: do not cite these nodes as evidence of what the source requires, and do not let
one of their gaps alone drive a decision. A gap list produced against this pack is still
useful; its provenance is provisional.

**What this pack is for.** It is a yardstick for `python -m easkills align`: a checklist
of AI-risk-management areas an architecture is measured against, so an unexamined area
shows up as a named gap (`ALN004`) instead of as silence. Coverage of a Category by a
model element is **not** a statement of compliance, certification or assurance — those
are judgements humans make with evidence this tooling does not hold.

**Integrity.** `model.yaml` and this file are pinned in `SHA256SUMS`. `align` refuses to
read the pack if either byte-changes (`ALN001`); re-pin with
`python -m easkills pin-reference --dir references/nist-ai-rmf-1.0` only for a
deliberate, reviewed update — for instance the verification reading above, or a later
AI RMF edition, in which case update the citation in the same commit.
