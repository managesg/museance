import { useId } from 'react';
import type { StenoMood } from '../engine/types';
import './steno.css';

const TITLE: Record<StenoMood, string> = {
  idle: 'The stenographer, a blue owl in red glasses, waits with a clipboard',
  scribbling: 'The stenographer scribbles the record onto a curl of paper tape',
  sealing: 'The stenographer presses a brass seal onto the paper tape',
};

const BODY =
  'M86 52C98 60 112 66 128 66C144 64 162 64 178 65C194 66 206 60 218 50C228 68 236 90 238 116C244 160 248 214 240 262C230 304 198 328 152 329C106 330 72 306 64 262C56 214 60 160 68 114C72 88 78 68 86 52Z';

// Tape centre line in clipboard space: off the paper, then a loose curl that never crosses itself.
const TAPE = 'M16 20C16 38 15 52 13 64C10 82 -4 96 -26 100C-48 104 -66 96 -72 80C-78 64 -64 54 -52 62C-46 66 -46 76 -54 78';

// Four arcs with uneven radii so rims and seals read hand-inked, not compass-drawn.
function ring(x: number, y: number, r: number) {
  const k = r * 0.55, b = y + r + 1, t = y - r - 0.5, l = x - r + 0.5;
  return `M${x + r} ${y}C${x + r} ${y + k} ${x + k} ${b} ${x} ${b}C${x - k} ${b} ${l} ${y + k} ${l} ${y}C${l} ${y - k} ${x - k} ${t} ${x} ${t}C${x + k} ${t} ${x + r} ${y - k} ${x + r} ${y}Z`;
}

const RIMS = `${ring(114, 116, 25)}${ring(172, 116, 25)}M139 112C142 107 145 107 147.5 112M197 111L240 105M89.5 112L76 109`;

export function Stenographer({ mood }: { mood: StenoMood }) {
  const maskId = `steno-tape-${useId().replace(/[^\w-]/g, '')}`;
  return (
    <svg
      className={`steno steno--${mood}`}
      viewBox="0 0 260 360"
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMax meet"
      role="img"
    >
      <title>{TITLE[mood]}</title>
      <defs>
        <mask id={maskId} maskUnits="userSpaceOnUse" x="-120" y="-120" width="240" height="260">
          {/* Butt-capped reveal stroke, padded past both tape ends so the round caps are never clipped. */}
          <path
            className="steno-tape-reveal"
            d={`M16 6L${TAPE.slice(1)}L-68 81`}
            pathLength={1}
            fill="none"
            stroke="#fff"
            strokeWidth="18"
            strokeDasharray="1 2"
            strokeDashoffset="1"
          />
        </mask>
      </defs>

      <ellipse cx="152" cy="341" rx="92" ry="12" fill="var(--floor-shadow)" />

      <g className="steno-owl" stroke="var(--ink)" strokeLinecap="round" strokeLinejoin="round">
        <g fill="var(--beak)" strokeWidth="4.5">
          <path d="M122 312C122 320 121 326 116 330C111 332 106 334 107 338C108 341 114 340 119 337C120 340 124 342 128 340C131 339 131 336 130 334C134 337 139 339 142 337C145 334 141 331 137 329C133 326 132 320 133 312" />
          <path d="M176 312C176 320 175 326 170 330C165 332 160 334 161 338C162 341 168 340 173 337C174 340 178 342 182 340C185 339 185 336 184 334C188 337 193 339 196 337C199 334 195 331 191 329C187 326 186 320 187 312" />
        </g>

        <path d={BODY} fill="var(--slate)" stroke="none" />
        <path
          d="M218 50C228 68 236 90 238 116C244 160 248 214 240 262C230 304 198 328 152 329C190 320 216 294 225 256C232 212 230 160 225 122C222 96 220 72 218 50Z"
          fill="var(--slate-deep)"
          stroke="none"
        />
        <path
          d="M100 172C118 156 188 154 214 174C232 206 232 268 212 302C194 322 118 324 98 302C78 272 80 204 100 172Z"
          fill="var(--steno-belly)"
          stroke="none"
        />
        <path
          d="M157 183q5 8 10 0M180 183q5 8 10 0M201 185q5 8 10 0M147 205q5 8 10 0M170 205q5 8 10 0M193 205q5 8 10 0M211 209q5 8 10 0M159 227q5 8 10 0M182 227q5 8 10 0M204 229q5 8 10 0M149 249q5 8 10 0M172 249q5 8 10 0M195 249q5 8 10 0M137 271q5 8 10 0M160 271q5 8 10 0M183 271q5 8 10 0M125 293q5 8 10 0M148 293q5 8 10 0M171 293q5 8 10 0"
          fill="none"
          stroke="var(--slate-deep)"
          strokeWidth="3"
        />
        <path d={BODY} fill="none" strokeWidth="6" />
        <path d="M138 67l-4-9M145 65v-10M152 66l4-8" fill="none" strokeWidth="3.5" />

        <g className="steno-face">
          <path d={`${ring(114, 116, 23)}${ring(172, 116, 23)}`} fill="var(--steno-belly)" stroke="none" />
          <circle cx="115" cy="118" r="14.5" fill="var(--belly)" strokeWidth="3" />
          <circle cx="171" cy="118" r="14.5" fill="var(--belly)" strokeWidth="3" />
          <g className="steno-pupils" stroke="none">
            <circle cx="113" cy="119" r="8.5" fill="var(--ink)" />
            <circle cx="169" cy="119" r="8.5" fill="var(--ink)" />
            <circle cx="116" cy="115.5" r="2.6" fill="var(--belly)" />
            <circle cx="172" cy="115.5" r="2.6" fill="var(--belly)" />
          </g>
          <circle className="steno-lid" cx="115" cy="118" r="16" fill="var(--slate)" strokeWidth="3" />
          <circle className="steno-lid" cx="171" cy="118" r="16" fill="var(--slate)" strokeWidth="3" />
          <path d={RIMS} fill="none" strokeWidth="10.5" />
          <path d={RIMS} fill="none" stroke="var(--crimson)" strokeWidth="5" />
          <path d="M96 108C98 100 103 95 109 93" fill="none" stroke="var(--belly)" strokeWidth="3" />
          <path d="M132 134C138 130 149 130 154 134C152 145 147 154 143 161C138 153 134 145 132 134Z" fill="var(--beak)" stroke="none" />
          <path d="M143 131.5C148 131 152 132 154 134C152 145 147 154 143 161Z" fill="var(--steno-beak-deep)" stroke="none" />
          <path d="M132 134C138 130 149 130 154 134C152 145 147 154 143 161C138 153 134 145 132 134Z" fill="none" strokeWidth="4" />
        </g>

        <g className="steno-wing-rest">
          <path
            d="M212 158C232 150 252 172 254 216C256 254 250 284 236 302C226 290 218 266 214 238C210 210 208 184 212 158Z"
            fill="var(--slate-deep)"
            strokeWidth="5"
          />
          <path
            d="M220 200q4 6 8 0q4 6 8 0q4 6 8 0M218 222q4 6 8 0q4 6 8 0q4 6 8 0M222 244q4 6 8 0q4 6 8 0M226 266q4 6 8 0q4 6 8 0"
            fill="none"
            strokeWidth="2.5"
          />
        </g>

        <g className="steno-clipboard" transform="translate(92 222) rotate(-16)">
          <path
            d="M-42 -58L42 -59Q46 -59 46 -55L45 56Q45 60 41 60L-41 59Q-45 59 -45 55L-46 -54Q-46 -58 -42 -58Z"
            fill="var(--wood)"
            strokeWidth="5"
          />
          <path d="M-37 -47L37 -48L38 50L-36 51Z" fill="var(--paper)" strokeWidth="3" />
          <path d="M38 38L38 50L26 50Z" fill="var(--paper-deep)" strokeWidth="2.5" />
          <path d="M-28 -32h54M-28 -22h48M-28 -12h56M-28 -2h42M-28 8h52M-28 18h32M-28 28h28M-28 38h20" fill="none" strokeWidth="2.4" />
          <path
            d="M-17 -66Q-17 -70 -13 -70L13 -70Q17 -70 17 -66L18 -52Q18 -48 14 -48L-14 -48Q-18 -48 -18 -52Z"
            fill="var(--ghost-shade)"
            strokeWidth="4"
          />
          <path d="M-6 -70Q-6 -78 0 -78Q6 -78 6 -70" fill="none" strokeWidth="4" />
          <g className="steno-tape" mask={`url(#${maskId})`} fill="none">
            <path d={TAPE} strokeWidth="16" />
            <path d={TAPE} stroke="var(--paper)" strokeWidth="10.5" />
            <path className="steno-ticks" d={TAPE} strokeWidth="2.6" strokeDasharray="4 4" strokeLinecap="butt" />
          </g>
          <g className="steno-imprint">
            <path d={ring(15, 46, 10)} fill="var(--brass)" strokeWidth="3" />
            <path d={`${ring(15, 46, 5)}M15 43v6M12 46h6`} fill="none" stroke="var(--brass-deep)" strokeWidth="2.2" />
          </g>
          <path
            d="M-58 -2C-50 -10 -38 -8 -34 0C-30 6 -32 14 -36 18C-34 24 -40 28 -46 24C-52 22 -58 16 -60 8C-61 4 -60 0 -58 -2Z"
            fill="var(--slate-deep)"
            strokeWidth="4.5"
          />
          <path d="M-36 8q-5 1 -9 -1M-38 17q-5 1 -9 -1" fill="none" strokeWidth="2.5" />
        </g>

        <g className="steno-wing-write">
          <g className="steno-arm">
            <g className="steno-stamp">
              <path d="M106 254H132Q134 254 134 256V266Q134 268 132 268H106Q104 268 104 266V256Q104 254 106 254Z" fill="var(--brass)" strokeWidth="4" />
              <path d="M108 263.5H130" fill="none" stroke="var(--brass-deep)" strokeWidth="3" />
              <path d="M113 242H125L126 254H112Z" fill="var(--wood)" strokeWidth="4" />
              <path d={ring(119, 233, 9)} fill="var(--wood-light)" strokeWidth="4" />
            </g>
            <path
              d="M238 166C218 170 186 180 160 198C146 208 132 218 124 229C128 234 134 234 139 231C142 237 150 237 154 233C158 237 166 235 170 231C190 224 216 214 243 206C245 190 243 176 238 166Z"
              fill="var(--slate-deep)"
              strokeWidth="5"
            />
            <path d="M204 186q4 6 8 0q4 6 8 0M180 198q4 6 8 0M160 212q4 6 8 0" fill="none" strokeWidth="2.5" />
            <g className="steno-quill">
              <path d="M126 220C128 204 140 186 160 174C158 190 146 210 130 224Z" fill="var(--wax)" strokeWidth="3.5" />
              <path d="M115 238L158 177" fill="none" strokeWidth="2.5" />
              <path d="M112 243L115 234L120 232L118 239Z" fill="var(--ink)" strokeWidth="2" />
              <path d="M117 227C123 222 132 224 134 230C130 236 122 237 117 233Z" fill="var(--slate-deep)" strokeWidth="3.5" />
            </g>
          </g>
        </g>

        <g className="steno-puff" fill="var(--paper-deep)" strokeWidth="2">
          <circle cx="97" cy="265" r="5" />
          <circle cx="141" cy="263" r="5" />
          <circle cx="121" cy="277" r="4.5" />
        </g>
      </g>
    </svg>
  );
}
