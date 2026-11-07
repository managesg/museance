import { useId } from 'react';
import type { HootMood } from '../engine/types';
import './hoot.css';

// Two half-arcs with unequal radii: a circle that reads as hand-drawn.
const ring = (cx: number, cy: number, r: number) =>
  `M${cx - r} ${cy}A${r} ${r - 1} 0 1 1 ${cx + r} ${cy}A${r} ${r + 1.5} 0 1 1 ${cx - r} ${cy}Z`;

const foot = (x: number, y: number) =>
  `M${x - 10} ${y - 14}C${x - 16} ${y - 4} ${x - 24} ${y + 4} ${x - 28} ${y + 8}C${x - 20} ${y + 12} ${x - 12} ${y + 9} ${x - 6} ${y + 5}` +
  `C${x - 6} ${y + 10} ${x - 4} ${y + 14} ${x} ${y + 16}C${x + 4} ${y + 13} ${x + 6} ${y + 9} ${x + 6} ${y + 5}` +
  `C${x + 12} ${y + 9} ${x + 20} ${y + 12} ${x + 28} ${y + 8}C${x + 24} ${y + 4} ${x + 16} ${y - 4} ${x + 10} ${y - 14}Z`;

// Shoulders match the head's width so head and body share one silhouette.
const BODY =
  'M190 118C246 118 300 134 306 176C314 232 331 300 323 394C313 452 262 488 192 487C118 486 66 450 58 392C50 300 66 232 74 176C80 134 134 118 190 118Z';
const BODY_SHADE = 'M296 212C320 262 331 330 323 394C313 452 262 488 192 487C252 474 292 434 300 376C308 318 306 260 296 212Z';
const CHEST = 'M190 228C248 228 292 280 296 350C300 420 256 468 190 470C124 468 80 420 84 350C88 280 132 228 190 228Z';
const WING_L = 'M92 214C66 244 52 300 56 356C58 380 64 398 72 410L78 392L86 412L93 392C102 340 108 270 92 214Z';
const WING_R = 'M288 214C314 244 330 302 325 358C323 382 317 400 309 410L302 392L295 412L288 392C278 340 272 270 288 214Z';
const HEAD = 'M190 64C254 62 302 96 307 152C312 210 264 254 190 256C116 254 68 210 74 152C80 96 126 66 190 64Z';
// Outline stops where the head meets the body, so no collar line crosses the chest.
const HEAD_LINE = 'M74 178C72 168 73 160 74 152C80 96 126 66 190 64C254 62 302 96 307 152C308 160 307 168 306 178';
const TUFT_L = 'M146 90Q138 58 124 34Q126 56 120 72Q112 44 96 26Q102 52 104 76Q88 54 70 42Q82 64 90 86Q74 76 56 70Q74 90 98 116Z';
const TUFT_R = 'M234 90Q242 58 256 34Q254 56 260 72Q268 44 284 26Q278 52 276 76Q292 54 310 42Q298 64 290 86Q306 76 324 70Q306 90 282 116Z';
const FACE =
  'M190 134C172 110 146 100 122 104C92 110 78 138 80 166C82 200 106 228 142 236C162 240 178 242 190 244C202 242 218 240 238 236C274 228 298 200 300 166C302 138 288 110 258 104C234 100 208 110 190 134Z';
const BROW_L = 'M94 126C112 110 150 108 180 128C182 134 180 140 174 141C150 128 120 124 94 126Z';
const BROW_R = 'M286 126C268 110 230 108 200 128C198 134 200 140 206 141C230 128 260 124 286 126Z';
const BEAK = 'M190 180C199 181 204 191 200 203L190 226L180 203C176 191 181 181 190 180Z';

const CHEVRONS = [
  [160, 276], [190, 272], [220, 276],
  [116, 300], [146, 298], [176, 300], [206, 298], [236, 300],
  [102, 324], [130, 322], [160, 324], [190, 322], [220, 324], [250, 322],
  [116, 348], [146, 346], [176, 348], [206, 346], [236, 348], [266, 346],
  [104, 372], [132, 370], [160, 372], [190, 370], [220, 372], [250, 370], [278, 372],
  [118, 396], [146, 394], [176, 396], [206, 394], [236, 396], [266, 394],
  [132, 420], [162, 418], [192, 420], [222, 418], [252, 420],
  [154, 444], [184, 442], [214, 444], [242, 442],
]
  .map(([x, y]) => `M${x - 6} ${y - 4}Q${x} ${y + 7} ${x + 6} ${y - 4}`)
  .join('');

function Eye({ cx, side, clip }: { cx: number; side: 'l' | 'r'; clip: string }) {
  const cy = 170;
  const lidEdge = `M${cx - 40} ${cy - 28}Q${cx} ${cy - 20} ${cx + 40} ${cy - 28}`;
  return (
    <>
      <clipPath id={clip}>
        <path d={ring(cx, cy, 26)} />
      </clipPath>
      <g clipPath={`url(#${clip})`}>
        <path d={ring(cx, cy, 26)} fill="var(--paper)" stroke="none" />
        <g className="hoot-pupil" stroke="none">
          <circle cx={cx} cy={cy + 2} r={12} fill="var(--ink)" />
          <circle cx={cx - 4} cy={cy - 3} r={3.5} fill="var(--paper)" />
        </g>
        <g className={`hoot-lidtilt hoot-lidtilt--${side}`}>
          <g className={`hoot-lid hoot-lid--${side}`}>
            <g className="hoot-blink">
              <path d={`M${cx - 40} ${cy - 170}H${cx + 40}V${cy - 28}Q${cx} ${cy - 20} ${cx - 40} ${cy - 28}Z`} fill="var(--owl-cream)" stroke="none" />
              <path d={lidEdge} fill="none" strokeWidth={4} />
            </g>
          </g>
        </g>
      </g>
      <path d={ring(cx, cy, 26)} fill="none" strokeWidth={3.5} />
    </>
  );
}

export function DrHoot({ mood }: { mood: HootMood }) {
  const id = useId();
  return (
    <svg
      className={`hoot hoot--${mood}`}
      viewBox="0 0 380 520"
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMax meet"
      role="img"
    >
      <title>{`Dr. Hoot, the skeptic, ${mood}`}</title>
      <ellipse cx={192} cy={494} rx={132} ry={14} fill="var(--floor-shadow)" />
      <g className="hoot-breath" stroke="var(--ink)" strokeWidth={5} strokeLinecap="round" strokeLinejoin="round">
        <path d={foot(152, 490) + foot(232, 490)} fill="var(--brass-deep)" strokeWidth={4} />
        <path d={BODY} fill="var(--owl)" stroke="none" />
        <path d={BODY_SHADE} fill="var(--hoot-deep)" stroke="none" />
        <path d={CHEST} fill="var(--hoot-chest)" stroke="none" />
        <path d={CHEVRONS} fill="none" stroke="var(--hoot-deep)" strokeWidth={3} />
        <path d={BODY} fill="none" />
        <path className="hoot-wing hoot-wing--l" d={WING_L} fill="var(--hoot-deep)" strokeWidth={4.5} />
        <path className="hoot-wing hoot-wing--r" d={WING_R} fill="var(--hoot-deep)" strokeWidth={4.5} />

        <g className="hoot-head">
          <g className="hoot-nod">
            <g className="hoot-tufts" fill="var(--hoot-deep)" strokeWidth={4.5}>
              <path d={TUFT_L} />
              <path d={TUFT_R} />
            </g>
            <path d={HEAD} fill="var(--owl)" stroke="none" />
            <path d={HEAD_LINE} fill="none" />
            <path d="M158 80q4 6 4 12M190 74q1 6 0 13M222 80q-4 6 -4 12" fill="none" strokeWidth={3} />
            <path d={FACE} fill="var(--owl-cream)" strokeWidth={3.5} />
            <path d="M112 226L108 233M136 236L134 244M244 236L246 244M268 226L272 233" fill="none" strokeWidth={3} />
            <Eye cx={140} side="l" clip={`${id}l`} />
            <Eye cx={240} side="r" clip={`${id}r`} />
            <path d={BEAK} fill="var(--hoot-deep)" strokeWidth={4} />
            <path d="M186 188Q183 196 186 204" fill="none" stroke="var(--owl)" strokeWidth={2.5} />
            <g fill="none">
              <path d={ring(140, 170, 38) + ring(240, 170, 38)} strokeWidth={6} />
              <path d="M178 166C184 156 196 156 202 166M102 164L78 154M278 164L302 154" strokeWidth={5} />
              <path d="M112 150Q118 141 128 137M212 150Q218 141 228 137" stroke="var(--paper)" strokeWidth={2.5} />
            </g>
            <path className="hoot-brow hoot-brow--l" d={BROW_L} fill="var(--hoot-deep)" strokeWidth={3.5} />
            <path className="hoot-brow hoot-brow--r" d={BROW_R} fill="var(--hoot-deep)" strokeWidth={3.5} />
          </g>
        </g>

        <g transform="rotate(-18 252 343)">
          <path
            d="M202 268L300 266Q306 266 306 272L308 414Q308 420 302 420L204 422Q198 422 198 416L196 274Q196 268 202 268Z"
            fill="var(--wood)"
            strokeWidth={4.5}
          />
          <path d="M208 282L296 281L298 408L209 410Z" fill="var(--paper)" strokeWidth={3} />
          <path d="M288 281.2L296 281L298 408L290 408.2Z" fill="var(--paper-deep)" stroke="none" />
          <path d="M218 298H262" stroke="var(--slate)" strokeWidth={4} />
          <path d="M218 314H284M218 328H276" stroke="var(--floor-shadow)" strokeWidth={3} />
          <g className="hoot-scribbles" fill="none" strokeWidth={2.5}>
            <path pathLength={1} d="M218 346q5 -6 10 0t10 0t10 0t10 0t10 0t10 0" />
            <path pathLength={1} d="M218 362q5 -6 10 0t10 0t10 0t10 0t10 0" />
            <path pathLength={1} d="M218 378q5 -6 10 0t10 0t10 0" />
          </g>
          <path className="hoot-check" pathLength={1} d="M232 374L246 390L278 350" fill="none" stroke="var(--crimson)" strokeWidth={6} />
          <path d="M232 256H272Q277 256 277 261V276H227V261Q227 256 232 256Z" fill="var(--slate)" strokeWidth={4} />
          <path d="M229.5 269H274.5V273.5H229.5Z" fill="var(--slate-deep)" stroke="none" />
          <path d="M244 256Q252 244 260 256" fill="none" strokeWidth={4} />
        </g>

        <g className="hoot-hand hoot-hand--l">
          <g className="hoot-hand-act">
            <g className="hoot-stick">
              <path d="M64.2 326.4L73 324.6L31.6 119.1L25.8 120.3Z" fill="var(--wood-light)" strokeWidth={4} />
              <path d="M67 318L31 128" stroke="var(--wood)" strokeWidth={2.5} />
              <path d={ring(27, 110, 8.5)} fill="var(--wood-light)" strokeWidth={4} />
            </g>
            <g className="hoot-pencil" strokeWidth={3}>
              <path d="M63.8 293.6L91 335.5L83.5 340.4L56.2 298.5Z" fill="var(--beak)" />
              <path d="M91 335.5L93.8 348L83.5 340.4Z" fill="var(--wax)" />
              <path d="M93 343.8L93.8 348L90.3 345.5Z" fill="var(--ink)" stroke="none" />
            </g>
            <path
              d="M42 290C44 276 64 270 78 278C88 284 88 296 84 302C90 308 88 320 80 324C70 330 54 328 46 320C38 312 38 300 42 290Z"
              fill="var(--hoot-deep)"
              strokeWidth={4.5}
            />
            <path d="M84 302C76 303 70 300 64 294M80 324C74 318 68 316 60 317" fill="none" strokeWidth={3} />
          </g>
        </g>

        <g className="hoot-hand hoot-hand--r">
          <g className="hoot-watch">
            <path className="hoot-clicks" d="M320 262V252M306 266L299 259M334 266L341 259" fill="none" strokeWidth={3.5} />
            <g className="hoot-crown" fill="var(--brass)" strokeWidth={3}>
              <path d="M317 274H323V282H317Z" />
              <path d="M313 269H327V275H313Z" />
            </g>
            <path d="M331 284L336 279L340 283L335 288Z" fill="var(--brass)" strokeWidth={3} />
            <path d={ring(320, 300, 19)} fill="var(--brass)" stroke="none" />
            <path d="M337.9 293.5A19 19 0 0 1 310.5 316.5A24 24 0 0 0 337.9 293.5Z" fill="var(--brass-deep)" stroke="none" />
            <path d={ring(320, 300, 19)} fill="none" strokeWidth={4} />
            <path d={ring(320, 300, 13)} fill="var(--wax)" strokeWidth={2.5} />
            <path d="M320 289V292.5M331 300H327.5M320 311V307.5M309 300H312.5" strokeWidth={2.5} />
            <path className="hoot-needle" d="M320 300V290.5" stroke="var(--crimson)" strokeWidth={3} />
            <circle cx={320} cy={300} r={2.2} fill="var(--ink)" stroke="none" />
          </g>
          <path
            d="M292 330C294 318 312 316 324 322C336 328 338 344 332 354C326 364 308 366 298 360C288 354 288 342 292 330Z"
            fill="var(--hoot-deep)"
            strokeWidth={4.5}
          />
          <path d="M300 330C308 336 316 338 326 334M296 344C304 350 316 351 330 347" fill="none" strokeWidth={3} />
        </g>
      </g>
    </svg>
  );
}
