import type { CSSProperties, ReactElement } from 'react';
import './courtroom.css';

/** Real coordinates of the drawn set on the 1920x1080 canvas, for cast and props that rest on it. */
export const SET_ANCHORS = {
  benchTop: { x: 960, y: 388 },
  tableTop: { x: 960, y: 712, rx: 330, ry: 66 },
  crystalBall: { x: 960, y: 604, r: 54 },
} as const;

const { tableTop: TOP, crystalBall: BALL } = SET_ANCHORS;
const INK = 'var(--ink)';

type Pt = readonly [number, number];
const r1 = (v: number) => Math.round(v * 10) / 10;

// Deterministic noise in [-1, 1]: the set trembles like a hand drawing, identically on every load.
function noise(n: number): number {
  const s = Math.sin(n * 12.9898 + 4.1414) * 43758.5453;
  return (s - Math.floor(s)) * 2 - 1;
}

// Straight-edged outline with nudged corners and slightly bowed edges.
function sketch(pts: Pt[], seed: number, wob = 1.6): string {
  const p = pts.map(([x, y], i): Pt => [x + noise(seed + i) * wob * 0.5, y + noise(seed + i + 40) * wob * 0.5]);
  let d = `M${r1(p[0][0])} ${r1(p[0][1])}`;
  p.forEach((a, i) => {
    const b = p[(i + 1) % p.length];
    const len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    const bow = noise(seed + i + 80) * wob;
    d += `Q${r1((a[0] + b[0]) / 2 - ((b[1] - a[1]) / len) * bow)} ${r1((a[1] + b[1]) / 2 + ((b[0] - a[0]) / len) * bow)} ${r1(b[0])} ${r1(b[1])}`;
  });
  return `${d}Z`;
}

const box = (x: number, y: number, w: number, h: number, seed: number, wob?: number) =>
  sketch([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], seed, wob);

// Ellipse points with a little radial tremble; index 0 is the right end, n/2 the left end.
function ring(cx: number, cy: number, rx: number, ry: number, seed: number, wob = 1.8, n = 18): Pt[] {
  return Array.from({ length: n }, (_, i): Pt => {
    const a = (i / n) * Math.PI * 2;
    const j = noise(seed + i) * wob;
    return [cx + Math.cos(a) * (rx + j), cy + Math.sin(a) * (ry + j)];
  });
}

// Catmull-Rom spline through the points as cubic Beziers (closed loops wrap, open ends clamp).
function spline(p: Pt[], closed: boolean): string {
  const n = p.length;
  const at = (i: number) => p[closed ? (i + n) % n : Math.min(n - 1, Math.max(0, i))];
  let d = `M${r1(p[0][0])} ${r1(p[0][1])}`;
  for (let i = 0; i < (closed ? n : n - 1); i++) {
    const [a, b, c, e] = [at(i - 1), at(i), at(i + 1), at(i + 2)];
    d += `C${r1(b[0] + (c[0] - a[0]) / 6)} ${r1(b[1] + (c[1] - a[1]) / 6)} ${r1(c[0] - (e[0] - b[0]) / 6)} ${r1(c[1] - (e[1] - b[1]) / 6)} ${r1(c[0])} ${r1(c[1])}`;
  }
  return closed ? `${d}Z` : d;
}

const oval = (cx: number, cy: number, rx: number, ry: number, seed: number, wob?: number) =>
  spline(ring(cx, cy, rx, ry, seed, wob), true);

// Flat fill, a darker tone clipped to the same outline, then the ink line last so the tone never eats it.
function inked(id: string, d: string, fill: string, w: number, tone?: readonly [string, string]): ReactElement {
  return (
    <g key={id}>
      <path d={d} fill={fill} />
      {tone && (
        <>
          <clipPath id={`set-${id}`}>
            <path d={d} />
          </clipPath>
          <path d={tone[0]} fill={tone[1]} clipPath={`url(#set-${id})`} />
        </>
      )}
      <path d={d} fill="none" stroke={INK} strokeWidth={w} />
    </g>
  );
}

const mirror = (pts: Pt[]): Pt[] => pts.map(([x, y]): Pt => [1920 - x, y]);

/* ---------- defs ---------- */

const MOTIF =
  'M0 -28C7 -18 12 -9 12 0C12 9 7 18 0 28C-7 18 -12 9 -12 0C-12 -9 -7 -18 0 -28Z' +
  'M0 -13C3 -8 5 -4 5 0C5 4 3 8 0 13C-3 8 -5 4 -5 0C-5 -4 -3 -8 0 -13Z' +
  'M-15 3C-22 -6 -31 -3 -31 4C-31 10 -22 11 -15 3Z' +
  'M15 3C22 -6 31 -3 31 4C31 10 22 11 15 3Z';
const PIP = 'M0 -6L5 0L0 6L-5 0Z';

const BALL_D = oval(BALL.x, BALL.y, BALL.r, BALL.r, 400, 1);

const DEFS = (
  <defs>
    <pattern id="set-damask" width="96" height="128" y="104" patternUnits="userSpaceOnUse">
      <g fill="var(--wall-deep)" fillRule="evenodd">
        {[[48, 32], [0, 96], [96, 96]].map(([x, y]) => (
          <path key={`m${x}-${y}`} transform={`translate(${x} ${y})`} d={MOTIF} />
        ))}
        {[[0, 32], [96, 32], [48, 96]].map(([x, y]) => (
          <path key={`p${x}-${y}`} transform={`translate(${x} ${y})`} d={PIP} />
        ))}
      </g>
    </pattern>
    <radialGradient id="set-flame-glow">
      <stop offset="0" stopColor="var(--flame-core)" stopOpacity="0.8" />
      <stop offset="0.35" stopColor="var(--flame)" stopOpacity="0.35" />
      <stop offset="1" stopColor="var(--flame)" stopOpacity="0" />
    </radialGradient>
    <radialGradient id="set-halo-warm">
      <stop offset="0" stopColor="var(--flame-core)" stopOpacity="0.6" />
      <stop offset="0.45" stopColor="var(--flame)" stopOpacity="0.24" />
      <stop offset="1" stopColor="var(--flame)" stopOpacity="0" />
    </radialGradient>
    <radialGradient id="set-halo-red">
      <stop offset="0" stopColor="var(--crimson)" stopOpacity="0.85" />
      <stop offset="0.45" stopColor="var(--crimson)" stopOpacity="0.4" />
      <stop offset="1" stopColor="var(--crimson-deep)" stopOpacity="0" />
    </radialGradient>
    <radialGradient id="set-glass" cx="0.42" cy="0.38" r="0.62">
      <stop offset="0" stopColor="var(--ghost)" stopOpacity="0.92" />
      <stop offset="0.7" stopColor="var(--ghost)" stopOpacity="0.74" />
      <stop offset="1" stopColor="var(--ghost-shade)" stopOpacity="0.96" />
    </radialGradient>
    <radialGradient id="set-core">
      <stop offset="0" stopColor="var(--flame-core)" />
      <stop offset="0.16" stopColor="var(--crimson)" />
      <stop offset="0.55" stopColor="var(--crimson)" stopOpacity="0.55" />
      <stop offset="1" stopColor="var(--crimson-deep)" stopOpacity="0" />
    </radialGradient>
    <radialGradient id="set-fever" cy="0.55" r="0.55">
      <stop offset="0" stopColor="var(--crimson)" stopOpacity="0.95" />
      <stop offset="0.7" stopColor="var(--crimson)" stopOpacity="0.7" />
      <stop offset="1" stopColor="var(--crimson-deep)" stopOpacity="0.85" />
    </radialGradient>
    <clipPath id="set-ball-clip">
      <path d={BALL_D} />
    </clipPath>
  </defs>
);

/* ---------- room: wall, wainscot, floor ---------- */

const SEAMS = [684, 732, 788, 852, 926, 1008];
const FLOORBOARDS =
  SEAMS.map((y, r) => `M-10 ${y}Q960 ${r1(y + noise(r + 500) * 4)} 1930 ${y}`).join('') +
  SEAMS.flatMap((y, r) =>
    [0, 1, 2, 3].map((k) => {
      const x = r1(150 + k * 520 + noise(r * 11 + k + 600) * 190);
      return `M${x} ${(r === 0 ? 652 : SEAMS[r - 1]) + 5}L${x} ${y - 5}`;
    }),
  ).join('');
const DADO_PANELS = Array.from({ length: 11 }, (_, i) => box(26 + i * 172, 584, 148, 30, 200 + i * 7, 1)).join('');

const ROOM = (
  <g>
    <rect width="1920" height="644" fill="var(--wall)" />
    <rect y="640" width="1920" height="440" fill="var(--floor)" />
    <path d={FLOORBOARDS} fill="none" stroke="var(--floor-shadow)" strokeWidth="3" opacity="0.75" />
    <rect y="642" width="1920" height="10" fill="var(--floor-shadow)" opacity="0.7" />
    <rect y="104" width="1920" height="452" fill="url(#set-damask)" opacity="0.32" />
    <rect y="104" width="1920" height="8" fill="var(--wall-deep)" />
    <path d={box(-10, 90, 1940, 14, 11)} fill="var(--wood-light)" stroke={INK} strokeWidth="4" />
    <rect y="570" width="1920" height="8" fill="var(--wall-deep)" />
    <path d={DADO_PANELS} fill="var(--wall-deep)" opacity="0.7" />
    <path d={box(-10, 556, 1940, 14, 23)} fill="var(--wood-light)" stroke={INK} strokeWidth="4" />
    <path d={box(-10, 620, 1940, 22, 37)} fill="var(--wood)" stroke={INK} strokeWidth="5" />
  </g>
);

/* ---------- judge's bench ---------- */

const CHAIR = 'M786 402L780 214C778 168 850 134 960 130C1070 134 1142 168 1140 214L1134 402Z';
const CHAIR_PANEL = 'M808 402L803 222C803 186 862 157 960 153C1058 157 1117 186 1117 222L1112 402Z';
const TUFTS = 'M960 174L878 262M960 174L926 288M960 174L994 288M960 174L1042 262M836 206L852 262M1084 206L1068 262';
const BELL_BODY = 'M722 390Q726 383 733 381Q734 352 752 345Q770 352 771 381Q778 383 782 390Q752 397 722 390Z';
const GAVEL_HEAD = 'M-14 -32Q0 -36 14 -32Q17 0 14 32Q0 36 -14 32Q-17 0 -14 -32Z';

const BENCH = (
  <g>
    <ellipse cx="960" cy="656" rx="282" ry="10" fill="var(--floor-shadow)" />
    <path d={CHAIR} fill="var(--wood)" stroke={INK} strokeWidth="6" />
    <path d={CHAIR_PANEL} fill="var(--wood-light)" stroke={INK} strokeWidth="4" />
    <path d={TUFTS} fill="none" stroke="var(--wood)" strokeWidth="4" />
    <g fill="var(--wood)">
      {[[878, 262], [926, 288], [994, 288], [1042, 262], [960, 174]].map(([x, y]) => (
        <circle key={`${x}`} cx={x} cy={y} r="5" />
      ))}
    </g>

    {inked('bench', box(706, 412, 508, 216, 7), 'var(--terracotta)', 6, ['M1188 400H1230V640H1188Z', 'var(--terracotta-deep)'])}
    <rect x="709" y="415" width="476" height="11" fill="var(--terracotta-deep)" />
    {inked('inset', box(744, 488, 432, 128, 10), 'var(--terracotta-deep)', 4, [box(755, 499, 430, 130, 12, 1), 'var(--terracotta)'])}

    <path d={box(848, 432, 224, 42, 8, 1)} fill="var(--brass)" stroke={INK} strokeWidth="4" />
    <path d={box(864, 438, 192, 30, 9, 0.8)} fill="none" stroke="var(--brass-deep)" strokeWidth="2.5" />
    <circle cx="856" cy="453" r="3.5" fill="var(--brass-deep)" />
    <circle cx="1064" cy="453" r="3.5" fill="var(--brass-deep)" />
    <text x="960" y="462" textAnchor="middle" className="set-plate">
      THE BENCH
    </text>

    <path d={box(698, 624, 524, 30, 13)} fill="var(--wood)" stroke={INK} strokeWidth="5" />
    <path d={sketch([[704, 378], [1216, 378], [1230, 396], [690, 396]], 5)} fill="var(--wood-light)" stroke={INK} strokeWidth="5" />
    <path d={box(690, 396, 540, 18, 6)} fill="var(--wood)" stroke={INK} strokeWidth="5" />

    {/* hand bell */}
    <path d="M752 296C762 296 767 306 765 316C763 325 758 329 752 329C746 329 741 325 739 316C737 306 742 296 752 296Z" fill="var(--wood-light)" stroke={INK} strokeWidth="3.5" />
    <path d="M748 327H756V346H748Z" fill="var(--wood)" stroke={INK} strokeWidth="3" />
    {inked('bell', BELL_BODY, 'var(--brass)', 4, ['M760 330Q776 352 774 380L790 400H764Q768 368 758 330Z', 'var(--brass-deep)'])}

    {/* gavel resting on its sound block */}
    <path d="M1105 378V390A27 6 0 0 0 1159 390V378Z" fill="var(--wood)" stroke={INK} strokeWidth="3.5" />
    <path d="M1106 385A27 6 0 0 0 1158 385" fill="none" stroke="var(--brass)" strokeWidth="3" />
    <ellipse cx="1132" cy="378" rx="27" ry="6" fill="var(--wood-light)" stroke={INK} strokeWidth="3.5" />
    <g transform="translate(1146 349) rotate(28)">
      <path d="M10 -4.5L66 -5.4Q76 -6 76 0Q76 6 66 5.4L10 4.5Z" fill="var(--wood-light)" stroke={INK} strokeWidth="3.5" />
      {inked('gavel', GAVEL_HEAD, 'var(--wood-light)', 4, ['M5 -40H20V40H5Q9 0 5 -40Z', 'var(--wood)'])}
      <path d="M-15 -25Q0 -28 15 -25L15.5 -19Q0 -22 -15.5 -19Z" fill="var(--brass)" stroke={INK} strokeWidth="2.5" />
      <path d="M-15.5 19Q0 22 15.5 19L15 25Q0 28 -15 25Z" fill="var(--brass)" stroke={INK} strokeWidth="2.5" />
    </g>
  </g>
);

/* ---------- seance table ---------- */

const TOP_PTS = ring(TOP.x, TOP.y, TOP.rx, TOP.ry, 300);
const RIM_DROP = 22;
const RIM = (() => {
  const lower = TOP_PTS.slice(0, 10).reverse().map(([x, y]): Pt => [x, y + RIM_DROP]);
  const [l, r] = [TOP_PTS[9], TOP_PTS[0]];
  return `M${r1(l[0])} ${r1(l[1])}L${spline(lower, false).slice(1)}L${r1(r[0])} ${r1(r[1])}Z`;
})();
const PEDESTAL =
  'M920 806H1000V828Q986 830 984 840Q1002 856 1000 870Q998 882 990 886H1012V912H908V886H930Q922 882 920 870Q918 856 936 840Q934 830 920 828Z';
// Feet tuck their inner ends under the pedestal's hub block, which is drawn over them.
const FOOT_FRONT: Pt[] = [[932, 892], [828, 922], [818, 930], [818, 955], [842, 959], [944, 910]];
const FOOT_BACK: Pt[] = [[926, 888], [856, 866], [848, 870], [848, 890], [866, 895], [926, 904]];
const FOOT_FRONT_TOP: Pt[] = [[816, 929], [946, 899], [946, 850], [800, 850]];
const FOOT_BACK_TOP: Pt[] = [[846, 873], [928, 895], [928, 850], [840, 850]];

const TABLE = (
  <g>
    <ellipse cx="960" cy="934" rx="310" ry="36" fill="var(--floor-shadow)" />
    {inked('foot-bl', sketch(FOOT_BACK, 700), 'var(--wood)', 4, [sketch(FOOT_BACK_TOP, 701, 0), 'var(--wood-light)'])}
    {inked('foot-br', sketch(mirror(FOOT_BACK), 710), 'var(--wood)', 4, [sketch(mirror(FOOT_BACK_TOP), 711, 0), 'var(--wood-light)'])}
    {inked('foot-fl', sketch(FOOT_FRONT, 720), 'var(--wood)', 5, [sketch(FOOT_FRONT_TOP, 721, 0), 'var(--wood-light)'])}
    {inked('foot-fr', sketch(mirror(FOOT_FRONT), 730), 'var(--wood)', 5, [sketch(mirror(FOOT_FRONT_TOP), 731, 0), 'var(--wood-light)'])}
    {inked('pedestal', PEDESTAL, 'var(--wood-light)', 5, ['M978 800H1020V920H978Z', 'var(--wood)'])}
    <path d={oval(960, 760, 300, 60, 301)} fill="var(--wood)" stroke={INK} strokeWidth="5" />
    <path d={RIM} fill="var(--wood)" stroke={INK} strokeWidth="5" />
    <path d={spline(TOP_PTS, true)} fill="var(--wood-light)" stroke={INK} strokeWidth="6" />
  </g>
);

/* ---------- crystal ball ---------- */

const CRYSTAL = (
  <g>
    <g className="set-halo">
      <circle cx={BALL.x} cy={BALL.y} r="150" fill="url(#set-halo-warm)" className="set-halo-warm" />
      <circle cx={BALL.x} cy={BALL.y} r="150" fill="url(#set-halo-red)" className="set-halo-red" />
    </g>
    <ellipse cx="968" cy="701" rx="56" ry="10" fill="var(--wood)" opacity="0.6" />
    <path d={BALL_D} fill="url(#set-glass)" />
    <g clipPath="url(#set-ball-clip)">
      <circle cx={BALL.x} cy={BALL.y} r={BALL.r + 2} fill="url(#set-fever)" className="set-ball-fever" />
      <circle cx={BALL.x} cy={BALL.y + 6} r="44" fill="url(#set-core)" className="set-ball-core" />
      <path d="M922 624Q944 598 966 616T1002 606" fill="none" stroke="var(--ghost-shade)" strokeWidth="4" opacity="0.8" />
    </g>
    <ellipse cx="982" cy="580" rx="12" ry="7.5" transform="rotate(-35 982 580)" fill="var(--paper)" />
    <circle cx="997" cy="598" r="4" fill="var(--paper)" />
    <path d={BALL_D} fill="none" stroke={INK} strokeWidth="5" />

    <path d="M916 690V698A44 10 0 0 0 1004 698V690Z" fill="var(--brass-deep)" stroke={INK} strokeWidth="3.5" />
    <ellipse cx="960" cy="690" rx="44" ry="10" fill="var(--brass)" stroke={INK} strokeWidth="3.5" />
    <path d="M947 690Q951 681 949 672H971Q969 681 973 690Z" fill="var(--brass)" stroke={INK} strokeWidth="3.5" />
    {inked('cup', 'M912 640Q916 669 948 675H972Q1004 669 1008 640Q960 654 912 640Z', 'var(--brass)', 4, ['M978 630H1020V680H978Q992 660 978 630Z', 'var(--brass-deep)'])}
  </g>
);

/* ---------- candles ---------- */

const FLAME = 'M0 -36C5 -26 10 -18 10 -10C10 -3 6 2 0 2C-6 2 -10 -3 -10 -10C-10 -18 -5 -26 0 -36Z';
const FLAME_CORE = 'M0 -21C2.5 -15 5 -11 5 -6C5 -2 3 0.5 0 0.5C-3 0.5 -5 -2 -5 -6C-5 -11 -2.5 -15 0 -21Z';

function candle(id: string, x: number, y: number, h: number, delay: number): ReactElement {
  const top = y - h;
  const body = `M${x - 11} ${y - 3}V${top + 6}Q${x - 10} ${top} ${x - 3} ${top - 1}Q${x + 3} ${top + 2} ${x + 11} ${top - 1}V${y - 3}Z`;
  const lag = { animationDelay: `${delay}s` };
  return (
    <g key={id}>
      <circle cx={x} cy={top - 22} r="50" fill="url(#set-flame-glow)" className="set-glow" style={lag} />
      <ellipse cx={x + 9} cy={y + 3} rx="30" ry="7" fill="var(--wood)" opacity="0.6" />
      <path d={`M${x - 26} ${y - 2}V${y + 2}A26 7 0 0 0 ${x + 26} ${y + 2}V${y - 2}Z`} fill="var(--brass-deep)" stroke={INK} strokeWidth="3.5" />
      <ellipse cx={x} cy={y - 2} rx="26" ry="7" fill="var(--brass)" stroke={INK} strokeWidth="3.5" />
      {inked(id, body, 'var(--wax)', 3.5, [`M${x + 3} ${top - 6}H${x + 14}V${y}H${x + 3}Z`, 'var(--paper-deep)'])}
      <path d={`M${x - 11} ${top + 7}Q${x - 14} ${top + 22} ${x - 8.5} ${top + 24}Q${x - 5} ${top + 20} ${x - 6} ${top + 4}Z`} fill="var(--wax)" stroke={INK} strokeWidth="3" />
      <path d={`M${x} ${top}q2 -5 -1 -10`} fill="none" stroke={INK} strokeWidth="3" />
      <g transform={`translate(${x} ${top - 6})`}>
        <g className="set-flame" style={lag}>
          <path d={FLAME} fill="var(--flame)" stroke={INK} strokeWidth="2.5" />
          <path d={FLAME_CORE} fill="var(--flame-core)" />
        </g>
      </g>
    </g>
  );
}

const CANDLES = [candle('c1', 742, 706, 96, -0.3), candle('c2', 804, 744, 58, -0.9), candle('c3', 1178, 716, 78, -0.55)];

/** The whole courtroom set behind the cast. tension 0..1 reddens the crystal ball and quickens the flames. */
export function CourtroomBackdrop({ tension = 0 }: { tension?: number }) {
  const t = tension > 0 ? Math.min(1, tension) : 0;
  return (
    <svg
      className="set-backdrop"
      viewBox="0 0 1920 1080"
      width="100%"
      height="100%"
      aria-hidden="true"
      style={{ '--tension': t } as CSSProperties}
    >
      {DEFS}
      {ROOM}
      {BENCH}
      {TABLE}
      {CRYSTAL}
      {CANDLES}
    </svg>
  );
}
