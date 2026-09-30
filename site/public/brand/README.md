# LegalForecastBench identity

The approved identity is the plain courthouse (option A): a pediment, three columns, and a base, in burgundy `#781D2B`, paired with the Newsreader wordmark. It has no probability curve or lettering inside the icon.

## Assets

- `courthouse.svg`: standalone mark on a transparent background.
- `wordmark.svg`: courthouse and outlined LegalForecastBench name.
- `partnership.svg`: full lockup with “In partnership with LegalQuants” and the official LegalQuants mark.
- `*-reversed.svg`: cream versions for dark backgrounds; the LegalQuants mark retains its original colors.
- `legalquants.svg`: official partner mark, with its original geometry and colors.

Keep aspect ratios intact. Leave at least one column-width of clear space around the courthouse. Use the standalone icon at small sizes; use the full partnership lockup only when the partner mark remains at least 24 pixels high (the supplied lockup needs a width of at least 468 pixels). The website header uses accessible live text and a separate 24-pixel partner mark so the partnership remains readable on phones.

The root public directory contains `favicon.svg`, `favicon.ico` (16, 32, and 48 pixels), `favicon-32.png`, and `apple-touch-icon.png` (180 pixels). Their cream backgrounds preserve contrast in browser chrome of either theme. The Apple icon has a square background; the device applies its own mask.

## Editing and regeneration

Edit the courthouse geometry in `src/brand.ts` and the export composition in `scripts/generate-brand.tsx`, relative to the site directory. Run `pnpm brand:generate` from that directory. This uses the project's pinned Satori, Resvg, and Fontsource dependencies; no additional tooling is needed. Commit regenerated assets with their source changes. SVG wordmarks have outlined text and embedded vector partner artwork, with no remote fonts or image dependencies.

## Credits and rights

The LegalQuants mark was obtained from the [official brand page](https://www.legalquants.com/brand) on September 29, 2026. LegalQuants retains rights to its name and mark; their inclusion here does not license third-party trademark use under this repository's software license. Keep the two identities distinct and follow the partner's brand guidelines.

Newsreader and Inter are distributed under the SIL Open Font License. Their notices are included beside these exports. Font licenses and partner trademark rights remain separate from the repository's Apache software license.
