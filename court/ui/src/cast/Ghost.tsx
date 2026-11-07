import { useId } from 'react';
import type { GhostMood } from '../engine/types';
import './ghost.css';

// One silhouette serves the fill, the cel shade, the outline, the relieved glow and the glitch split.
const BODY =
  'M198 96C257 93 303 137 307 199C310 236 318 264 338 292C356 318 372 348 376 384C366 394 350 398 340 394C331 419 314 435 298 433C284 431 276 419 271 406C263 429 247 447 229 445C213 443 205 429 200 415C192 433 177 445 161 441C146 437 138 425 133 411C125 429 110 437 95 431C81 425 75 411 72 398C60 404 40 400 26 388C30 352 46 322 62 296C80 266 90 238 93 200C96 137 140 98 198 96Z';
const FOLDS =
  'M264 424C268 388 276 352 290 318C286 352 283 388 283 424ZM195 430C197 392 202 360 211 330C210 362 210 396 211 430ZM126 428C125 390 123 362 116 336C127 362 135 392 141 426Z';
const FOLD_LINES = 'M270 406C272 393 275 383 280 372M200 415C201 402 203 392 207 382M134 411C132 399 129 389 125 379';
// Hem mask: opaque above this wave, sheer below it (white + alpha keeps the luminance exact in every browser).
const ABOVE_HEM =
  'M0 0H400V356C376 356 352 358 335 364C318 372 308 388 296 388C284 388 278 374 270 372C258 380 244 398 228 398C214 398 206 382 200 380C190 386 176 396 161 396C148 396 140 380 134 378C122 384 108 390 97 388C86 386 82 370 76 368C56 362 26 360 0 360Z';
const TILE =
  'M-30 -48L4 -48L11 -39L17 -48L30 -47Q48 -47 48 -29L47 30Q47 48 29 48L-29 47Q-48 47 -47 29L-48 -30Q-48 -48 -30 -48Z';
const TILE_SHADE = 'M-47 24L47 25L47 30Q47 48 29 48L-29 47Q-48 47 -47 29Z';
// Runs right of the glyph's centre line so the cracked sign stays legible.
const CRACK = 'M11 -39L17 -27L9 -17L18 -5L10 7L17 19L8 33L13 47M18 -5L32 -12L47 -8';

const ink = (w: number) => ({ fill: 'none', stroke: 'var(--ink)', strokeWidth: w });

// Left eye in local coords; the right one is its mirror so both lids droop outward.
const LIDDED_EYE = (
  <>
    <path d="M-11.9 -2L10.4 -8A12 16 0 1 1 -11.9 -2Z" fill="var(--ink)" />
    <path d="M-16 1Q-3 -7 14 -11" {...ink(4.5)} />
    <circle cx="-2" cy="5" r="3.5" fill="var(--paper)" />
  </>
);

export function Ghost({ mood, appGlyph }: { mood: GhostMood; appGlyph?: string }) {
  const id = useId();
  const glyph = appGlyph?.trim();
  const longGlyph = !!glyph && [...glyph].length > 2;
  return (
    <svg
      className={`ghost ghost--${mood}`}
      viewBox="0 0 400 480"
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMax meet"
      role="img"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <title>{`The Departed, ${mood}`}</title>
      <defs>
        <clipPath id={`${id}clip`}>
          <path d={BODY} />
        </clipPath>
        <mask id={`${id}hem`} maskUnits="userSpaceOnUse" x="0" y="0" width="400" height="480">
          <rect y="300" width="400" height="180" fill="#fff" fillOpacity="0.55" />
          <path d={ABOVE_HEM} fill="#fff" />
        </mask>
      </defs>
      {/* Static nudge: keeps headroom for the hat when the ghost bobs and lifts. */}
      <g transform="translate(0 16)">
        <g className="ghost__rig">
          <g className="ghost__float">
            <g className="ghost__flicker">
              <g className="ghost__body">
                <g className="ghost__glow" fill="var(--flame-core)">
                  <path d={BODY} opacity="0.14" transform="translate(200 300) scale(1.16 1.08) translate(-200 -300)" />
                  <path d={BODY} opacity="0.22" transform="translate(200 300) scale(1.08 1.04) translate(-200 -300)" />
                </g>
                <path className="ghost__split-a" d={BODY} fill="var(--glitch-a)" />
                <path className="ghost__split-b" d={BODY} fill="var(--glitch-b)" />
                <g className="ghost__sheet" mask={`url(#${id}hem)`}>
                  <g clipPath={`url(#${id}clip)`}>
                    <path d={BODY} fill="var(--ghost-shade)" />
                    <path d={BODY} fill="var(--ghost)" transform="translate(-12 -7)" />
                    <path d={FOLDS} fill="var(--ghost-shade)" />
                  </g>
                  <path d={FOLD_LINES} {...ink(3.5)} />
                  <path d={BODY} {...ink(6)} />
                </g>
                <g className="ghost__face">
                  <path className="ghost__brow ghost__brow--l" d="M150 186C160 182 170 180 181 181" {...ink(7)} />
                  <path className="ghost__brow ghost__brow--r" d="M219 181C230 180 240 182 250 186" {...ink(7)} />
                  <g className="ghost__var ghost__eyes--open">
                    <ellipse cx="168" cy="220" rx="12" ry="16" fill="var(--ink)" />
                    <ellipse cx="232" cy="220" rx="12" ry="16" fill="var(--ink)" />
                    <g fill="var(--paper)">
                      <circle cx="163" cy="213" r="4.5" />
                      <circle cx="227" cy="213" r="4.5" />
                      <circle cx="172" cy="228" r="2" />
                      <circle cx="236" cy="228" r="2" />
                    </g>
                  </g>
                  <g className="ghost__var ghost__eyes--lidded">
                    <g transform="translate(168 223)">{LIDDED_EYE}</g>
                    <g transform="translate(232 223) scale(-1 1)">{LIDDED_EYE}</g>
                  </g>
                  <path
                    className="ghost__var ghost__eyes--closed"
                    d="M155 219Q168 231 181 219M219 219Q232 231 245 219"
                    {...ink(6)}
                  />
                  <path className="ghost__var ghost__mouth--frown" d="M184 262Q200 246 216 262" {...ink(6)} />
                  <path className="ghost__var ghost__mouth--smile" d="M184 252Q200 268 216 252" {...ink(6)} />
                  <ellipse className="ghost__var ghost__mouth--gasp" cx="200" cy="258" rx="8" ry="10" fill="var(--ink)" />
                </g>
                <g className="ghost__hat">
                  <g transform="translate(220 70) rotate(12)">
                    <path d={TILE} fill="var(--terracotta)" />
                    <path d={TILE_SHADE} fill="var(--terracotta-deep)" />
                    {glyph ? (
                      <text
                        className="ghost__glyph"
                        y="-4"
                        textAnchor="middle"
                        dominantBaseline="central"
                        fontSize="54"
                        fill="var(--paper)"
                        textLength={longGlyph ? 76 : undefined}
                        lengthAdjust={longGlyph ? 'spacingAndGlyphs' : undefined}
                      >
                        {glyph}
                      </text>
                    ) : (
                      <g fill="var(--paper)">
                        <path d="M-21 -3L21 -5" stroke="var(--paper)" strokeWidth="10" />
                        <circle cx="-1" cy="-23" r="6.5" />
                        <circle cx="1" cy="15" r="6.5" />
                      </g>
                    )}
                    <path d={CRACK} {...ink(4)} />
                    <path d={TILE} {...ink(5)} />
                  </g>
                </g>
              </g>
            </g>
          </g>
        </g>
      </g>
    </svg>
  );
}
