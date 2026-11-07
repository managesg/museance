import { useId, type CSSProperties, type ReactNode } from 'react';
import type { LockStatus } from '../contracts';
import './cards.css';

// A closed loop with a wobbling radius, smoothed through midpoints, so the edge reads as poured wax.
function blob(cx: number, cy: number, r: number, lobes: number, amp: number): string {
  const n = 30;
  const pts = Array.from({ length: n }, (_, i) => {
    const a = (i / n) * Math.PI * 2;
    const k = 1 + amp * (0.65 * Math.sin(lobes * a + 0.7) + 0.35 * Math.sin((2 * lobes + 1) * a + 1.9));
    return [cx + Math.cos(a) * r * k, cy + Math.sin(a) * r * k] as const;
  });
  const f = (v: number) => v.toFixed(1);
  const mid = (i: number) => {
    const [p, q] = [pts[i % n], pts[(i + 1) % n]];
    return `${f((p[0] + q[0]) / 2)} ${f((p[1] + q[1]) / 2)}`;
  };
  let d = `M${mid(n - 1)}`;
  for (let i = 0; i < n; i++) d += `Q${f(pts[i][0])} ${f(pts[i][1])} ${mid(i)}`;
  return `${d}Z`;
}

const WAX = blob(80, 80, 66, 5, 0.055);

export function WaxSeal({
  tone,
  size,
  stretch,
  label,
  className,
  children,
}: {
  tone: 'brass' | 'crimson';
  size?: number;
  stretch?: boolean;
  label?: string;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <svg
      className={className}
      viewBox="0 0 160 160"
      width={size}
      height={size}
      preserveAspectRatio={stretch ? 'none' : undefined}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    >
      <path
        d={WAX}
        fill={`var(--${tone}-deep)`}
        stroke="var(--ink)"
        strokeWidth="4"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      {/* the face sits up-left of the rim so the deep shade gathers lower right */}
      <path d={WAX} transform="translate(5 5) scale(0.9)" fill={`var(--${tone})`} />
      <circle
        cx="77"
        cy="77"
        r="57"
        fill="none"
        stroke={`var(--${tone}-deep)`}
        strokeWidth="2.6"
        strokeDasharray="0.1 7"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      {children}
    </svg>
  );
}

type Puff = readonly [x: number, y: number, r: number, dx: number, dy: number];
const RUBBER_PUFFS: readonly Puff[] = [
  [8, 96, 10, -16, 6],
  [36, 108, 7.5, -9, 11],
  [122, 112, 6.5, 0, 13],
  [204, 108, 9, 9, 11],
  [232, 94, 10, 16, 5],
];
const SEAL_PUFFS: readonly Puff[] = [
  [22, 134, 11, -14, 9],
  [80, 154, 8.5, 0, 13],
  [138, 136, 11, 14, 9],
];

function Puffs({ at }: { at: readonly Puff[] }) {
  return (
    <g aria-hidden="true">
      {at.map(([x, y, r, dx, dy]) => (
        <circle
          key={`${x},${y}`}
          className="cc-stamp__puff"
          cx={x}
          cy={y}
          r={r}
          fill="var(--paper-deep)"
          stroke="var(--ink)"
          strokeWidth="1.6"
          style={{ '--dx': `${dx}px`, '--dy': `${dy}px` } as CSSProperties}
        />
      ))}
    </g>
  );
}

const SEAL_LINES = [
  ['SWORN', 71, 92],
  ['LOCKED', 107, 108],
] as const;

const FRAME_OUT =
  'M21 9.5C80 8 160 10.8 219 9.2C227 9.4 231.6 14 231.4 22C232.4 46 230.6 66 231.6 88C231.4 96 227 100.6 219 100.6C160 102 80 99.6 21 101C13 100.8 8.6 96.2 8.8 88C7.6 64 9.4 44 8.4 22C8.6 14 13 9.6 21 9.5Z';
const FRAME_IN =
  'M28 19C86 18 154 20 212 18.8C218 19 222.2 22.6 222 28.4C222.8 50 221.6 64 222.4 82C222.2 87.8 218.4 91.6 212 91.6C154 92.6 86 90.6 28 91.8C22 91.6 17.8 87.6 18 82C17.2 62 18.6 46 17.6 28.4C17.8 22.8 22 19.2 28 19Z';
// Ink skips where the rubber was worn: fixed specks and scratches knocked out of the impression.
const SPECKS: readonly (readonly [number, number, number])[] = [
  [34, 30, 2.2], [62, 84, 1.7], [100, 24, 1.9], [136, 88, 2.3], [172, 38, 1.6], [196, 78, 2.1],
  [214, 28, 1.5], [50, 60, 1.3], [152, 62, 1.4], [116, 44, 1.2], [84, 70, 1.5], [202, 54, 1.1],
  [24, 50, 1.6], [226, 70, 1.7], [70, 40, 1], [184, 92, 1.2],
];
const SCRATCHES = 'M30 72L54 66M150 30L186 25M92 97L118 93M196 62L210 60';

// textLength squeezes each word to the frame so the long ones keep a legible cap height.
const RUBBER: Record<Exclude<LockStatus, 'LOCKED'>, { word: string; font: number; fit: number; dashed: boolean }> = {
  STRUCK: { word: 'PERJURY', font: 46, fit: 178, dashed: false },
  UNSWORN: { word: 'UNSWORN', font: 42, fit: 180, dashed: true },
  FABRICATED: { word: 'FABRICATED', font: 35, fit: 190, dashed: true },
};

export function Stamp({ status, size = 200 }: { status: LockStatus; size?: number }) {
  const mask = `cc-stamp-${useId().replace(/[^\w-]/g, '')}`;

  if (status === 'LOCKED') {
    return (
      <WaxSeal tone="brass" size={size} label="Sworn, locked" className="cc-stamp cc-stamp--locked">
        {SEAL_LINES.map(([word, y, fit]) => (
          <g key={word} className="cc-stamp__word" fontSize="32" textAnchor="middle">
            <text x="77" y={y} dx="-1.2" dy="-1.2" fill="var(--wax)" textLength={fit} lengthAdjust="spacingAndGlyphs">
              {word}
            </text>
            <text x="77" y={y} fill="var(--ink)" textLength={fit} lengthAdjust="spacingAndGlyphs">
              {word}
            </text>
          </g>
        ))}
        <path
          d="M46 79H68M86 79H108M77 74L82 79L77 84L72 79Z"
          fill="var(--ink)"
          stroke="var(--ink)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <Puffs at={SEAL_PUFFS} />
      </WaxSeal>
    );
  }

  const { word, font, fit, dashed } = RUBBER[status];
  return (
    <svg
      className={`cc-stamp cc-stamp--ink cc-stamp--${status.toLowerCase()}`}
      viewBox="0 0 240 110"
      width={size}
      height={Math.round((size * 110) / 240)}
      role="img"
      aria-label={word}
    >
      <mask id={mask} maskUnits="userSpaceOnUse" x="0" y="0" width="240" height="110">
        <rect width="240" height="110" fill="#fff" />
        {SPECKS.map(([x, y, r]) => (
          <circle key={`${x},${y}`} cx={x} cy={y} r={r} fill="#000" />
        ))}
        <path d={SCRATCHES} stroke="#000" strokeWidth="1.4" strokeLinecap="round" />
      </mask>
      <g mask={`url(#${mask})`} fill="none" stroke="currentColor" strokeLinejoin="round" strokeLinecap="round">
        <path d={FRAME_OUT} strokeWidth="7" strokeDasharray={dashed ? '16 9' : undefined} />
        <path d={FRAME_IN} strokeWidth="2.6" />
        <text
          className="cc-stamp__word"
          x="120"
          y="56"
          fill="currentColor"
          stroke="none"
          fontSize={font}
          textAnchor="middle"
          dominantBaseline="central"
          textLength={fit}
          lengthAdjust="spacingAndGlyphs"
        >
          {word}
        </text>
      </g>
      <Puffs at={RUBBER_PUFFS} />
    </svg>
  );
}
