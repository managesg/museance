import type { FauxMood } from '../engine/types';
import './faux.css';

const TITLE: Record<FauxMood, string> = {
  hidden: 'Faux, a cardboard standee of the app, out of sight',
  wave: 'Faux, a cardboard standee of the app, waving cheerfully',
  bow: 'Faux, a cardboard standee of the app, taking a bow',
  smug: 'Faux, a cardboard standee of the app, looking smug',
};

// One phone silhouette serves the kraft back (offset left as the cut edge), the print and the outline.
const BOARD =
  'M72 51C120 49 180 51 208 50C226 50 238 62 238 80C239 230 237 380 238 476C238 494 226 506 208 506C160 507 110 505 72 506C54 506 42 494 42 476C41 330 43 210 42 80C42 62 54 51 72 51Z';
const SCREEN =
  'M68 88C120 87 170 89 212 88C220 88 226 94 226 102C227 220 225 340 226 440C226 448 220 454 212 454C170 455 110 453 68 454C60 454 54 448 54 440C53 330 55 210 54 102C54 94 60 88 68 88Z';
const DISPLAY =
  'M74 98C120 97 170 99 206 98C212 98 216 102 216 108C217 150 215 190 216 216C216 222 212 226 206 226C160 227 110 225 74 226C68 226 64 222 64 216C63 180 65 140 64 108C64 102 68 98 74 98Z';
// Corrugated flutes show on the cut edge as a wavy line between the liners.
const FLUTES = 'M36 86' + 'q2.4 4 0 8q-2.4 4 0 8'.repeat(24);
const ARM =
  'M-13 0C-13-17 13-17 13 0C13 30 11 62 10 92C21 95 25 118 16 129C8 138-10 138-16 128C-19 122-20 116-19 110C-27 109-32 99-27 93C-23 89-17 91-12 95C-12 64-13 30-13 0Z';

type Tone = 'paper' | 'terracotta' | 'brass';
const TONE: Record<Tone, [face: string, side: string, mark: string]> = {
  paper: ['var(--paper)', 'var(--paper-deep)', 'var(--ink)'],
  terracotta: ['var(--terracotta)', 'var(--terracotta-deep)', 'var(--paper)'],
  brass: ['var(--brass)', 'var(--brass-deep)', 'var(--ink)'],
};
const DIV = 'M-9 0H9M0-8.5v.01M0 8.5v.01';
const MUL = 'M-7-7L7 7M7-7L-7 7';
const ADD = 'M-9 0H9M0-9V9';
const EQ = 'M-12-5H12M-12 5H12';
const DOT = 'M0 5v.01';
// The fixture calculator's ten keys; a slight tilt each keeps the print hand-cut.
const KEYS: { x: number; y: number; w: number; tone: Tone; label?: string; glyph?: string; tilt: number }[] = [
  { x: 64, y: 236, w: 44, tone: 'paper', label: '7', tilt: -1.2 },
  { x: 118, y: 236, w: 44, tone: 'paper', label: '8', tilt: 0.8 },
  { x: 172, y: 236, w: 44, tone: 'terracotta', glyph: DIV, tilt: -0.6 },
  { x: 64, y: 290, w: 44, tone: 'paper', label: '1', tilt: 0.9 },
  { x: 118, y: 290, w: 44, tone: 'paper', label: '0', tilt: -0.8 },
  { x: 172, y: 290, w: 44, tone: 'terracotta', glyph: MUL, tilt: 1.1 },
  { x: 64, y: 344, w: 44, tone: 'paper', glyph: DOT, tilt: -0.4 },
  { x: 118, y: 344, w: 44, tone: 'paper', label: 'C', tilt: 0.5 },
  { x: 172, y: 344, w: 44, tone: 'terracotta', glyph: ADD, tilt: -1 },
  { x: 64, y: 398, w: 152, tone: 'brass', glyph: EQ, tilt: 0.3 },
];

const ink = (w: number) => ({ fill: 'none', stroke: 'var(--ink)', strokeWidth: w });
const polar = (r: number, deg: number) => {
  const a = (deg * Math.PI) / 180;
  return `${(r * Math.cos(a)).toFixed(1)} ${(r * Math.sin(a)).toFixed(1)}`;
};

function Key({ x, y, w, tone, label, glyph, tilt }: (typeof KEYS)[number]) {
  const [face, side, mark] = TONE[tone];
  const cx = x + w / 2;
  const fy = y + 18;
  return (
    <g transform={`rotate(${tilt} ${cx} ${y + 22})`}>
      <rect x={x} y={y} width={w} height={44} rx={8} fill={face} />
      <path d={`M${x} ${y + 35}H${x + w}V${y + 36}Q${x + w} ${y + 44} ${x + w - 8} ${y + 44}H${x + 8}Q${x} ${y + 44} ${x} ${y + 36}Z`} fill={side} />
      <rect x={x} y={y} width={w} height={44} rx={8} {...ink(3.5)} />
      {label ? (
        <text className="faux__key-label" x={cx} y={fy} fill={mark}>
          {label}
        </text>
      ) : (
        <path d={glyph} transform={`translate(${cx} ${fy})`} fill="none" stroke={mark} strokeWidth={glyph === DOT ? 7 : 4.5} />
      )}
    </g>
  );
}

// A googly eye: the pupil hangs at the bottom of the dome and its group pivots on the eye centre.
function Eye({ x, y, r, right }: { x: number; y: number; r: number; right?: boolean }) {
  const p = r * 0.52;
  const k = r - 3;
  const g = r * 0.66;
  return (
    <g className={right ? 'faux__eye faux__eye--r' : 'faux__eye'} transform={`translate(${x} ${y})`}>
      <circle r={r} fill="var(--belly)" />
      <path d={`M${polar(k, -25)}A${k} ${k} 0 0 1 ${polar(k, 120)}A${k * 1.35} ${k * 1.35} 0 0 0 ${polar(k, -25)}Z`} fill="var(--paper-deep)" />
      <g className="faux__pupil">
        <circle cy={r - p - 3.5} r={p} fill="var(--penguin)" />
      </g>
      <path d={`M${polar(g, 200)}A${g} ${g} 0 0 1 ${polar(g, 245)}`} fill="none" stroke="var(--belly)" strokeWidth={4} />
      <circle r={r} {...ink(4.5)} />
    </g>
  );
}

export function Faux({ mood }: { mood: FauxMood }) {
  return (
    <svg
      className={`faux faux--${mood}`}
      viewBox="0 0 320 560"
      width="100%"
      height="100%"
      preserveAspectRatio="xMidYMax meet"
      role="img"
      aria-hidden={mood === 'hidden' || undefined}
    >
      <title>{TITLE[mood]}</title>
      <g className="faux__rig">
        <ellipse cx={136} cy={510} rx={134} ry={12} fill="var(--floor-shadow)" />
        <g className="faux__easel">
          <path d="M36 246C26 330 12 430 2 507L27 508C34 430 42 340 50 268Z" fill="var(--kraft)" stroke="var(--ink)" strokeWidth={4.5} />
          <path d="M34 300L11 495M43 300L20 495" fill="none" stroke="var(--kraft-deep)" strokeWidth={2} />
        </g>
        <g className="faux__tilt">
          <g className="faux__board">
            <path d={BOARD} transform="translate(-12 0)" fill="var(--kraft)" stroke="var(--ink)" strokeWidth={5.5} />
            <path d={FLUTES} fill="none" stroke="var(--kraft-deep)" strokeWidth={2} />
            <path d={BOARD} fill="var(--penguin)" />
            <rect x={118} y={66} width={44} height={7} rx={3.5} fill="var(--slate-deep)" />
            <circle cx={178} cy={69.5} r={4} fill="var(--slate-deep)" />
            <circle cx={140} cy={480} r={14} fill="none" stroke="var(--slate-deep)" strokeWidth={3} />
            <path d={SCREEN} fill="var(--slate-deep)" stroke="var(--ink)" strokeWidth={3.5} />
            <path d={DISPLAY} fill="var(--slate)" stroke="var(--ink)" strokeWidth={3.5} />
            {KEYS.map((k) => (
              <Key key={k.label ?? k.glyph} {...k} />
            ))}
          </g>
          <g className="faux__face">
            <Eye x={108} y={158} r={30} />
            <Eye x={175} y={163} r={25} right />
            <path d="M104 199C118 224 162 226 182 196C164 211 120 210 104 199Z" fill="var(--wax)" />
            <path d="M97 194Q101 198 103 204M189 190Q185 194 184 200" fill="none" stroke="var(--wax)" strokeWidth={4.5} />
          </g>
          <g className="faux__peel">
            <path d="M238 464L238 476C238 494 226 506 208 506L196 506Z" fill="var(--kraft)" />
            <path d={BOARD} {...ink(5.5)} />
            <path d="M238 464C226 465 212 467 206 472C201 478 198 494 196 506Z" fill="var(--paper)" />
            <path d="M232 470L202 500" fill="none" stroke="var(--paper-deep)" strokeWidth={5} />
            <path d="M238 464C226 465 212 467 206 472C201 478 198 494 196 506Z" {...ink(3.5)} />
          </g>
          <g transform="translate(229 312)">
            <g className="faux__arm">
              <path d={ARM} fill="var(--kraft)" stroke="var(--ink)" strokeWidth={4.5} />
              <path d="M-4 6C-4 34-4 62-3 88M5 6C5 34 5 62 4 88" fill="none" stroke="var(--kraft-deep)" strokeWidth={2} />
            </g>
            <circle r={8.5} fill="var(--brass)" />
            <path d={`M${polar(6.5, -40)}A6.5 6.5 0 0 1 ${polar(6.5, 130)}A8 8 0 0 0 ${polar(6.5, -40)}Z`} fill="var(--brass-deep)" />
            <circle r={8.5} {...ink(3.5)} />
          </g>
        </g>
      </g>
    </svg>
  );
}
