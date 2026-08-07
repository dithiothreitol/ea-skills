# NOTICE — bundled typefaces

Three typefaces are bundled here as `woff2` subsets (`latin` and `latin-ext`; the
Polish diacritics live in `latin-ext`). They were taken from the `next/font` build
cache of the ArchXS site, which fetches them from Google Fonts, so they are the
upstream releases unmodified apart from subsetting.

| Family | Copyright | Licence | Upstream |
|---|---|---|---|
| Fraunces | Copyright The Fraunces Project Authors | SIL Open Font License 1.1 | <https://github.com/undercasetype/Fraunces> |
| Inter | Copyright The Inter Project Authors | SIL Open Font License 1.1 | <https://github.com/rsms/inter> |
| IBM Plex Mono | Copyright IBM Corp. | SIL Open Font License 1.1 | <https://github.com/IBM/plex> |

OFL 1.1 permits bundling and redistribution, including inside a commercial or
differently licensed work. It is **not** covered by this repository's MIT licence;
see [`NOTICE.md`](../../../NOTICE.md) at the root.

**Outstanding obligation: the full OFL 1.1 text is not yet bundled here.** Section 1
of the licence requires the licence to accompany the fonts, and a link is not the
same thing as a copy. Fetch `OFL.txt` from each upstream repository above and commit
the three copies alongside these files, then delete this paragraph. This is written
down rather than left implicit for the same reason the reference packs carry a
verification status: an unmet obligation that looks met is worse than one that is
named.

Nothing in `easkills/` reads these files. They exist only so that
[`render.mjs`](../render.mjs) produces the same slides offline as online.
