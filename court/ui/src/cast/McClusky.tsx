import { useId, type CSSProperties } from 'react';
import type { McCluskyMood } from '../engine/types';
import './mcclusky.css';

const TITLE: Record<McCluskyMood, string> = {
  idle: 'McClusky, Esq., penguin barrister, waiting at the bar',
  swearing: 'McClusky, Esq., raising his candle to swear a claim',
  nervous: 'McClusky, Esq., sweating and glancing sideways',
  caught: 'McClusky, Esq., caught out, his wig popping off',
  fainted: 'McClusky, Esq., fainted flat on his back',
  relieved: 'McClusky, Esq., sighing with relief',
};

// Art data, drawn in the 420x520 viewBox; floor line at y 496.
const TAIL = 'M 150 258 C 108 262, 78 290, 64 330 C 52 366, 52 396, 38 420 L 64 432 C 76 404, 80 372, 90 342 C 102 308, 124 292, 154 290 Z';
const TAIL_SHADE = 'M 154 290 C 124 292, 102 308, 90 342 C 80 372, 76 404, 64 432 L 55 428 C 66 400, 70 368, 80 336 C 92 302, 118 282, 152 279 Z';
const TAIL_FRINGE = 'M 41 422 l -6 13 M 48 425 l -6 13 M 55 428 l -6 13 M 62 431 l -6 13';
const FOOT_FAR = 'M 142 474 C 164 468, 198 470, 222 478 C 234 480, 240 488, 234 494 C 226 499, 216 498, 210 495 C 202 500, 190 500, 184 496 C 174 500, 160 500, 152 495 C 138 492, 132 480, 142 474 Z';
const FOOT_NEAR = 'M 214 476 C 240 468, 278 470, 302 480 C 316 482, 322 490, 316 497 C 308 502, 296 502, 290 498 C 282 503, 268 503, 262 499 C 252 503, 236 503, 228 498 C 212 495, 206 482, 214 476 Z';
const BODY = 'M 208 238 C 258 236, 302 276, 316 334 C 328 388, 324 446, 294 472 C 270 490, 226 492, 186 490 C 142 488, 106 472, 94 440 C 78 398, 82 332, 110 290 C 132 256, 168 240, 208 238 Z';
const BELLY = 'M 226 262 C 272 268, 304 316, 309 372 C 314 428, 292 470, 248 478 C 214 484, 182 478, 166 458 C 146 432, 148 372, 166 326 C 180 290, 200 260, 226 262 Z';
const BELLY_SHADE = 'M 168 330 C 154 374, 156 432, 178 458 C 198 478, 232 482, 258 476 C 220 470, 192 446, 184 410 C 178 382, 178 354, 168 330 Z';
const HEAD = 'M 216 124 C 258 122, 290 156, 290 198 C 290 238, 260 266, 218 268 C 176 270, 144 240, 142 198 C 140 158, 174 126, 216 124 Z';
const FACE = 'M 240 148 C 266 148, 288 172, 289 202 C 290 232, 274 258, 250 266 C 230 272, 210 262, 208 244 C 206 226, 218 212, 220 192 C 222 170, 224 150, 240 148 Z';
const EYE = 'M 254 184 C 264 184, 270 193, 270 203 C 270 213, 263 221, 254 220 C 245 220, 239 211, 239 202 C 239 192, 245 184, 254 184 Z';
const PUPIL = 'M 258 195 C 263 195, 267 199, 267 204 C 267 209, 263 213, 258 213 C 253 213, 249 209, 249 204 C 249 199, 253 195, 258 195 Z';
const BEAK = 'M 278 204 C 294 200, 316 206, 332 220 C 318 227, 298 229, 282 227 C 274 221, 273 210, 278 204 Z';
const JAW = 'M 282 227 C 298 229, 314 227, 326 224 C 318 236, 302 241, 288 239 C 281 237, 278 231, 282 227 Z';
const WIG = 'M 178 262 C 177.2 271.5, 162.6 278.1, 156 272 C 147.7 277.9, 133.2 270, 134 260 C 123 259.4, 115.4 242.8, 122 234 C 110.9 229.8, 109 210.2, 119 204 C 107.9 198.3, 110.8 176.9, 123 174 C 114.4 165, 122.1 145.4, 134 146 C 128.2 135.5, 139.9 121.2, 152 124 C 148.4 112.3, 165.4 100.2, 176 107 C 177.2 93.8, 195.5 88, 204 98 C 209.8 87.5, 227 88.1, 232 99 C 239.3 91.4, 255.3 98, 256 109 C 265.4 105.2, 276.3 118.2, 271 127 C 281.4 128.6, 283.4 142.5, 274 148 C 271.9 153.1, 259.3 158.2, 254 156 C 251.9 160.1, 236.6 164.9, 232 163 C 231.7 168.3, 218.9 179, 214 178 C 216.8 182.9, 208.8 200.3, 203 202 C 205.3 207.7, 200.9 225.5, 196 230 C 198.6 234.3, 192.9 250, 188 252 C 189 256, 182.1 263, 178 262 Z';
const WIG_SHADE = 'M 274 148 C 262 154, 242 160, 228 166 C 212 176, 204 196, 198 222 C 194 240, 188 254, 178 262 C 168 270, 150 276, 134 260 C 150 262, 164 254, 172 240 C 180 222, 184 196, 196 176 C 210 156, 240 146, 274 140 Z';
// Two tiers of rolled curls, inset from the outline.
const WIG_ROWS =
  'M 148.4 247.2 C 141.3 246.7, 134.6 232.1, 138.8 226.4 C 130.8 223.6, 129.2 206.8, 136.4 202.4 C 129.7 197.8, 132 181, 139.6 178.4 C 135 172.7, 141.1 157, 148.4 156 C 143.7 147.7, 153.7 135.4, 162.8 138.4 C 161.3 130.2, 174.8 120.7, 182 124.8 C 183 116.2, 198.6 111.2, 204.4 117.6 C 208 110, 223.7 110.6, 226.8 118.4 C 232.6 112.5, 246.1 118.1, 246 126.4 C 253.3 124, 261.7 134.1, 258 140.8 ' +
  'M 155.6 218.8 C 149.6 216.7, 148.3 204.1, 153.8 200.8 C 147.2 197.2, 148.8 184.6, 156.2 182.8 C 152 178.2, 156.6 166.5, 162.8 166 C 159.6 160.1, 167.2 150.9, 173.6 152.8 C 171.9 145.8, 182 138.6, 188 142.6 C 188.3 134.8, 200 131, 204.8 137.2 C 207.5 131.1, 219.3 131.5, 221.6 137.8 C 225.8 133.7, 235.9 137.9, 236 143.8';
const WRAP_1 = 'M 150 242 C 188 230, 248 234, 290 250 C 300 258, 298 270, 288 274 C 244 264, 188 262, 154 268 C 140 264, 138 248, 150 242 Z';
const WRAP_1_SHADE = 'M 154 268 C 188 262, 244 264, 288 274 C 292 272, 295 268, 296 264 C 250 254, 190 252, 146 258 C 147 263, 150 266, 154 268 Z';
const WRAP_2 = 'M 142 264 C 182 254, 250 258, 298 274 C 308 284, 304 298, 292 300 C 244 290, 184 288, 146 294 C 132 288, 130 272, 142 264 Z';
const WRAP_2_RIBS = 'M 170 262 l 0 28 M 196 259 l 0 30 M 222 260 l 1 30 M 248 263 l 1 29 M 272 268 l 1 27';
const WRAP_3 = 'M 138 288 C 180 280, 252 284, 302 300 C 312 310, 308 324, 294 326 C 244 316, 182 314, 142 320 C 126 314, 126 298, 138 288 Z';
const WRAP_3_SHADE = 'M 142 320 C 182 314, 244 316, 294 326 C 300 324, 304 320, 306 316 C 252 304, 186 302, 134 310 C 136 316, 139 319, 142 320 Z';
const KNOT = 'M 236 296 C 250 288, 270 290, 276 304 C 282 318, 272 330, 256 330 C 240 330, 230 318, 232 306 C 232 302, 233 298, 236 296 Z';
const TAIL_A = 'M 240 320 C 236 342, 230 362, 222 382 L 248 390 C 252 366, 256 344, 260 326 Z';
const TAIL_A_SHADE = 'M 252 323 C 249 344, 246 366, 242 388 L 248 390 C 252 366, 256 344, 260 326 Z';
const TAIL_B = 'M 260 326 C 266 344, 272 360, 276 378 L 300 370 C 292 354, 284 338, 278 320 Z';
const TAIL_B_SHADE = 'M 266 324 C 272 342, 278 358, 284 375 L 276 378 C 272 360, 266 344, 260 326 Z';
const FLIPPER_B = 'M 130 288 C 108 300, 92 342, 92 382 C 92 410, 108 432, 130 438 C 142 432, 148 412, 150 384 C 152 346, 152 304, 130 288 Z';
const BOARD = 'M 134 356 L 194 354 C 198 354, 200 357, 200 361 L 201 446 C 201 450, 198 453, 194 453 L 136 454 C 132 454, 129 451, 129 447 L 128 362 C 128 358, 130 356, 134 356 Z';
const CLIP = 'M 150 362 L 150 350 C 150 344, 156 341, 164 341 C 172 341, 178 344, 178 350 L 178 362 Z';
const FLIPPER_C = 'M 280 304 C 304 298, 334 322, 352 352 C 362 368, 366 382, 356 388 C 344 392, 324 380, 306 364 C 290 350, 270 330, 280 304 Z';
const BASE = 'M 330 424 C 332 412, 344 406, 358 406 C 372 406, 384 412, 386 424 C 376 431, 340 431, 330 424 Z';
const STEM = 'M 352 406 L 352 398 C 346 396, 346 388, 352 386 L 353 356 C 347 354, 347 346, 353 344 L 354 334 L 362 334 L 363 344 C 369 346, 369 354, 363 356 L 364 386 C 370 388, 370 396, 364 398 L 364 406 Z';
const CANDLE = 'M 349 330 L 349 268 C 349 263, 353 261, 358 262 C 363 261, 367 263, 367 268 L 367 330 Z';
const FLAME = 'M 358 210 C 364 222, 372 234, 371 244 C 370 254, 364 259, 358 259 C 352 259, 346 254, 345 244 C 344 234, 352 222, 358 210 Z';
const FLAME_CORE = 'M 358 230 C 362 237, 365 243, 364 248 C 363 253, 361 255, 358 255 C 355 255, 353 253, 352 248 C 351 243, 354 237, 358 230 Z';
const DROP = 'M 0 -14 C 4 -6, 9 0, 9 6 C 9 12, 5 15, 0 15 C -5 15, -9 12, -9 6 C -9 0, -4 -6, 0 -14 Z';
const DROPS: readonly (readonly [number, number, number])[] = [[110, 150, -24], [294, 136, 22], [102, 198, -34], [308, 178, 30]];
const FLOOR_SCARF = 'M 204 480 C 176 470, 150 488, 122 482 C 96 476, 66 486, 40 484 C 30 484, 22 490, 24 497 C 44 508, 72 500, 98 504 C 128 509, 160 498, 206 504 Z';

export function McClusky({ mood, stress }: { mood: McCluskyMood; stress: number }) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const s = Number.isFinite(stress) ? Math.min(1, Math.max(0, stress)) : 0;
  const minDrops = mood === 'nervous' ? 2 : mood === 'caught' ? 3 : 0;
  const drops = mood === 'fainted' ? 0 : Math.max(Math.round(s * 4), minDrops);

  return (
    <svg
      className={`mcc is-${mood}`}
      viewBox="0 0 420 520"
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMax meet"
      role="img"
      aria-labelledby={`${uid}-title`}
      style={{ '--mcc-stress': s } as CSSProperties}
    >
      <title id={`${uid}-title`}>{TITLE[mood]}</title>
      <defs>
        <radialGradient id={`${uid}-glow`}>
          <stop offset="0" stopColor="var(--flame-core)" stopOpacity={0.8} />
          <stop offset="0.45" stopColor="var(--flame)" stopOpacity={0.3} />
          <stop offset="1" stopColor="var(--flame)" stopOpacity={0} />
        </radialGradient>
      </defs>

      <ellipse className="mcc-shadow" cx={200} cy={496} rx={150} ry={17} fill="var(--floor-shadow)" />

      <g className="mcc-pose" stroke="var(--ink)" strokeWidth={5} strokeLinecap="round" strokeLinejoin="round">
        <g className="mcc-sway">
          <g className="mcc-breathe">
            <g className="mcc-tail">
              <path d={TAIL} fill="var(--crimson)" stroke="none" />
              <path d={TAIL_SHADE} fill="var(--crimson-deep)" stroke="none" />
              <path d={TAIL} fill="none" />
              <path d={TAIL_FRINGE} fill="none" strokeWidth={4} />
            </g>

            <g className="mcc-feet">
              <path d={FOOT_FAR} fill="var(--mcc-beak-shade)" />
              <path d="M 210 495 l -4 -8 M 184 496 l -3 -8" fill="none" strokeWidth={4} />
              <g className="mcc-foot-near">
                <path d={FOOT_NEAR} fill="var(--beak)" />
                <path d="M 290 498 l -5 -9 M 262 499 l -3 -9" fill="none" strokeWidth={4} />
              </g>
            </g>

            <path d={BODY} fill="var(--penguin)" />
            <path d={BELLY} fill="var(--belly)" stroke="none" />
            <path d={BELLY_SHADE} fill="var(--mcc-belly-shade)" stroke="none" />
            <path d={BELLY} fill="none" strokeWidth={4.5} />

            <g className="mcc-head">
              <path d={HEAD} fill="var(--penguin)" />
              <path d={FACE} fill="var(--belly)" strokeWidth={4.5} />
              <g className="mcc-eye-size">
                <g className="mcc-eye-open">
                  <g className="mcc-blink">
                    <path d={EYE} fill="var(--belly)" strokeWidth={4.5} />
                    <g className="mcc-pupil">
                      <path d={PUPIL} fill="var(--penguin)" stroke="none" />
                      <circle cx={261.5} cy={199.5} r={3.2} fill="var(--belly)" stroke="none" />
                    </g>
                  </g>
                </g>
                <path className="mcc-eye-shut" d="M 240 207 C 246 195, 262 194, 269 205" fill="none" strokeWidth={6} />
                <path className="mcc-eye-x" d="M 243 191 L 266 214 M 265 190 L 243 214" fill="none" strokeWidth={6} />
              </g>
              <path className="mcc-brow" d="M 238 175 C 247 169, 260 168, 270 172" fill="none" strokeWidth={7} />
              <path d="M 284 227 L 326 222 L 318 239 Z" fill="var(--crimson-deep)" strokeWidth={4} />
              <path className="mcc-jaw" d={JAW} fill="var(--mcc-beak-shade)" />
              <path d={BEAK} fill="var(--beak)" />
              <path d="M 294 211 C 297 210, 300 210, 302 211" fill="none" strokeWidth={4} />
              <path
                className="mcc-puff"
                d="M 318 186 C 314 178, 322 172, 328 176 C 330 168, 342 168, 344 176 C 352 176, 354 186, 346 190 C 342 196, 326 196, 322 192 C 316 192, 314 188, 318 186 Z"
                fill="var(--ghost)"
                strokeWidth={4}
              />
              <g className="mcc-wig">
                <path d={WIG} fill="var(--wig)" stroke="none" />
                <path d={WIG_SHADE} fill="var(--mcc-wig-shade)" stroke="none" />
                <path d={WIG_ROWS} fill="none" stroke="var(--mcc-wig-shade)" strokeWidth={4} />
                <path d={WIG} fill="none" />
              </g>
            </g>

            <g className="mcc-scarves">
              <path d={WRAP_1} fill="var(--crimson)" stroke="none" />
              <path d={WRAP_1_SHADE} fill="var(--crimson-deep)" stroke="none" />
              <path d={WRAP_1} fill="none" />
              <path d={WRAP_2} fill="var(--crimson-deep)" stroke="none" />
              <path d={WRAP_2_RIBS} fill="none" stroke="var(--crimson)" strokeWidth={5} />
              <path d={WRAP_2} fill="none" />
              <path d={WRAP_3} fill="var(--crimson)" stroke="none" />
              <path d={WRAP_3_SHADE} fill="var(--crimson-deep)" stroke="none" />
              <path d={WRAP_3} fill="none" />
              <g className="mcc-tail-a">
                <path d={TAIL_A} fill="var(--crimson)" stroke="none" />
                <path d={TAIL_A_SHADE} fill="var(--crimson-deep)" stroke="none" />
                <path d={TAIL_A} fill="none" />
                <path d="M 225 384 l -2 13 M 232 386 l -1 13 M 239 388 l -1 13 M 246 390 l 0 12" fill="none" strokeWidth={4} />
              </g>
              <g className="mcc-tail-b">
                <path d={TAIL_B} fill="var(--crimson)" stroke="none" />
                <path d={TAIL_B_SHADE} fill="var(--crimson-deep)" stroke="none" />
                <path d={TAIL_B} fill="none" />
                <path d="M 279 377 l 2 13 M 286 375 l 3 12 M 293 373 l 3 12" fill="none" strokeWidth={4} />
              </g>
              <path d={KNOT} fill="var(--crimson)" />
              <path d="M 246 302 C 252 308, 254 316, 251 324" fill="none" strokeWidth={4} />
            </g>

            <g className="mcc-arm-b">
              <g className="mcc-board">
                <g transform="rotate(-8 164 404)">
                  <path d={BOARD} fill="var(--wood-light)" />
                  <path d="M 192 358 L 197 358 L 198 450 L 192 451 Z" fill="var(--wood)" stroke="none" />
                  <path d="M 138 368 L 191 366 L 192 444 L 139 446 Z" fill="var(--paper)" strokeWidth={4} />
                  <path d="M 146 384 L 182 383 M 146 398 L 178 397 M 146 412 L 184 411 M 146 426 L 170 425" fill="none" strokeWidth={4} />
                  <path d={CLIP} fill="var(--brass)" />
                  <path d="M 152 355 L 176 355 L 176 360 L 152 360 Z" fill="var(--brass-deep)" stroke="none" />
                  <circle cx={164} cy={349} r={3.2} fill="var(--ink)" stroke="none" />
                </g>
              </g>
              <path d={FLIPPER_B} fill="var(--penguin)" />
              <path d="M 108 328 C 102 356, 102 390, 112 418" fill="none" stroke="var(--mcc-sheen)" strokeWidth={4} />
            </g>

            <g className="mcc-arm-c">
              <g className="mcc-stick">
                <path d={BASE} fill="var(--brass)" />
                <path d="M 336 424 C 348 428, 368 428, 380 424 L 381 426 C 370 430, 346 430, 335 426 Z" fill="var(--brass-deep)" stroke="none" />
                <path d={STEM} fill="var(--brass)" />
                <path d="M 359 336 L 361 336 L 362 345 C 367 347, 367 353, 362 355 L 363 387 C 368 389, 368 395, 363 397 L 363 404 L 359 404 Z" fill="var(--brass-deep)" stroke="none" />
                <path d="M 336 334 C 340 326, 376 326, 380 334 C 376 341, 340 341, 336 334 Z" fill="var(--brass)" />
                <path d={CANDLE} fill="var(--wax)" />
                <path d="M 361 265 C 364 265, 366 266, 366 269 L 366 329 L 361 329 Z" fill="var(--paper-deep)" stroke="none" />
                <path d="M 358 262 L 358 252" fill="none" strokeWidth={4} />
                <g className="mcc-flame-size">
                  <circle className="mcc-glow" cx={358} cy={236} r={48} fill={`url(#${uid}-glow)`} stroke="none" />
                  <g className="mcc-flame">
                    <path d={FLAME} fill="var(--flame)" strokeWidth={4} />
                    <path d={FLAME_CORE} fill="var(--flame-core)" stroke="none" />
                  </g>
                </g>
                <path className="mcc-smoke" d="M 358 250 C 350 238, 367 230, 359 216 C 352 204, 366 196, 361 182" fill="none" stroke="var(--smoke)" strokeWidth={6} />
              </g>
              <path d={FLIPPER_C} fill="var(--penguin)" />
              <path d="M 300 320 C 318 330, 334 346, 344 362" fill="none" stroke="var(--mcc-sheen)" strokeWidth={4} />
            </g>

            <g className="mcc-sweat">
              {DROPS.slice(0, drops).map(([x, y, r]) => (
                <g key={`${x}-${y}`} transform={`translate(${x} ${y}) rotate(${r})`}>
                  <g className="mcc-drop">
                    <path d={DROP} fill="var(--ghost)" strokeWidth={4} />
                  </g>
                </g>
              ))}
            </g>
            <path className="mcc-shock" d="M 300 112 L 312 94 M 318 140 L 338 130 M 324 168 L 344 164" fill="none" strokeWidth={6} />
          </g>
        </g>
      </g>

      <g className="mcc-floor-scarf" stroke="var(--ink)" strokeWidth={5} strokeLinecap="round" strokeLinejoin="round">
        <path d={FLOOR_SCARF} fill="var(--crimson)" />
        <path d="M 120 494 C 140 488, 160 492, 178 488" fill="none" stroke="var(--crimson-deep)" strokeWidth={6} />
        <path d="M 26 488 l -12 -2 M 24 494 l -12 0 M 26 500 l -11 3" fill="none" strokeWidth={4} />
      </g>
    </svg>
  );
}
