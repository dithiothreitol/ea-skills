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

**Verification status: structure not yet verified against the cited source.**
It was written from working knowledge of CSF 2.0 rather than read off NIST CSWP 29 node
by node, and nothing mechanical can catch the difference — a Category name that is
subtly wrong, or a Category that does not exist, looks exactly like a correct one to
every later reader and to every `align` report. Treat this pack as a **draft yardstick**
until someone has done that reading:

* Do not cite a node of this pack as evidence of what NIST requires.
* Do not let an `ALN004` gap from this pack alone drive an investment decision.
* Do check it before you rely on it — open CSWP 29, walk the Function and Category
  tables, and correct or confirm `model.yaml`. Then re-pin
  (`python -m easkills pin-reference --dir references/nist-csf-2.0`), delete this
  section, and say in the commit message that the reading was done.

This is stated here rather than quietly fixed later because an unverified taxonomy that
*looks* verified is the failure this repository exists to prevent one layer down, where
element provenance is mechanically checked. The reference layer has no such check, so it
gets a written status instead.

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
