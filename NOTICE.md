# NOTICE — what the MIT licence covers, and what it does not

[`LICENSE`](LICENSE) is the MIT licence, and it covers **the code and documentation
authored in this repository**. It does not cover third-party material distributed
alongside that work, which carries its own terms. This file names every such case; the
scope note lives here rather than appended to `LICENSE` so that automated licence
detection can recognise the MIT text unmodified — a scope note that makes tooling report
"Other" tells adopters less than it tells them.

## Vendored under `oracle/`

The validation oracle is third-party material, vendored rather than fetched so that the
gate does not depend on the network. Provenance, retrieval dates and hash pins are in
[`oracle/NOTICE.md`](oracle/NOTICE.md); in summary:

* **`relationships.xml`, `relationships-keys.xml`** — from the Archi source tree
  (archimatetool/archi), distributed under the MIT licence, included unmodified with
  attribution.
* **`archimate3_Model.xsd`, `archimate3_Diagram.xsd`, `archimate3_View.xsd`** — The Open
  Group's ArchiMate Model Exchange File Format schemas, published for public use.
  ArchiMate® is a registered trademark of The Open Group, used here only to identify the
  notation this tooling reads and writes.
* **`xml.xsd`** — W3C, required because the Open Group schema imports it by URL.

If you redistribute this repository commercially, confirm the current terms with each
source. The hash pins make it unambiguous which revision you are relying on.

## Shipped under `references/`

Reference packs are data, not code, and **only openly licensed content ships here** —
public domain or public law, each with a `NOTICE.md` naming its source, its licence status
and whether a human has verified its structure against that source. See
[`references/README.md`](references/README.md).

* **`nist-csf-2.0/`** — NIST Cybersecurity White Paper CSWP 29 (February 2024). A work of
  the U.S. federal government, not subject to copyright protection in the United States
  under 17 U.S.C. §105. NIST does not endorse this repository or any product.

**BIAN, APQC PCF, eTOM, ACORD and TOGAF's TRM are licensed and are deliberately absent.**
They are the reference models most organisations actually own, and none of them may be
redistributed here — so the split is mechanism here, content at the adopter, under the
adopter's licence. Transcribing a licensed taxonomy into a fixture "for the example" would
be a licence breach dressed as convenience.

## Standards implemented, not reproduced

No specification text is copied into this repository. ArchiMate rules are derived from the
machine-readable relationship matrix above rather than from prose; TOGAF governance
mechanics and the ISO/IEC/IEEE 42010:2022 conformance checklist are implemented in this
repository's own words. The standards themselves remain the authority on their own
meaning, and none of them is reproduced here in whole or in part.
