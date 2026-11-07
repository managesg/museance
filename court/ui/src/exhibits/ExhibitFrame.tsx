import { useEffect, useRef, useState, type ReactNode, type Ref } from 'react';
import type { ExhibitMode } from '../engine/types';
import './exhibits.css';

type Which = 'original' | 'revival';
type Output = { text: string; tone: 'match' | 'diverge' | 'neutral' };
type Box = readonly [x: number, y: number, w: number, h: number];
type Spot = { x: number; y: number; r: number };

// Everything is drawn on the 500x440 stage zone; exhibits.css places the HTML layers on the same numbers.
const W = 500;
const H = 440;
const inset = ([x, y, w, h]: Box, d: number): Box => [x + d, y + d, w - 2 * d, h - 2 * d];
const shift = ([x, y, w, h]: Box, dx: number, dy: number): Box => [x + dx, y + dy, w, h];
const OUT: Box = [16, 14, 468, 366];
const BEADS = inset(OUT, 10);
const COVE = inset(OUT, 20);
const RAIL_IN = inset(OUT, 30);
const LINER_IN = inset(OUT, 38);
const SCREEN = inset(OUT, 50);
const PLATE: Box = [72, 356, 356, 72];
// Where the magnifier waits until runSteps names the element it reads.
const FALLBACK: Spot = { x: 250, y: 124, r: 40 };

const f = (v: number) => Math.round(v * 10) / 10;
// Deterministic noise in [-1, 1]: the inked edges tremble the same way on every render.
const noise = (k: number) => {
  const s = Math.sin(k * 12.9898 + 4.1414) * 43758.5453;
  return (s - Math.floor(s)) * 2 - 1;
};
const polar = (cx: number, cy: number, r: number, deg: number) =>
  [cx + r * Math.cos((deg * Math.PI) / 180), cy + r * Math.sin((deg * Math.PI) / 180)] as const;

// A rectangle with nudged corners and gently bowed edges, as if inked by hand.
function rough([x, y, w, h]: Box, seed: number, wob = 1): string {
  const p = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]].map(([px, py], i) => [
    px + noise(seed + i) * wob,
    py + noise(seed + i + 9) * wob,
  ]);
  const edges = p.map(([ax, ay], i) => {
    const [bx, by] = p[(i + 1) % 4];
    const len = Math.hypot(bx - ax, by - ay);
    const bow = noise(seed + i + 20) * wob * 1.5;
    return `Q${f((ax + bx) / 2 - ((by - ay) / len) * bow)} ${f((ay + by) / 2 + ((bx - ax) / len) * bow)} ${f(bx)} ${f(by)}`;
  });
  return `M${f(p[0][0])} ${f(p[0][1])}${edges.join('')}Z`;
}

// The lower and right sides of the band between two boxes, mitred at the corners: the shade side of a moulding lit from the upper left.
function lowerRight([ox, oy, ow, oh]: Box, [ix, iy, iw, ih]: Box): string {
  return `M${ox + ow} ${oy}V${oy + oh}H${ox}L${ix} ${iy + ih}H${ix + iw}V${iy}Z`;
}
function upperLeft([ox, oy, ow, oh]: Box, [ix, iy, iw, ih]: Box): string {
  return `M${ox} ${oy + oh}V${oy}H${ox + ow}L${ix + iw} ${iy}H${ix}V${iy + ih}Z`;
}

// A four-lobed cast ornament, smoothed through midpoints.
function rosette(cx: number, cy: number, r: number): string {
  const pts = Array.from({ length: 24 }, (_, i) => polar(cx, cy, r * (1 + 0.22 * Math.cos((i * Math.PI) / 3 + Math.PI)), i * 15));
  const mid = (i: number) => {
    const [a, b] = [pts[i % 24], pts[(i + 1) % 24]];
    return `${f((a[0] + b[0]) / 2)} ${f((a[1] + b[1]) / 2)}`;
  };
  return `M${mid(23)}${pts.map(([px, py], i) => `Q${f(px)} ${f(py)} ${mid(i)}`).join('')}Z`;
}

// A plaque with scooped corners.
function plaque([x, y, w, h]: Box, c = 10): string {
  return (
    `M${x + c} ${y}H${x + w - c}Q${x + w - c} ${y + c} ${x + w} ${y + c}V${y + h - c}` +
    `Q${x + w - c} ${y + h - c} ${x + w - c} ${y + h}H${x + c}Q${x + c} ${y + h - c} ${x} ${y + h - c}V${y + c}Q${x + c} ${y + c} ${x + c} ${y}Z`
  );
}

const sparkle = (x: number, y: number, s: number) =>
  `M${x} ${y - s}Q${x} ${y} ${x + s} ${y}Q${x} ${y} ${x} ${y + s}Q${x} ${y} ${x - s} ${y}Q${x} ${y} ${x} ${y - s}Z`;

// A fan shell on the top rail: scalloped ribs meeting at the hinge.
const SHELL = { cx: 250, cy: 38, r: 32 };
const RIBS = Array.from({ length: 8 }, (_, i) => 180 + (i * 180) / 7);
const SHELL_D =
  `M${SHELL.cx - SHELL.r} ${SHELL.cy}` +
  RIBS.slice(1)
    .map((a, i) => {
      const [mx, my] = polar(SHELL.cx, SHELL.cy, SHELL.r * 1.2, (a + RIBS[i]) / 2);
      const [ex, ey] = polar(SHELL.cx, SHELL.cy, SHELL.r, a);
      return `Q${f(mx)} ${f(my)} ${f(ex)} ${f(ey)}`;
    })
    .join('') +
  `Q${SHELL.cx} ${SHELL.cy + 14} ${SHELL.cx - SHELL.r} ${SHELL.cy}Z`;
const SHELL_RIBS = RIBS.slice(1, -1)
  .map((a) => {
    const [x, y] = polar(SHELL.cx, SHELL.cy, SHELL.r * 0.92, a);
    return `M${SHELL.cx} ${SHELL.cy + 5}L${f(x)} ${f(y)}`;
  })
  .join('');

// A cobweb strung in the upper-right corner of the window, sagging between its spokes.
const WEB = (() => {
  const [cx, cy] = [RAIL_IN[0] + RAIL_IN[2], RAIL_IN[1]];
  const at = (r: number, a: number) => polar(cx, cy, r, a).map(f).join(' ');
  const spokes = [178, 150, 122, 94];
  const threads = spokes.map((a) => `M${cx} ${cy}L${at(56, a)}`).join('');
  const rings = [15, 29, 43]
    .map((r) => spokes.slice(1).map((a, i) => `M${at(r, spokes[i])}Q${at(r * 0.78, (a + spokes[i]) / 2)} ${at(r, a)}`).join(''))
    .join('');
  return threads + rings;
})();

const ink = (w: number) => ({ fill: 'none', stroke: 'var(--ink)', strokeWidth: w });

function frameArt(which: Which) {
  const old = which === 'original';
  const railIn = rough(RAIL_IN, 7, 0.7);
  const rail = rough(OUT, 3) + railIn;
  const liner = railIn + rough(LINER_IN, 11, 0.5);
  const [px, py, pw, ph] = PLATE;
  const back = (
    <svg className="exhibit__back" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
      <path d={rough(shift(OUT, 9, 11), 41)} fill="var(--wall-deep)" />
      <path d={plaque(shift(PLATE, 6, 8))} fill="var(--wall-deep)" />
      <path d={railIn} fill={old ? 'var(--paper-deep)' : 'var(--paper)'} />
      <path d={rough(inset(SCREEN, -4), 19, 0.4)} fill={old ? 'var(--wax)' : 'var(--belly)'} />
      {old &&
        [[60, 146, 2.6], [59, 270, 1.8], [182, 58, 2.2], [312, 336, 2.8], [440, 214, 2], [338, 57, 1.6], [96, 337, 2]].map(
          ([x, y, r]) => <circle key={`${x}-${y}`} cx={x} cy={y} r={r} fill="var(--floor-shadow)" />,
        )}
    </svg>
  );
  const front = (
    <svg className="exhibit__front" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
      {/* picture wire up to an S-hook on the set's picture rail */}
      <path d="M250 -13L132 18M250 -13L368 18" {...ink(4.5)} />
      <path d="M250 -13L132 18M250 -13L368 18" fill="none" stroke="var(--brass)" strokeWidth="1.6" />
      <path d="M250 -11V-20Q250 -27 256 -27Q262 -27 262 -21" {...ink(6)} />
      <path d="M250 -11V-20Q250 -27 256 -27Q262 -27 262 -21" fill="none" stroke="var(--brass)" strokeWidth="2.5" />

      <path d={rail} fill="var(--brass)" fillRule="evenodd" />
      {old &&
        [[150, 21, 15, 4.5, -3], [476, 236, 3.8, 14, 2], [24, 296, 3.6, 11, -2], [446, 373, 10, 3.5, 4]].map(([x, y, rx, ry, a]) => (
          <ellipse key={`${x}-${y}`} cx={x} cy={y} rx={rx} ry={ry} transform={`rotate(${a} ${x} ${y})`} fill="var(--brass-deep)" />
        ))}
      <path d={lowerRight(COVE, RAIL_IN)} fill="var(--brass-deep)" />
      <path d={rough(COVE, 5, 0.7)} {...ink(2.5)} />
      <path d={rough(BEADS, 13, 0.5)} fill="none" stroke="var(--brass-deep)" strokeWidth="6" strokeDasharray="0.1 11" />
      <path d={rail} {...ink(5)} />

      <path d={liner} fill="var(--wood-light)" fillRule="evenodd" />
      <path d={upperLeft(RAIL_IN, inset(RAIL_IN, 4))} fill="var(--wood)" />
      <path d={rough(LINER_IN, 11, 0.5)} {...ink(3)} />

      {[[BEADS[0], BEADS[1]], [BEADS[0] + BEADS[2], BEADS[1]], [BEADS[0] + BEADS[2], BEADS[1] + BEADS[3]], [BEADS[0], BEADS[1] + BEADS[3]]].map(
        ([x, y]) => (
          <g key={`${x}-${y}`}>
            <path d={rosette(x, y, 16)} fill="var(--brass)" stroke="var(--ink)" strokeWidth="3.5" />
            <circle cx={x} cy={y} r="6" fill="var(--brass-deep)" stroke="var(--ink)" strokeWidth="2.5" />
          </g>
        ),
      )}

      <path d={SHELL_D} fill="var(--brass)" />
      <path d={SHELL_RIBS} fill="none" stroke="var(--brass-deep)" strokeWidth="3" />
      <path d={SHELL_D} {...ink(4)} />
      <ellipse cx={SHELL.cx} cy={SHELL.cy + 5} rx="9" ry="5" fill="var(--brass-deep)" stroke="var(--ink)" strokeWidth="3" />

      {old ? (
        <path d={WEB} fill="none" stroke="var(--ink)" strokeWidth="1.6" opacity="0.55" />
      ) : (
        <g fill="var(--paper)" stroke="var(--ink)" strokeWidth="2">
          <path d={sparkle(70, 22, 11)} />
          <path d={sparkle(472, 318, 8)} />
        </g>
      )}

      <path d={plaque(PLATE)} fill="var(--brass)" stroke="var(--ink)" strokeWidth="4" />
      <path d={plaque(inset(PLATE, 6), 7)} fill="none" stroke="var(--brass-deep)" strokeWidth="2.5" />
      {[px + 18, px + pw - 18].map((x) => (
        <g key={x}>
          <circle cx={x} cy={py + 18} r="5" fill="var(--brass-deep)" stroke="var(--ink)" strokeWidth="2" />
          <path d={`M${x - 3} ${py + 21}L${x + 3} ${py + 15}`} {...ink(1.8)} />
        </g>
      ))}
      <text className="exhibit__plate-title" x={W / 2} y={py + 31}>
        {old ? 'EXHIBIT O' : 'EXHIBIT R'}
      </text>
      <text className="exhibit__plate-sub" x={W / 2} y={py + ph - 14}>
        {old ? 'THE ORIGINAL · sealed oracle' : 'THE REVIVAL'}
      </text>
    </svg>
  );
  return { back, front };
}

const ART = { original: frameArt('original'), revival: frameArt('revival') };

const HEM = 'C170 270 152 252 132 262C112 271 94 252 74 262C54 271 30 252 -4 261';
// One velvet panel; the right one is the same art mirrored. Its right edge is where the pair meets.
const DRAPE = (
  <svg viewBox="0 0 190 266" preserveAspectRatio="none">
    <path d={`M-4 -4H190V258${HEM}Z`} fill="var(--crimson)" />
    {[22, 64, 106, 146].map((x) => (
      <path key={x} d={`M${x} -4C${x + 7} 80 ${x - 5} 170 ${x + 4} 262L${x + 17} 264C${x + 9} 170 ${x + 20} 80 ${x + 13} -4Z`} fill="var(--crimson-deep)" />
    ))}
    <path d="M190 246C170 258 152 240 132 250C112 259 94 240 74 250C54 259 30 240 -4 249" fill="none" stroke="var(--brass)" strokeWidth="6" />
    <path d={`M190 -4V258${HEM}`} {...ink(5)} />
  </svg>
);

const SWAGS = Array.from({ length: 8 }, (_, i) => `Q${368 - 46 * i - 23} 52 ${368 - 46 * (i + 1)} 30`).join('');
const VALANCE = (
  <svg viewBox="0 0 368 48" preserveAspectRatio="none">
    <path d={`M-4 -4H372V30H368${SWAGS}H-4Z`} fill="var(--crimson)" />
    <path d={`M368 30${SWAGS}`} transform="translate(0 -8)" fill="none" stroke="var(--brass)" strokeWidth="5" />
    <path d={`M372 30H368${SWAGS}H-4`} {...ink(4)} />
    {Array.from({ length: 7 }, (_, i) => 322 - 46 * i).map((x) => (
      <path key={x} d={`M${x} 29L${x - 5} 42Q${x} 47 ${x + 5} 42Z`} fill="var(--brass)" stroke="var(--ink)" strokeWidth="2.5" />
    ))}
  </svg>
);

const PARCHMENT = (
  <svg viewBox="0 0 396 294" preserveAspectRatio="none" aria-hidden="true">
    <path d={rough([10, 10, 376, 274], 61, 2.2)} fill="var(--paper)" stroke="var(--ink)" strokeWidth="3" />
    <path d={rough([22, 22, 352, 250], 67, 1.2)} fill="none" stroke="var(--paper-deep)" strokeWidth="3" />
    <ellipse cx="330" cy="62" rx="26" ry="15" transform="rotate(-18 330 62)" fill="var(--paper-deep)" opacity="0.7" />
    <ellipse cx="74" cy="238" rx="18" ry="10" transform="rotate(12 74 238)" fill="var(--paper-deep)" opacity="0.6" />
  </svg>
);

// Where the observed text sits, in frame units. runSteps tags the iframe with the selector it reads.
function locate(root: HTMLElement, frame: HTMLIFrameElement): Spot | null {
  const sel = frame.dataset.exhibitObserve;
  const doc = frame.contentDocument;
  if (!sel || !doc) return null;
  let el: Element | null = null;
  try {
    el = doc.querySelector(sel);
  } catch {
    return null;
  }
  if (!el) return null;
  const text = doc.createRange();
  text.selectNodeContents(el);
  const t = text.getBoundingClientRect();
  const r = t.width || t.height ? t : el.getBoundingClientRect();
  const fr = frame.getBoundingClientRect();
  const box = root.getBoundingClientRect();
  if (!box.width || !box.height || !frame.clientWidth) return null;
  // Screen px per iframe px: the frame's zoom times however the integration scales the stage.
  const k = fr.width / frame.clientWidth;
  const sx = W / box.width;
  const sy = H / box.height;
  const [x0, y0, w, h] = SCREEN;
  const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
  return {
    x: clamp((fr.left - box.left + (r.left + r.width / 2) * k) * sx, x0, x0 + w),
    y: clamp((fr.top - box.top + (r.top + r.height / 2) * k) * sy, y0, y0 + h),
    r: clamp(Math.max(r.width * k * sx, r.height * k * sy) / 2 + 12, 30, 110),
  };
}

function Cross({ spot, output }: { spot: Spot; output: Output | null }) {
  const { x, y, r } = spot;
  // The handle runs level toward the middle, along the observed row, so it keeps clear of the keys being pressed; the tag hangs from its end.
  const angle = x < W / 2 ? 0 : 180;
  const [ex, ey] = polar(x, y, r + 54, angle);
  const handle = `M${r + 15} -9H${r + 46}Q${r + 54} -9 ${r + 54} 0Q${r + 54} 9 ${r + 46} 9H${r + 15}Z`;
  const [gx, gy] = polar(0, 0, r * 0.62, 200);
  const [hx, hy] = polar(0, 0, r * 0.62, 250);
  const [sx, sy] = polar(0, 0, r + 2, -20);
  const [tx, ty] = polar(0, 0, r + 2, 110);
  const len = output?.text.length ?? 0;
  const size = len <= 6 ? 'l' : len <= 10 ? 'm' : 's';
  // The tag may run from the handle's end to the frame's edge, less a margin; longer text ends in an ellipsis.
  const room = (angle === 0 ? W - ex : ex) + 21 - 6;
  return (
    <>
      <svg className="exhibit__cross" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
        <g className="exhibit__lens" style={{ transform: `translate(${f(x)}px, ${f(y)}px)` }}>
          <g className="exhibit__lens-body">
            <g transform={`rotate(${angle})`}>
              <path d={`M${r + 2} -8H${r + 16}V8H${r + 2}Z`} fill="var(--brass)" stroke="var(--ink)" strokeWidth="3.5" />
              <path d={handle} fill="var(--wood-light)" />
              <path d={`M${r + 15} 3H${r + 53}Q${r + 51} 9 ${r + 46} 9H${r + 15}Z`} fill="var(--wood)" />
              <path d={handle} {...ink(4)} />
            </g>
            <circle r={r} fill="var(--ghost)" opacity="0.18" />
            <path d={`M${f(gx)} ${f(gy)}A${f(r * 0.62)} ${f(r * 0.62)} 0 0 1 ${f(hx)} ${f(hy)}`} fill="none" stroke="var(--paper)" strokeWidth="5" />
            <circle r={r} {...ink(15)} />
            <circle r={r} fill="none" stroke="var(--brass)" strokeWidth="9" />
            <path d={`M${f(sx)} ${f(sy)}A${r + 2} ${r + 2} 0 0 1 ${f(tx)} ${f(ty)}`} fill="none" stroke="var(--brass-deep)" strokeWidth="4" />
          </g>
        </g>
      </svg>
      {output && (
        <p
          className={`exhibit__tag exhibit__tag--${output.tone}`}
          data-side={angle === 0 ? 'right' : 'left'}
          data-size={size}
          style={{ left: `${(ex / W) * 100}%`, top: `${(ey / H) * 100}%`, maxWidth: `${(room / W) * 100}%` }}
        >
          <span className="exhibit__tag-verb">shows</span>
          <span className="exhibit__tag-value">{output.text || '(blank)'}</span>
        </p>
      )}
    </>
  );
}

/** One exhibit on the wall: a gilt frame around a live, same-origin iframe of the app, dressed per mode. */
export function ExhibitFrame({
  which,
  mode,
  src,
  title,
  output = null,
  children,
  frameRef,
}: {
  which: Which;
  mode: ExhibitMode;
  src: string;
  title: string;
  output?: Output | null;
  children?: ReactNode;
  frameRef?: Ref<HTMLIFrameElement>;
}) {
  const rootRef = useRef<HTMLElement>(null);
  const [spot, setSpot] = useState<Spot | null>(null);

  // Track the observed element while crossing: when a run starts (attribute), the page reloads, or a result lands.
  useEffect(() => {
    const root = rootRef.current;
    const frame = root?.querySelector('iframe');
    if (mode !== 'cross' || !root || !frame) return;
    const measure = () => setSpot(locate(root, frame));
    measure();
    const watch = new MutationObserver(measure);
    watch.observe(frame, { attributes: true, attributeFilter: ['data-exhibit-observe'] });
    frame.addEventListener('load', measure);
    return () => {
      watch.disconnect();
      frame.removeEventListener('load', measure);
    };
  }, [mode, output]);

  const art = ART[which];
  return (
    <figure
      ref={rootRef}
      className={`exhibit exhibit--${which} exhibit--${mode}`}
      aria-label={`${which === 'original' ? 'Exhibit O, the original' : 'Exhibit R, the revival'}: ${title}`}
    >
      {art.back}
      <div className="exhibit__screen">
        {/* No allow-modals: an alert() in a same-origin app would freeze the whole stage. */}
        <iframe
          ref={frameRef}
          className="exhibit__app"
          src={src || undefined}
          title={title}
          tabIndex={mode === 'live' ? 0 : -1}
          sandbox="allow-scripts allow-same-origin allow-forms"
        />
        {mode === 'booting' && (
          <div className="exhibit__crt" aria-hidden="true">
            <span className="exhibit__beam exhibit__beam--halo" />
            <span className="exhibit__beam" />
            <span className="exhibit__scan" />
          </div>
        )}
        <div className="exhibit__drape exhibit__drape--l" aria-hidden="true">
          {DRAPE}
        </div>
        <div className="exhibit__drape exhibit__drape--r" aria-hidden="true">
          {DRAPE}
        </div>
        <div className="exhibit__valance" aria-hidden="true">
          {VALANCE}
        </div>
      </div>
      {(mode === 'evidence' || mode === 'reading') && (
        <div className="exhibit__sheet">
          {PARCHMENT}
          <div className="exhibit__sheet-body">{children}</div>
        </div>
      )}
      {art.front}
      {mode === 'cross' && <Cross spot={spot ?? FALLBACK} output={output} />}
    </figure>
  );
}
