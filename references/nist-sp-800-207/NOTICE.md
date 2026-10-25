# NOTICE — NIST SP 800-207 Zero Trust Architecture

**Source.** Scott Rose, Oliver Borchert, Stu Mitchell, Sean Connelly, *Zero Trust
Architecture*, NIST Special Publication 800-207, National Institute of Standards and
Technology, U.S. Department of Commerce, August 2020, Section 2.1 "Tenets of Zero Trust".
<https://doi.org/10.6028/NIST.SP.800-207>

**Licence / status.** A work of the United States federal government. Under 17 U.S.C.
§105 it is **not subject to copyright protection in the United States** and is in the
public domain. NIST asks that it be cited, which is what this file is for. NIST does not
endorse this repository or any product; "NIST" is used here only to identify the source of
the taxonomy.

**What is transcribed here.** The seven basic tenets of Section 2.1, one node each, under
one domain node for the section. Each tenet's **lead sentence** is carried verbatim in the
node's `description`; the node's `name` is the same sentence, except for tenet 4, whose
lead sentence (211 characters) exceeds the pack schema's 200 and is named by its own
opening words up to the first dash. The explanatory paragraphs that follow each lead
sentence are not reproduced: they, and the rest of the publication, are the authority on
what a tenet asks of an architecture.

**Verification status: structure not yet verified.** Two things are true at once here,
and collapsing them into one word is exactly what this section exists to prevent.

*What has been done (2026-10-25).* The tenets were not written from memory. The PDF of the
cited edition was fetched from the DOI above (SHA-256 `0290d6ec…5e03d`), its text extracted
with `pypdf`, and the seven lead sentences of Section 2.1 split out mechanically — the
numbered items between "basic tenets:" and "The above tenets attempt", each item's text up
to its first sentence end. All seven matched the transcription below character for
character, with one exception the extraction itself cannot settle: the two dashes in tenet
4 are drawn by a glyph the PDF maps to no Unicode character, so the extracted text shows a
replacement character where this pack has an em dash. The em dash is an inference from the
publication's typography, stated here rather than presented as extracted.

*What has not been done.* That check was run by an agent, not read by a person. This
repository defines a verified pack as one **a human** has read the primary source for and
walked the taxonomy against. Until a person does that reading — including the two dashes
above — and replaces this section with a dated statement of it, treat the pack as a draft
yardstick: do not cite these nodes as evidence of what the source requires, and do not let
one of their gaps alone drive a decision.

**What this pack is for.** A yardstick for `python -m easkills align`: the seven tenets as
seven nodes a model's principles and requirements can answer, so a tenet the architecture
has not addressed shows up as a named gap (`ALN004`). Coverage of a tenet is **not** a
statement that the architecture is zero trust — the publication itself says the tenets are
an ideal goal not every strategy implements in its purest form.

**Integrity.** `model.yaml` and this file are pinned in `SHA256SUMS`. `align` refuses to
read the pack if either byte-changes (`ALN001`); re-pin with
`python -m easkills pin-reference --dir references/nist-sp-800-207` only for a deliberate,
reviewed update, such as the human reading above.
