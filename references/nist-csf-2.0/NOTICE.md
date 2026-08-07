# NOTICE — NIST Cybersecurity Framework 2.0

**Source.** *The NIST Cybersecurity Framework (CSF) 2.0*, NIST Cybersecurity White
Paper NIST CSWP 29, National Institute of Standards and Technology, U.S. Department of
Commerce, February 2024. <https://doi.org/10.6028/NIST.CSWP.29>

**Licence / status.** A work of the United States federal government. Under 17 U.S.C.
§105 it is **not subject to copyright protection in the United States** and is in the
public domain. NIST asks that it be cited, which is what this file is for. NIST does
not endorse this repository or any product; "NIST" is used here only to identify the
source of the taxonomy.

**What is transcribed here.** Structure only: the six Functions (GOVERN, IDENTIFY,
PROTECT, DETECT, RESPOND, RECOVER) and the twenty-two Categories, with the identifiers
NIST publishes for them (`GV.OC`, `ID.AM`, …). Subcategories, Implementation Examples
and Informative References are **not** included, and no normative wording is
paraphrased — the Framework's own text is the authority on what each Category means.

**Verification status: structure verified against the cited source, 2026-08-07.** The six
Functions and twenty-two Categories in `model.yaml` were walked against the Function and
Category tables of NIST CSWP 29 by this repository's maintainer and confirmed as
transcribed — identifiers, names and parentage, which is the whole of what this pack
carries. No correction was needed. The commit bearing this line is the record of that
reading; nothing in this repository can re-perform it.

Two limits survive the check, and both are properties of the pack rather than doubts about
it. The reading was against the **February 2024** edition cited above, so a later CSF
edition makes this statement stale — re-read the tables and re-date this line in the same
commit that changes the citation. And a verified *structure* is not a verified *meaning*:
the identifiers are right, and what each Category requires is still the Framework's own
text to say.

The state is written down rather than left implicit because an unverified taxonomy that
*looks* verified is the failure this repository exists to prevent one layer down, where
element provenance is mechanically checked. The reference layer has no such check, so it
gets a written status instead — including when the answer is good.

**What this pack is for.** It is a yardstick for `python -m easkills align`: a checklist
of security-governance areas an architecture is measured against, so an unexamined area
shows up as a named gap (`ALN004`) instead of as silence. Coverage of a Category by a
model element is **not** a statement of compliance, certification or assurance — those
are judgements humans make with evidence this tooling does not hold.

**Integrity.** `model.yaml` and this file are pinned in `SHA256SUMS`. `align` refuses to
read the pack if either byte-changes (`ALN001`); re-pin with
`python -m easkills pin-reference --reference nist-csf-2.0` only for a deliberate,
reviewed update — for instance a later CSF edition, in which case update the citation
above in the same commit.
