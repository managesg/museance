import type { ReactNode } from 'react';
import type { GuyKind, GuyState } from '../engine/types';
import './littleguy.css';

type Pt = [number, number];
type Pose = 'rest' | 'up' | 'hips' | 'limp';
type EyeLook = 'open' | 'small' | 'happy' | 'x' | 'hollow';
type MouthLook = 'smile' | 'grin' | 'wobble' | 'flat' | 'o';

interface Rig {
  arms: [Pt, Pt];
  hips: [number, number, number];
  eyes: [number, number, number, number];
  mouth: Pt;
  chest: Pt;
  crack: string;
  patch: Pt;
  spark: Pt;
}

const GROUND = 156;
const INK = 'var(--ink)';

const RIGS: Record<GuyKind, Rig> = {
  calculator: { arms: [[41, 86], [120, 86]], hips: [60, 100, 130], eyes: [66, 94, 80, 8], mouth: [80, 94], chest: [102, 118], crack: 'M57 38L64 47L58 53L67 66M64 47L72 50', patch: [63, 52], spark: [126, 28] },
  keycap: { arms: [[33, 98], [127, 98]], hips: [62, 98, 131], eyes: [67, 93, 102, 7], mouth: [80, 118], chest: [113, 124], crack: 'M90 40L84 52L92 60L85 72L91 87M92 60L101 63', patch: [88, 62], spark: [130, 32] },
  brush: { arms: [[49, 88], [111, 88]], hips: [70, 90, 132], eyes: [68, 92, 80, 7], mouth: [80, 90], chest: [80, 117], crack: 'M72 102L80 110L73 118L83 129', patch: [77, 115], spark: [120, 22] },
  clock: { arms: [[39, 100], [121, 100]], hips: [64, 96, 132], eyes: [69, 91, 81, 6], mouth: [80, 113], chest: [108, 125], crack: 'M54 88L63 96L57 104L68 115', patch: [61, 101], spark: [126, 50] },
  checkbox: { arms: [[40, 92], [120, 92]], hips: [62, 98, 128], eyes: [66, 94, 94, 7], mouth: [80, 111], chest: [108, 114], crack: 'M110 38L103 50L110 58L101 72', patch: [52, 117], spark: [128, 28] },
  trash: { arms: [[46, 84], [114, 84]], hips: [64, 96, 131], eyes: [68, 92, 80, 7], mouth: [80, 96], chest: [102, 118], crack: 'M100 60L93 72L100 80L92 94', patch: [96, 114], spark: [132, 22] },
  listitem: { arms: [[24, 92], [136, 92]], hips: [62, 98, 122], eyes: [68, 92, 98, 6], mouth: [80, 110], chest: [116, 106], crack: 'M122 52L115 62L122 70L114 84', patch: [44, 102], spark: [128, 34] },
};

// glitch entry is the pre-break look; the held broken pose is fixed below
const LOOKS: Record<GuyState, { eyes: EyeLook; mouth: MouthLook; arms: Pose }> = {
  idle: { eyes: 'open', mouth: 'smile', arms: 'rest' },
  nervous: { eyes: 'small', mouth: 'wobble', arms: 'up' },
  glitch: { eyes: 'open', mouth: 'o', arms: 'up' },
  locked: { eyes: 'happy', mouth: 'grin', arms: 'hips' },
  repaired: { eyes: 'open', mouth: 'smile', arms: 'rest' },
  fabricated: { eyes: 'hollow', mouth: 'o', arms: 'rest' },
};

// [control, end] relative to the shoulder; x points away from the body
const POSES: Record<Pose, [Pt, Pt]> = {
  rest: [[10, 8], [17, 22]],
  up: [[12, -4], [17, -20]],
  hips: [[18, 8], [3, 20]],
  limp: [[3, 14], [5, 28]],
};

const n = (v: number) => Math.round(v * 10) / 10;

function arm([x, y]: Pt, dir: 1 | -1, pose: Pose): string {
  const [[cx, cy], [ex, ey]] = POSES[pose];
  const hx = x + dir * ex, hy = y + ey;
  const a = Math.atan2(ey - cy, dir * (ex - cx));
  const fingers = [-0.7, 0, 0.7].map((t) => `M${hx} ${hy}l${n(5 * Math.cos(a + t))} ${n(5 * Math.sin(a + t))}`).join('');
  return `M${x} ${y}Q${x + dir * cx} ${y + cy} ${hx} ${hy}${fingers}`;
}

function leg(x: number, y: number, dir: 1 | -1, spread: number): string {
  return `M${x} ${y}Q${x + dir * (spread / 2 + 1)} ${(y + GROUND) / 2} ${x + dir * spread} ${GROUND}l${dir * 7} 0`;
}

function seal(x: number, y: number, r: number): string {
  const p = (ang: number, rr: number) => `${n(x + rr * Math.cos(ang))} ${n(y + rr * Math.sin(ang))}`;
  let d = `M${p(0, r)}`;
  for (let i = 0; i < 12; i++) d += `Q${p(((i + 0.5) * Math.PI) / 6, r * 1.25)} ${p(((i + 1) * Math.PI) / 6, r)}`;
  return `${d}Z`;
}

const MOUTHS: Record<MouthLook, (x: number, y: number) => ReactNode> = {
  smile: (x, y) => <path d={`M${x - 7} ${y}Q${x} ${y + 7} ${x + 7} ${y}`} strokeWidth={3.5} />,
  grin: (x, y) => <path d={`M${x - 9} ${y - 1}Q${x} ${y + 13} ${x + 9} ${y - 1}Z`} fill="var(--crimson-deep)" strokeWidth={3.5} />,
  wobble: (x, y) => <path d={`M${x - 9} ${y + 1}l3 -3l3 3l3 -3l3 3l3 -3`} strokeWidth={3} />,
  flat: (x, y) => <path d={`M${x - 7} ${y + 2}L${x + 7} ${y - 1}`} strokeWidth={3.5} />,
  o: (x, y) => <ellipse cx={x} cy={y + 2} rx={3.5} ry={4.5} fill={INK} strokeWidth={2} />,
};

function Face({ rig, eyes, mouth }: { rig: Rig; eyes: EyeLook; mouth: MouthLook }) {
  const [lx, rx, y, r] = rig.eyes;
  return (
    <g className="lg-face" fill="none" stroke={INK} strokeLinecap="round" strokeLinejoin="round">
      {[lx, rx].map((x) =>
        eyes === 'happy' ? (
          <path key={x} d={`M${x - r} ${y + 2}Q${x} ${y - r - 2} ${x + r} ${y + 2}`} strokeWidth={4} />
        ) : eyes === 'x' ? (
          <path key={x} d={`M${x - 5} ${y - 5}l10 10m0 -10l-10 10`} strokeWidth={4} />
        ) : (
          <g key={x}>
            <ellipse cx={x} cy={y} rx={r} ry={r + 1} fill={eyes === 'hollow' ? 'var(--ghost)' : 'var(--belly)'} strokeWidth={3.5} />
            {eyes !== 'hollow' && <circle className="lg-pupil" cx={x} cy={y + 1} r={eyes === 'small' ? 2.2 : r * 0.48} fill={INK} stroke="none" />}
          </g>
        ),
      )}
      {MOUTHS[mouth](...rig.mouth)}
    </g>
  );
}

const OPS: Record<string, string> = {
  '+': 'M80 51V77M67 64H93',
  '-': 'M67 64H93', '−': 'M67 64H93', '÷': 'M67 64H93', '/': 'M67 64H93',
  '×': 'M70 54L90 74M90 54L70 74', x: 'M70 54L90 74M90 54L70 74', '*': 'M70 54L90 74M90 54L70 74',
  '=': 'M68 58H92M68 70H92',
};

function Glyph({ g }: { g: string }) {
  if (g === '.') return <circle cx={80} cy={70} r={5.5} fill="var(--paper)" stroke={INK} strokeWidth={3} />;
  const d = OPS[g];
  if (!d) return <text className="lg-glyph" x={80} y={78} textAnchor="middle">{g.slice(0, 2)}</text>;
  return (
    <g fill="none" strokeLinecap="round">
      <path d={d} stroke={INK} strokeWidth={11} />
      <path className="lg-glyph-in" d={d} strokeWidth={5} />
      {(g === '÷' || g === '/') && [52, 76].map((cy) => <circle key={cy} cx={80} cy={cy} r={4} fill="var(--paper)" stroke={INK} strokeWidth={3} />)}
    </g>
  );
}

// pre plays during the ~600ms glitch, post is the held broken pose
function Glitchy({ on, pre, cycle, post }: { on: boolean; pre: ReactNode; cycle: ReactNode[]; post: ReactNode }) {
  if (!on) return pre;
  return (
    <>
      <g className="lg-pre">
        {cycle.map((c, i) => <g key={i} className="lg-cyc" style={{ animationDelay: `${-60 * i}ms` }}>{c}</g>)}
      </g>
      <g className="lg-post">{post}</g>
    </>
  );
}

const lcd = (t: string) => <text className="lg-lcd" x={108} y={61} textAnchor="end">{t}</text>;
const KEY_FILLS = ['paper-deep', 'paper-deep', 'paper-deep', 'paper-deep', 'brass', 'terracotta'];
const CALC = 'M47 30C62 27 98 27 113 30Q120 31 120 38L121 122Q121 130 113 130C96 132 64 132 47 130Q40 129 40 122L41 38Q41 31 47 30Z';
const BELL = 'M-15 3C-15 -13 15 -13 15 3Z';
const BOX = 'M46 34C66 32 94 32 114 34Q120 35 120 41L120 121Q120 127 114 128C94 130 66 130 46 128Q40 127 40 121L40 41Q40 35 46 34Z';
const ROW = 'M30 50C60 48 100 48 130 50Q136 51 136 57L136 115Q136 122 130 122C100 124 60 124 30 122Q24 122 24 115L24 57Q24 51 30 50Z';
const tick = (d: string) => (
  <g fill="none" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} stroke={INK} strokeWidth={13} />
    <path d={d} stroke="var(--wall)" strokeWidth={6} />
  </g>
);
const TICK = 'M56 62L72 78L106 32';
const lines = (d: string) => <path d={d} fill="none" stroke="var(--wood-light)" strokeWidth={4.5} strokeLinecap="round" strokeLinejoin="round" />;
const SCRAMBLE = ['M64 60H96M80 70H128M56 80H74', 'M56 67L124 61M60 77H90', 'M88 64H124M56 64H78M70 78H112', 'M56 71H124'];

function Body({ kind, glitch, glyph }: { kind: GuyKind; glitch: boolean; glyph: string }) {
  const ink = { stroke: INK, strokeWidth: 5, strokeLinejoin: 'round' as const, strokeLinecap: 'round' as const };
  switch (kind) {
    case 'calculator':
      return (
        <>
          <path d={CALC} transform="translate(5 4)" fill="var(--slate-deep)" {...ink} />
          <path className="lg-sil" d={CALC} fill="var(--slate)" {...ink} />
          <path d="M50 38C68 37 92 37 110 38Q113 38 113 41L113 63Q113 66 110 66C92 67 68 67 50 66Q47 66 47 63L47 41Q47 38 50 38Z" fill="var(--paper)" {...ink} strokeWidth={4} />
          <Glitchy on={glitch} pre={lcd('0')} cycle={['#&!', '7E?', 'NaN', '8.8'].map(lcd)} post={lcd('Err')} />
          {KEY_FILLS.map((f, i) => (
            <rect key={i} x={50 + (i % 3) * 23} y={106 + Math.floor(i / 3) * 12} width={14} height={8} rx={2.5} fill={`var(--${f})`} stroke={INK} strokeWidth={3} />
          ))}
        </>
      );
    case 'keycap':
      return (
        <>
          <path className="lg-sil" d="M44 36C70 33 92 33 116 36Q123 37 124 44L129 122Q130 130 122 131C96 133 64 133 38 131Q30 130 31 122L36 44Q37 37 44 36Z" fill="var(--terracotta-deep)" {...ink} />
          <path d="M47 85L35 126M113 85L125 126" {...ink} strokeWidth={3} />
          <path d="M50 40C68 38 92 38 110 40Q115 41 115 46L114 82Q114 87 109 87C92 89 68 89 51 87Q46 87 46 82L45 46Q45 41 50 40Z" fill="var(--terracotta)" {...ink} strokeWidth={4} />
          <Glitchy on={glitch} pre={<Glyph g={glyph} />} cycle={['×', '=', '÷', '7'].map((g) => <Glyph key={g} g={g} />)} post={<Glyph g="?" />} />
        </>
      );
    case 'brush':
      return (
        <>
          <path className="lg-sil" d="M57 100L103 100L97 130Q80 136 63 130Z" fill="var(--wood)" {...ink} />
          <path d="M67 106L70 126" stroke="var(--wood-light)" strokeWidth={4} strokeLinecap="round" />
          <path className="lg-sil" d="M54 60C50 42 56 26 70 18C76 14 84 14 90 18C104 26 110 42 106 60Z" fill="var(--wood-light)" {...ink} />
          <path d="M62 30C66 21 74 17 80 17C86 17 94 21 98 30C90 34 70 34 62 30Z" fill="var(--crimson)" {...ink} strokeWidth={4} />
          <path d="M70 36C68 43 68 50 70 57M80 36V57M90 36C92 43 92 50 90 57" fill="none" stroke="var(--wood)" strokeWidth={3} strokeLinecap="round" />
          <path className="lg-sil" d="M51 58C68 56 92 56 109 58Q112 59 112 63L111 96Q111 100 107 100C90 102 70 102 53 100Q49 100 49 96L48 63Q48 59 51 58Z" fill="var(--brass)" {...ink} />
          <path d="M52 66C70 68 90 68 108 66" fill="none" stroke="var(--brass-deep)" strokeWidth={3} strokeLinecap="round" />
        </>
      );
    case 'clock':
      return (
        <>
          <path d="M60 36C62 17 98 17 100 36" fill="none" {...ink} />
          <g transform="translate(52 46) rotate(-28)">
            <path d={BELL} fill="var(--brass)" {...ink} strokeWidth={4.5} />
            <circle cy={-11} r={3} fill="var(--brass-deep)" stroke={INK} strokeWidth={2.5} />
          </g>
          <g className="lg-bell-r">
            <g transform="translate(108 46) rotate(28)">
              <path d={BELL} fill="var(--brass)" {...ink} strokeWidth={4.5} />
              <circle cy={-11} r={3} fill="var(--brass-deep)" stroke={INK} strokeWidth={2.5} />
            </g>
          </g>
          <path className="lg-sil" d="M80 52C104 51 123 70 122 94C122 118 104 136 80 136C56 137 38 118 38 94C37 70 56 52 80 52Z" fill="var(--wood)" {...ink} />
          <path d="M80 62C98 62 112 76 112 94C112 112 98 126 80 126C62 126 48 112 48 94C48 76 62 62 80 62Z" fill="var(--paper)" {...ink} strokeWidth={4} />
          <path d="M80 66V71M52 94H57M103 94H108" {...ink} strokeWidth={3} />
          <path className="lg-hand lg-hand-h" d="M80 94L69 100" {...ink} strokeWidth={5} />
          <path className="lg-hand lg-hand-m" d="M80 94L95 103" {...ink} strokeWidth={3.5} />
          <circle cx={80} cy={94} r={3.2} fill={INK} />
        </>
      );
    case 'checkbox':
      return (
        <>
          <path d={BOX} transform="translate(5 4)" fill="var(--floor-shadow)" {...ink} />
          <path className="lg-sil" d={BOX} fill="var(--paper)" {...ink} />
          <path d="M50 44C68 43 92 43 110 44" fill="none" stroke="var(--paper-deep)" strokeWidth={4} strokeLinecap="round" />
          <Glitchy on={glitch} pre={tick(TICK)} cycle={[tick(TICK), null, tick(TICK), null]} post={tick('M54 64L66 77M76 72L102 40')} />
        </>
      );
    case 'trash':
      return (
        <>
          <path className="lg-sil" d="M44 56L116 56L110 129Q80 134 50 129Z" fill="var(--slate)" {...ink} />
          <path d="M62 106L63 124M80 106V126M98 106L97 124" fill="none" stroke="var(--slate-deep)" strokeWidth={4} strokeLinecap="round" />
          <g className="lg-lid">
            <path d="M68 42C68 33 92 33 92 42" fill="none" {...ink} strokeWidth={4.5} />
            <path className="lg-sil" d="M42 42C68 40 92 40 118 42Q123 43 123 48L122 52Q122 56 117 56L43 56Q38 56 38 52L38 48Q38 43 42 42Z" fill="var(--slate-deep)" {...ink} strokeWidth={4.5} />
          </g>
        </>
      );
    case 'listitem':
      return (
        <>
          <path d={ROW} transform="translate(4 4)" fill="var(--floor-shadow)" {...ink} />
          <path className="lg-sil" d={ROW} fill="var(--paper)" {...ink} />
          <circle cx={42} cy={70} r={6} fill={INK} />
          <Glitchy on={glitch} pre={lines('M56 64H124M56 78H104')} cycle={SCRAMBLE.map(lines)} post={lines('M56 64l8 -5l8 9l8 -9l8 9l8 -9l8 9l8 -5M56 79H70M84 77H104')} />
        </>
      );
  }
}

// crumpled paper that spills out when the trash lid flies open
const SPILL: [number, number, number][] = [[126, 30, 0], [140, 54, 40], [110, 12, -25], [140, 86, 15], [96, 20, 60]];
const BALL = 'M-6 -4L-1 -7L5 -5L7 1L3 6L-4 6L-7 1Z';

const SPLAT: [number, number, number][] = [[36, 26, 4], [124, 18, 3], [132, 54, 5], [28, 66, 3], [24, 110, 4.5], [136, 104, 3], [120, 150, 4], [40, 150, 3], [60, 8, 2.5], [104, 6, 3.5]];

function Tag({ text }: { text: string }) {
  const t = text.length > 14 ? `${text.slice(0, 13)}…` : text;
  const squeeze = t.length * 18 > 140; // Courier Prime advance is 0.6em at 30px
  return (
    <g className="lg-tag" transform="rotate(-2 80 181)">
      <path d="M8 166C50 164 110 164 152 166Q156 166 156 170L156 194Q156 198 152 198C110 199 50 199 8 198Q4 198 4 194L4 170Q4 166 8 166Z" fill="var(--paper)" stroke={INK} strokeWidth={3} />
      <text x={80} y={189} textAnchor="middle" textLength={squeeze ? 140 : undefined} lengthAdjust={squeeze ? 'spacingAndGlyphs' : undefined}>{t}</text>
    </g>
  );
}

export function LittleGuy({ kind, glyph, state, label }: { kind: GuyKind; glyph?: string; state: GuyState; label?: string }) {
  const rig = RIGS[kind] ?? RIGS.keycap;
  const look = LOOKS[state] ?? LOOKS.idle;
  const glitch = state === 'glitch';
  const arms = (pose: Pose) => (
    <path className="lg-arms" d={arm(rig.arms[0], -1, pose) + arm(rig.arms[1], 1, pose)} fill="none" stroke={INK} strokeWidth={4.5} strokeLinecap="round" strokeLinejoin="round" />
  );
  const [hl, hr, hy] = rig.hips;
  const spread = state === 'locked' ? 9 : 4;
  const [sx, sy] = rig.spark;
  const [px, py] = rig.patch;
  const [cx, cy] = rig.chest;
  return (
    <svg className={`lg lg--${kind} is-${state}`} viewBox="0 0 160 200" width="100%" height="100%" preserveAspectRatio="xMidYMax meet" role="img" overflow="visible">
      <title>{`${label ? `${label} ` : ''}${kind}: ${state}`}</title>
      <ellipse className="lg-shadow" cx={80} cy={157} rx={42} ry={6} fill="var(--floor-shadow)" />
      <g className="lg-rig">
        <path className="lg-legs" d={leg(hl, hy, -1, spread) + leg(hr, hy, 1, spread)} fill="none" stroke={INK} strokeWidth={4.5} strokeLinecap="round" strokeLinejoin="round" />
        <g className="lg-upper">
          {glitch ? <><g className="lg-pre">{arms('up')}</g><g className="lg-post">{arms('limp')}</g></> : arms(look.arms)}
          <g className="lg-body"><Body kind={kind} glitch={glitch} glyph={glyph ?? '+'} /></g>
          {glitch ? (
            <>
              <g className="lg-pre"><Face rig={rig} eyes={look.eyes} mouth={look.mouth} /></g>
              <g className="lg-post">
                <Face rig={rig} eyes="x" mouth="flat" />
                <path className="lg-crack" d={rig.crack} fill="none" stroke={INK} strokeWidth={3.5} strokeLinecap="round" strokeLinejoin="round" />
              </g>
            </>
          ) : (
            <Face rig={rig} eyes={look.eyes} mouth={look.mouth} />
          )}
          {state === 'nervous' && (
            <path className="lg-sweat" d={`M${sx + 2} ${sy + 12}c6 8 4 12 0 12s-6 -4 0 -12Z`} fill="var(--paper)" stroke={INK} strokeWidth={2.5} strokeLinejoin="round" />
          )}
          {state === 'locked' && (
            <>
              <g className="lg-badge">
                <path d={seal(cx, cy, 13)} fill="var(--brass)" stroke={INK} strokeWidth={3} strokeLinejoin="round" />
                <circle cx={cx} cy={cy} r={8.5} fill="none" stroke="var(--brass-deep)" strokeWidth={2.5} />
                <path d={`M${cx - 3} ${cy - 1}v-2.5a3 3 0 0 1 6 0v2.5`} fill="none" stroke={INK} strokeWidth={2} />
                <rect x={cx - 4.5} y={cy - 1} width={9} height={6.5} rx={1.5} fill={INK} />
              </g>
              <g className="lg-puff">
                {[[-17, -8], [17, -10], [-13, 14], [15, 13]].map(([dx, dy]) => <circle key={dx} cx={cx + dx} cy={cy + dy} r={4} fill="var(--paper-deep)" />)}
              </g>
            </>
          )}
          {state === 'repaired' && (
            <>
              <g className="lg-patch">
                {[38, -38].map((a) => <rect key={a} x={px - 15} y={py - 5.5} width={30} height={11} rx={3.5} transform={`rotate(${a} ${px} ${py})`} fill="var(--floor)" stroke={INK} strokeWidth={3} />)}
                <circle cx={px} cy={py} r={2} fill="var(--floor-shadow)" />
              </g>
              <path className="lg-spark" d={`M${sx} ${sy - 10}Q${sx + 2} ${sy - 2} ${sx + 10} ${sy}Q${sx + 2} ${sy + 2} ${sx} ${sy + 10}Q${sx - 2} ${sy + 2} ${sx - 10} ${sy}Q${sx - 2} ${sy - 2} ${sx} ${sy - 10}Z`} fill="var(--flame-core)" stroke={INK} strokeWidth={2.5} strokeLinejoin="round" />
            </>
          )}
        </g>
      </g>
      {kind === 'brush' && glitch && (
        <g className="lg-splat">
          {SPLAT.map(([x, y, r], i) => <circle key={i} cx={x} cy={y} r={r} fill={INK} style={{ animationDelay: `${i * 55}ms` }} />)}
        </g>
      )}
      {kind === 'trash' && glitch && (
        <g className="lg-spill">
          {SPILL.map(([x, y, a], i) => (
            <g key={i} transform={`translate(${x} ${y}) rotate(${a})`}>
              <g className="lg-bit" style={{ animationDelay: `${600 + i * 55}ms` }}>
                <path d={BALL} fill="var(--paper)" stroke={INK} strokeWidth={2.5} strokeLinejoin="round" />
                <path d="M-3 -2L1 1L4 -2M-2 3L1 1" fill="none" stroke={INK} strokeWidth={1.5} strokeLinecap="round" />
              </g>
            </g>
          ))}
        </g>
      )}
      {label && <Tag text={label} />}
    </svg>
  );
}
