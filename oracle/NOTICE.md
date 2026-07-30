# Vendored validation oracle -- provenance and licensing

Every semantic rule in this repository is decided by the files in this directory, not by
a language model and not by rules typed from memory. They are vendored rather than
fetched at runtime for two reasons: `pubs.opengroup.org` sits behind SSO, and a
validation gate that depends on the network is not a gate.

`SHA256SUMS` pins each file. The validator reports `ORACLE001` if any file drifts from
its pin, so an oracle change is always a deliberate, reviewable commit
(`python -m easkills pin-oracle` after reviewing the diff).

| File | Source | Retrieved | Purpose |
|---|---|---|---|
| `relationships.xml` | [archimatetool/archi](https://github.com/archimatetool/archi/blob/master/com.archimatetool.model/model/relationships.xml) -- `com.archimatetool.model/model/` | 2026-07-29 | ArchiMate 3.2 permitted-relationship matrix (declares `version="3.2"`; 11 569 permitted source/target/type combinations). Drives rule `REL001`. |
| `relationships-keys.xml` | [archimatetool/archi](https://github.com/archimatetool/archi/blob/master/com.archimatetool.model/model/relationships-keys.xml) | 2026-07-29 | Letter legend for the matrix (`v` = Serving, `r` = Realization, ...). Read this rather than guessing letter meanings. |
| `archimate3_Model.xsd` | [The Open Group](https://www.opengroup.org/xsd/archimate/) -- `3.1/` | 2026-07-29 | Model Exchange File Format schema (Open Group document C19C, covers ArchiMate 3.1 **and** 3.2 models). Drives the compiler's output validation. |
| `archimate3_Diagram.xsd` | The Open Group, as above | 2026-07-29 | Adds views/diagrams. This is the schema a model **with views** must validate against. |
| `archimate3_View.xsd` | The Open Group, as above | 2026-07-29 | Included by the Diagram schema; adds `views` to the model root. |
| `xml.xsd` | [W3C](https://www.w3.org/2001/xml.xsd) | 2026-07-30 | Schema for the `xml:` namespace (`xml:lang`). Required because `archimate3_Model.xsd` imports it **by URL**. |

## The xml.xsd trap

`archimate3_Model.xsd` line 11 declares:

```xml
<xs:import namespace="http://www.w3.org/XML/1998/namespace"
           schemaLocation="http://www.w3.org/2001/xml.xsd" />
```

A naive `etree.XMLSchema(etree.parse(...))` therefore fetches that schema from w3.org
every time it validates. It works on a developer machine with network access and fails in
a sandboxed CI runner -- the worst failure mode available to a validation gate, because it
passes exactly where nobody is watching and fails where everybody is.

`easkills/oracle.py` builds the schema through a parser with `no_network=True` plus an
offline resolver that maps the URL to the vendored copy and **raises** on any other
remote reference. The vendored Open Group files are left byte-identical, since they are
hash-pinned; only the resolution is redirected. `test_exchange_schema_builds_without_network`
locks this in: with the network disabled at parser level, a successful schema build is
proof the import resolved locally.

## Licensing

The vendored files are third-party material and are **not** covered by this
repository's licence:

* Archi's `relationships*.xml` come from the Archi source tree (Archi is distributed
  under the MIT licence). They are included unmodified with attribution.
* The Open Group XSDs are published for public use as part of the ArchiMate Model
  Exchange File Format standard, downloadable without registration from
  `https://www.opengroup.org/xsd/archimate/`. ArchiMate(R) is a registered trademark of
  The Open Group.

If you redistribute this repository commercially, confirm the current terms with the
respective sources -- the pins above make it unambiguous which revision you are relying
on. The alternative to vendoring, for anyone who prefers it, is to point the loader in
`easkills/oracle.py` at a locally installed Archi.

## Not vendored, deliberately

* **The ArchiMate specification text.** Rules are derived from the machine-readable
  matrix, not from prose, so no specification text is reproduced here.
* **The TOGAF standard.** Governance skills implement its mechanics (conformance
  levels, dispensations with expiry, Phase H change classes) in this repository's own
  words; no TOGAF text is copied.
* **pyArchimate.** Phase 0 needs only `lxml` plus these schemas, so the project avoids
  taking a GPL-3.0 dependency. Revisit only if SVG rendering or auto-layout is needed
  and Archi's headless CLI proves insufficient.
