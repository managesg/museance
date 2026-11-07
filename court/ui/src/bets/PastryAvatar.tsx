import type { ReactNode } from 'react';
import type { Pastry } from '../engine/types';
import './bets.css';

type Pt = readonly [number, number];
type At = readonly [cx: number, cy: number, rx: number, ry: number, rot?: number, seed?: number];

const r1 = (v: number) => Math.round(v * 10) / 10;
const INK = { stroke: 'var(--ink)', strokeWidth: 4.5, strokeLinejoin: 'round', strokeLinecap: 'round' } as const;

const NAMES: Record<Pastry, string> = {
  croissant: 'Croissant',
  bagel: 'Bagel',
  eclair: 'Éclair',
  pretzel: 'Pretzel',
  canele: 'Canelé',
  kouign: 'Kouign-amann',
};

// An ellipse whose radius wanders a little, smoothed through edge midpoints, so outlines read hand-drawn.
function lump(cx: number, cy: number, rx: number, ry: number, rot = 0, seed = 0): string {
  const n = 14;
  const t = (rot * Math.PI) / 180;
  const pts = Array.from({ length: n }, (_, i): Pt => {
    const a = (i / n) * Math.PI * 2;
    const k = 1 + 0.035 * Math.sin(3 * a + seed) + 0.02 * Math.sin(5 * a + 2 * seed);
    const x = Math.cos(a) * rx * k;
    const y = Math.sin(a) * ry * k;
    return [cx + x * Math.cos(t) - y * Math.sin(t), cy + x * Math.sin(t) + y * Math.cos(t)];
  });
  const mid = (i: number) => {
    const [p, q] = [pts[i % n], pts[(i + 1) % n]];
    return `${r1((p[0] + q[0]) / 2)} ${r1((p[1] + q[1]) / 2)}`;
  };
  let d = `M${mid(n - 1)}`;
  for (let i = 0; i < n; i++) d += `Q${r1(pts[i][0])} ${r1(pts[i][1])} ${mid(i)}`;
  return `${d}Z`;
}

// Light comes from the upper left: the shade fills the outline, the lit face sits up-left inside it, ink goes on last.
function Shaded({ d, lit, litTransform, fill, shade }: { d: string; lit?: string; litTransform?: string; fill: string; shade: string }) {
  return (
    <>
      <path d={d} fill={`var(--${shade})`} />
      <path d={lit ?? d} transform={litTransform} fill={`var(--${fill})`} />
      <path d={d} fill="none" {...INK} />
    </>
  );
}

function Piece({ at, fill, shade }: { at: At; fill: string; shade: string }) {
  const [cx, cy, rx, ry, rot = 0, seed = 0] = at;
  return (
    <Shaded
      d={lump(cx, cy, rx, ry, rot, seed)}
      lit={lump(cx - rx * 0.06, cy - ry * 0.1, rx * 0.86, ry * 0.82, rot, seed)}
      fill={fill}
      shade={shade}
    />
  );
}

function Face({ x, y, scale = 1, blush }: { x: number; y: number; scale?: number; blush?: boolean }) {
  return (
    <g className="pa__face" transform={`translate(${x} ${y}) scale(${scale})`}>
      {blush &&
        [-1, 1].map((s) => <ellipse key={s} cx={s * 13} cy={6.5} rx={4.4} ry={2.6} fill="var(--terracotta)" opacity={0.7} />)}
      {[-1, 1].map((s) => (
        <g key={s}>
          <ellipse cx={s * 7} cy={0} rx={4.3} ry={5.1} fill="var(--belly)" stroke="var(--ink)" strokeWidth={2.4} />
          <circle cx={s * 6.2} cy={1.1} r={2.4} fill="var(--ink)" />
        </g>
      ))}
      <path d="M-4.6 7.4Q0 12 4.6 7.4" fill="none" stroke="var(--ink)" strokeWidth={2.8} strokeLinecap="round" />
    </g>
  );
}

// One cubic run per stretch, joined smoothly, so the twist (OVER) can be laid back on top of the knot.
const PRETZEL =
  'M36 95C40 89 45.8 83.6 50 78C54.8 71.6 65.6 58.6 70 52C74.4 45.4 78 34 88 34C98 34 106 44 106 54C106 74 84 97 60 97C36 97 14 74 14 54C14 44 22 34 32 34C42 34 45.6 45.4 50 52C54.4 58.6 65.2 71.6 70 78C74.2 83.6 80 89 84 95';
const OVER = 'M50 78C54.8 71.6 65.6 58.6 70 52';

function Dough({ d, over }: { d: string; over?: boolean }) {
  // butt ends on the twist so it sits flush on the knot; the lit core keeps round ends to hide the seam
  const cap = over ? 'butt' : 'round';
  return (
    <g fill="none" strokeLinejoin="round">
      <path d={d} stroke="var(--ink)" strokeWidth={25} strokeLinecap={cap} />
      <path d={d} stroke="var(--wood)" strokeWidth={16} strokeLinecap={cap} />
      <path d={d} stroke="var(--wood-light)" strokeWidth={10} strokeLinecap="round" transform="translate(-1.2 -1.6)" />
    </g>
  );
}

const Grain = ({ at: [x, y, a], fill }: { at: readonly [x: number, y: number, deg: number]; fill: string }) => (
  <rect
    x={x - 2.4}
    y={y - 1.5}
    width={4.8}
    height={3}
    rx={1.2}
    transform={`rotate(${a} ${x} ${y})`}
    fill={`var(--${fill})`}
    stroke="var(--ink)"
    strokeWidth={1.2}
  />
);

const BAGEL_HOLE = lump(60, 72, 13, 6.5, 0, 2);
const CANELE = 'M29 44C28 58 24 80 25 97C36 106 84 106 95 97C96 80 92 58 91 44Z';
const GLAZE =
  'M13 79C12 70 22 62 34 61C48 58 70 56 84 58C98 59 108 64 108 70C108 73 104 74 100 73C96 72 94 78 90 78C86 78 86 73 81 73C72 74 60 76 50 77C45 77 44 84 40 84C36 84 36 78 31 78C24 79 18 81 13 79Z';

const ART: Record<Pastry, ReactNode> = {
  croissant: (
    <>
      <Piece at={[22, 88, 10, 15, 40, 1]} fill="brass" shade="brass-deep" />
      <Piece at={[98, 88, 10, 15, -40, 2]} fill="brass" shade="brass-deep" />
      <Piece at={[38, 80, 15, 21, 24, 3]} fill="brass" shade="brass-deep" />
      <Piece at={[82, 80, 15, 21, -24, 4]} fill="brass" shade="brass-deep" />
      <Piece at={[60, 75, 21, 27, 0, 5]} fill="brass" shade="brass-deep" />
      <path d="M48 56C55 52 65 52 72 56" fill="none" stroke="var(--brass-deep)" strokeWidth={3} strokeLinecap="round" />
      <Face x={60} y={76} blush />
    </>
  ),
  bagel: (
    <>
      {/* evenodd cuts the hole clean through, so whatever the bagel sits on shows in it */}
      <path d={lump(60, 80, 46, 26, 0, 6) + BAGEL_HOLE} fill="var(--wood-light)" fillRule="evenodd" />
      <path d={lump(60, 76, 45, 22, 0, 6) + BAGEL_HOLE} fill="var(--brass-deep)" fillRule="evenodd" />
      <path d="M47 72A13 6.5 0 0 1 73 72A13 2.6 0 0 1 47 72Z" fill="var(--wood-light)" />
      <path d={BAGEL_HOLE} fill="none" {...INK} strokeWidth={3.5} />
      <path d={lump(60, 80, 46, 26, 0, 6)} fill="none" {...INK} />
      {(
        [
          [28, 66, -30], [40, 59, 15], [54, 58, -10], [70, 58, 20], [86, 62, -25],
          [95, 75, 35], [24, 80, 10], [86, 86, -15],
        ] as const
      ).map((at) => (
        <Grain key={`${at[0]},${at[1]}`} at={at} fill="wax" />
      ))}
      <Face x={60} y={84} scale={0.9} />
    </>
  ),
  eclair: (
    <>
      <Piece at={[60, 79, 50, 23, -6, 7]} fill="floor-shadow" shade="brass-deep" />
      <path d={GLAZE} fill="var(--wood)" {...INK} strokeWidth={4} />
      <path d="M30 67C42 61 58 59 74 59" fill="none" stroke="var(--wood-light)" strokeWidth={3.5} strokeLinecap="round" />
      <Face x={58} y={86} scale={0.95} blush />
    </>
  ),
  pretzel: (
    <>
      <Dough d={PRETZEL} />
      <Dough d={OVER} over />
      {(
        [
          [26, 37, 20], [39, 32, -10], [82, 32, 15], [96, 37, -25], [105, 62, 40], [15, 64, -30],
        ] as const
      ).map((at) => (
        <Grain key={`${at[0]},${at[1]}`} at={at} fill="wax" />
      ))}
      <Face x={60} y={93} scale={0.72} />
    </>
  ),
  canele: (
    <>
      <Shaded d={CANELE} litTransform="translate(6 3) scale(0.8 0.94)" fill="terracotta-deep" shade="wood" />
      <path
        d="M37 50C35 66 33 84 33 100M45 52C44 68 43 86 43 103M75 52C76 68 77 86 77 103M83 50C85 66 87 84 87 100"
        fill="none"
        stroke="var(--ink)"
        strokeWidth={2.6}
        strokeLinecap="round"
      />
      <path d={lump(60, 44, 32, 9.5, 0, 3)} fill="var(--terracotta-deep)" {...INK} strokeWidth={4} />
      <path d={lump(60, 45, 19, 5, 0, 5)} fill="var(--wood)" {...INK} strokeWidth={2.5} />
      <Face x={59} y={69} />
    </>
  ),
  kouign: (
    <>
      <Piece at={[60, 88, 46, 16, 0, 2]} fill="terracotta" shade="terracotta-deep" />
      <Piece at={[60, 58, 24, 13, 0, 4]} fill="flame" shade="terracotta" />
      <Piece at={[35, 74, 21, 16, -24, 6]} fill="flame" shade="terracotta" />
      <Piece at={[85, 74, 21, 16, 24, 8]} fill="flame" shade="terracotta" />
      <Piece at={[60, 86, 28, 16, 0, 9]} fill="flame" shade="terracotta" />
      <path d={lump(60, 68, 7, 4, 0, 1)} fill="var(--terracotta)" {...INK} strokeWidth={3} />
      {([[42, 66], [78, 65], [52, 55], [70, 54]] as const).map(([x, y]) => (
        <circle key={`${x},${y}`} cx={x} cy={y} r={1.8} fill="var(--wax)" />
      ))}
      <Face x={60} y={85} scale={0.9} />
    </>
  ),
};

/** A gallery bettor's pastry, ink-outlined like the cast, with a tiny face. Without a size it fills its box. */
export function PastryAvatar({ kind, size }: { kind: Pastry; size?: number }) {
  return (
    <svg
      className={`pa pa--${kind}`}
      viewBox="0 0 120 120"
      width={size ?? '100%'}
      height={size ?? '100%'}
      preserveAspectRatio="xMidYMax meet"
      role="img"
      overflow="visible"
    >
      <title>{NAMES[kind] ?? kind}</title>
      <ellipse cx={60} cy={107} rx={kind === 'eclair' ? 46 : 40} ry={5.5} fill="var(--floor-shadow)" />
      <g className="pa__body">{ART[kind]}</g>
    </svg>
  );
}
