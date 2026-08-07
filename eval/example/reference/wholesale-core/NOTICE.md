# NOTICE — Wholesale Core capability reference

**Source.** None. This taxonomy was **authored for the ea-skills worked example** by the
maintainers of this repository, and is licensed with the rest of the repository (MIT).

It is *not* a transcription, abridgement or paraphrase of BIAN, the APQC Process
Classification Framework, eTOM, ACORD, TOGAF's Technical Reference Model, or any other
published reference model. Those are licensed works: they may not be redistributed here,
and copying one into a fixture "just for the example" would be a licence breach dressed
up as convenience. See [`references/README.md`](../../../../references/README.md) for what
this repository does ship, and `template/reference/README.md` for how to drop a licensed
pack into your own repository, where your licence covers it.

**What it is for.** Aurora Foods is a fictional B2B food wholesaler, so the example needs
a wholesale-shaped yardstick to be aligned against. Four domains and the capabilities
under them, chosen so the example demonstrates every state a mapping can be in:
capabilities the model genuinely covers, several it covers only partly, one deliberate
exclusion with its reason, and a whole domain excluded by a single recorded decision that
its children inherit.

**What it is not.** Not an industry standard, not a benchmark, and not advice about what
capabilities a food wholesaler ought to have. If you are looking for a real reference
model, license one; if you are looking for what a pack looks like, this is it.

**Integrity.** `model.yaml` and this file are pinned in `SHA256SUMS`; `align` refuses to
read the pack if either byte-changes (`ALN001`). `mappings.yaml` is deliberately *not*
pinned — it is the file an architect edits, and pinning it would make re-pinning a
reflex, which is how pins stop meaning anything.
