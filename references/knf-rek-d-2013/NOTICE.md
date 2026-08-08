# NOTICE — KNF Rekomendacja D (2013)

**Source.** *Rekomendacja D dotycząca zarządzania obszarami technologii informacyjnej i
bezpieczeństwa środowiska teleinformatycznego w bankach*, Komisja Nadzoru Finansowego,
załącznik do uchwały Nr 7/2013 KNF z dnia 8 stycznia 2013 r. (Dz. Urz. KNF z 2013 r.
poz. 5), issued under art. 137 pkt 5 of the Polish Banking Law.
<https://www.knf.gov.pl/knf/pl/komponenty/img/Rekomendacja_D_8_01_13_uchwala_7_33016.pdf>

**Licence / status.** An official document of a Polish public authority, published in
the authority's official journal. Under art. 4 pkt 1–2 of the Polish Copyright Act
(ustawa z dnia 4 lutego 1994 r. o prawie autorskim i prawach pokrewnych), official
documents and official materials are **not subject to copyright**; this pack ships as
public law. KNF does not endorse this repository or any product; the Recommendation is
named here only to identify the source of the taxonomy.

**What is transcribed here.** Structure plus the normative statements: the four areas
(obszary) the document declares, the twenty-two recommendations, each node named with
the document's own section heading (from its table of contents) and carrying the
recommendation's statement **verbatim, in Polish** as its description. The detailed
numbered guidance under each recommendation (1.1, 1.2, …) is not included. Nothing is
paraphrased or translated — the document's own wording is the normative text.

**Verification status: structure not yet verified.** Two things are true at once here,
and collapsing them into one word is exactly what this section exists to prevent.

*What has been done (2026-08-08).* The areas, statements and headings were transcribed
from the text of the cited official PDF (list of recommendations, pp. 8–11; areas, p. 4;
headings, table of contents), not written from memory. The one inference the pack
originally rested on — which heading belongs to which numbered recommendation, taken from
the table of contents' order — has since been **checked directly against the document
body**: each `N. Rekomendacja N` section opener in chapters IV–VII was located and the
heading preceding it compared against `model.yaml`. All twenty-two matched, so the
correspondence is now read off the source rather than inferred; no correction was needed.

*What has not been done.* That check was run by an agent, not read by a person. This
repository defines a verified pack as one **a human** has read the primary source for and
walked the taxonomy against, and the distinction is not ceremony: a mechanical comparison
confirms that two strings agree, not that the taxonomy means what a reader will take it to
mean — and this pack additionally carries Polish legal text, where that gap is wider, not
narrower. Until a person does that reading and replaces this section with a dated
statement of it, treat the pack as a draft yardstick: do not cite these nodes as evidence
of what the source requires, and do not let one of their gaps alone drive a decision. A
gap list produced against this pack is still useful, and the check above should make the
remaining reading short.

**What this pack is for.** It is a yardstick for `python -m easkills align`: a checklist
of the IT-governance and ICT-security areas KNF's supervisory expectations name, so an
unexamined area shows up as a named gap (`ALN004`) instead of as silence. It applies to
banks (and, appropriately, to branches of credit institutions); coverage of a
recommendation by a model element is **not** a statement of compliance with it — that is
a judgement humans make with evidence this tooling does not hold, under the
proportionality principle the document itself states.

**Integrity.** `model.yaml` and this file are pinned in `SHA256SUMS`. `align` refuses to
read the pack if either byte-changes (`ALN001`); re-pin with
`python -m easkills pin-reference --dir references/knf-rek-d-2013` only for a
deliberate, reviewed update — for instance the verification reading above, or a later
edition of the Recommendation, in which case update the citation in the same commit.
