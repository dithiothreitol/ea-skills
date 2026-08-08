# The open reference library

Reference packs an architecture repository can copy into its own `reference/` directory
and align against (`python -m easkills align`). **Only openly licensed content ships
here** — everything in this directory is either public domain or public law, with a
`NOTICE.md` naming its source and status.

| Pack | Nodes | Source | Licence | Verification |
|---|---|---|---|---|
| [`nist-csf-2.0/`](nist-csf-2.0/) | functions + categories | NIST CSWP 29 (2024) | public domain (17 U.S.C. §105) | **verified 2026-08-07** against the cited edition, see its [NOTICE](nist-csf-2.0/NOTICE.md) |
| [`nist-ai-rmf-1.0/`](nist-ai-rmf-1.0/) | functions + categories | NIST AI 100-1 (2023) | public domain (17 U.S.C. §105) | **structure not yet verified** — transcribed from the published text, awaiting the human reading its [NOTICE](nist-ai-rmf-1.0/NOTICE.md) describes |
| [`knf-rek-d-2013/`](knf-rek-d-2013/) | areas + recommendations | Uchwała 7/2013 KNF (Dz. Urz. KNF 2013 poz. 5) | public law (art. 4 polskiego prawa autorskiego) | **structure not yet verified** — transcribed from the official PDF, awaiting the human reading its [NOTICE](knf-rek-d-2013/NOTICE.md) describes |

## Using one

```bash
mkdir -p <your-ea-repo>/reference
cp -r references/nist-csf-2.0 <your-ea-repo>/reference/
python -m easkills align --root <your-ea-repo> --reference nist-csf-2.0
```

Every node starts as a gap (`ALN004`). Closing them is authoring
`reference/nist-csf-2.0/mappings.yaml` — one entry per node, either naming the local
elements that answer it or recording *with a rationale* that it is out of scope. The
`ea-align` skill is the discipline; `template/reference/README.md` is the drop-in
procedure, including for the licensed packs that cannot ship here.

## Verification, and why the column above is not decoration

A shipped pack is data other people measure their architecture against, so it carries the
same obligation the vendored oracle does — and one no test in this repository can
discharge:

**A pack's structure is verified when a human has read the primary source its NOTICE cites
and walked the taxonomy against it.** Not a recollection of that source, and not a
secondary summary. A reference taxonomy written from memory is the exact failure this
repository exists to prevent one layer down, where every element's provenance is
mechanically located in a real file: an invented or subtly misnamed node is
indistinguishable from a correct one to every later reader *and* to every `align` report,
and it will be used to justify investment.

So the verification state is written down per pack, in the NOTICE and in the table above,
and a test asserts the two agree — an unverified pack silently losing its caveat is
exactly how a draft yardstick becomes an authority. Until a pack says verified:

* do not cite its nodes as evidence of what the source requires;
* do not let one of its gaps alone drive a decision;
* do gate on it if you like — a gap list is still useful while its provenance is provisional.

When the reading is done: correct or confirm `model.yaml`, turn the NOTICE's
verification-status section into a dated statement of what was read and against which
edition, carry that date into the table above, re-pin
(`python -m easkills pin-reference --dir references/<pack>`), and say in the commit message
that the reading happened. **The date is not decoration, and a test requires it** —
verification is against one edition of one document, so an undated claim cannot be known to
have gone stale, and a pack that outlives its source edition is the draft yardstick again
wearing a better label.

`ALN001` protects a pack after that check. It cannot perform it, and it does not pretend to.

## What is deliberately absent

**BIAN, APQC PCF, eTOM, ACORD, TOGAF's TRM and the like are licensed.** They are the
reference models most organisations actually own, and none of them may be redistributed
here — so the split is *mechanism here, content at the adopter*: the loader, the
validator and the reports live in this repository, the taxonomy lives in yours, under
your licence. Transcribing a licensed taxonomy into a fixture "just for the example"
would be a licence breach dressed as convenience.

**No mappings ship with a pack either.** A mapping is a judgement about one
organisation's architecture; a shipped one would be a guess about yours, and a
plausible guess is worse than an empty file, because an empty file is honest about
where the work has not been done.
