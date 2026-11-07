# MUSÉANCE visual style (for the stage UI in `court/ui/`)

Source: Alejandro's SeaBridge design system (colors, type scale, tone), adapted for MUSÉANCE. Only the design language is reused: **no SeaBridge logo, mascot or licensed font files** go into this repo. The SeaBridge display font (Recoleta) is licensed, so we use **Fraunces** (SIL OFL, Google Fonts) for display text instead.

Tone: modern, calm, institutional ("a real court, not a cartoon"): clean light surfaces, deep navy headings, one aqua accent, state colors that mean something. The cast (ghost, penguin, owl) stays, drawn small and flat on top of this, never as the background.

## Tokens (paste into `:root`)

```css
:root {
  /* brand */
  --navy: #0F2757;        /* headings, primary action, dark bars */
  --navy-900: #081739;    /* deepest background (header/footer bar) */
  --deep-blue: #1E3A8A;   /* links, focus ring, info */
  --aqua: #71CACD;        /* single accent: chips, highlights, the "revival" side */
  --aqua-200: #DBF2F3;    /* accent fill */
  --mist: #F0F5FC;        /* section fills (most used background) */
  --paper: #F7F9FD;       /* page background */
  --white: #FFFFFF;       /* cards */
  /* text */
  --ink: #0A1833;         /* body text */
  --fg-2: #354972;        /* secondary text */
  --fg-3: #6C7FA0;        /* meta, labels */
  --border-1: #DCE3EE;    /* hairlines */
  --border-2: #BAC5D8;    /* stronger rules */
  /* court states (meaning, not decoration) */
  --locked: #2F8F6B;      /* LOCKED / match / verified */
  --unsworn: #C28A2B;     /* UNSWORN / flaky / review */
  --struck: #B1454A;      /* STRUCK / PERJURY / mismatch */
  /* type */
  --font-display: "Fraunces", Georgia, serif;   /* titles and the big numbers only */
  --font-sans: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace;
  /* scale */
  --t-12: .75rem; --t-14: .875rem; --t-16: 1rem; --t-20: 1.25rem; --t-24: 1.5rem; --t-32: 2rem; --t-44: 2.75rem; --t-64: 4rem;
  --space: 8px;           /* 8px grid: 8, 16, 24, 32, 48 */
  --radius-sm: 6px; --radius: 10px; --radius-lg: 16px;
  --shadow-1: 0 1px 2px rgba(10,24,51,.06), 0 1px 1px rgba(10,24,51,.04);
  --shadow-2: 0 8px 24px rgba(10,24,51,.08);
}
```

Fonts (free): `<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">`

## Rules
1. Background `--paper`; panels are white cards (`--radius`, `--shadow-1`, 1px `--border-1`). No wood, no brown, no gradients, no textures.
2. One accent only (`--aqua`). Navy for headings and the primary button; everything else is neutral.
3. Color = meaning: green only for LOCKED/match, red only for STRUCK/PERJURY/mismatch, amber only for UNSWORN/flaky. Every state also has a text label (accessibility).
4. Numbers are the hero: fidelity, mismatches, false strikes in `--font-display`, large (`--t-44` to `--t-64`), with the unit and source in small `--fg-3` text under them.
5. Original vs revival: two equal white cards side by side, labeled "Original (2016)" / "Revival (rebuilt today)", same height, the app iframe filling the card; revival card gets a 3px `--aqua` top border.
6. Claim list = a clean table: mono id (`c07`), plain-language claim, state pill (rounded, tinted bg + colored text). PERJURY row: `--struck` left border + pill.
7. Spacing on the 8px grid; generous white space; max 2 font weights per screen.
8. Motion: 150-250 ms ease-out on state changes only (a pill flipping to STRUCK, numbers counting 68 → 0). Respect `prefers-reduced-motion`.
9. Header: navy-900 bar, "MUSÉANCE" in Fraunces, one-line subtitle in Plex; app switcher as segmented control.
10. Must read well on a projector: body ≥ 16px, contrast ≥ 4.5:1, nothing important under 14px.

## Prompt for the P3 coding agent (paste as-is)

> Restyle the MUSÉANCE stage in `court/ui/` using `design/MUSEANCE_STYLE.md` exactly: replace the wood/brown courtroom look with the tokens there (paper background, white cards, navy headings, a single aqua accent, green/amber/red only for LOCKED/UNSWORN/STRUCK). Keep every feature, data source and test unchanged; change only styles, layout spacing and fonts (load Fraunces + IBM Plex from Google Fonts). Make the measured numbers (fidelity, attack mismatches, false strikes) the largest elements, each with its source file in small text. Original and revival as two equal cards side by side. Claim list as a table with mono ids and state pills; PERJURY rows marked red with a text label. Keep the cast small and flat. Check: it must read on a projector (body ≥ 16px, contrast ≥ 4.5:1), work at 1280×720, and pass the existing UI tests. Do not add new colors or fonts. Commit as one PR titled "P3: restyle to MUSÉANCE style".

## Skills that help (Claude Code)
- A frontend design skill (e.g. Anthropic's official `frontend-design` plugin, if installed) for layout and hierarchy.
- An "anti-slop" UI review pass: remove generic AI-looking copy, decorative gradients, invented numbers; every number on screen must come from a repo file.
- Run the UI once with screenshots at 1280×720 and 1920×1080 before merging.
