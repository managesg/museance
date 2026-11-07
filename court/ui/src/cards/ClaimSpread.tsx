import { useLayoutEffect, useRef, type CSSProperties } from 'react';
import type { CardView } from '../engine/types';
import { ClaimCard } from './ClaimCard';
import './cards.css';

// Card centre, tilt and width in zone pixels; height is always 1.5 × width.
interface Pose {
  x: number;
  y: number;
  r: number;
  w: number;
  z: number;
  focus: boolean;
}

const MIN_W = 112; // narrowest small card whose 20px text still fits
const PAD = 8;
const GAP = 8;
const ASIDE_TILT = [3, 5, 2, 4];

export function ClaimSpread({
  cards,
  focusId,
  width,
  height,
  showBets = false,
}: {
  cards: CardView[];
  focusId: string | null;
  width: number;
  height: number;
  // The gallery's chips show only while claims are sworn.
  showBets?: boolean;
}) {
  const poses = layout(cards, focusId, width, height, showBets);
  const keys = keysOf(cards);
  const nodes = useRef(new Map<string, HTMLDivElement>());
  const last = useRef(new Map<string, Pose>());

  // Animate from each card's previous pose to its new one before paint; unseen cards deal from the ball.
  useLayoutEffect(() => {
    const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
    let dealt = 0;
    keys.forEach((key, i) => {
      const el = nodes.current.get(key);
      const before = last.current.get(key);
      last.current.set(key, poses[i]);
      if (!el) return;
      if (!before) deal(el, poses[i], width / 2, height * 0.38, dealt++ * 110, calm);
      else if (moved(before, poses[i])) glide(el, before, poses[i], calm);
    });
    for (const key of last.current.keys()) if (!keys.includes(key)) last.current.delete(key);
  });

  return (
    <div className="cc-spread" style={{ width, height }}>
      {cards.map((view, i) => {
        const p = poses[i];
        const key = keys[i];
        return (
          <div
            key={key}
            className="cc-spread__slot"
            ref={(el) => {
              if (el) nodes.current.set(key, el);
              else nodes.current.delete(key);
            }}
            style={{ width: p.w, zIndex: p.z, transform: place(p), '--card-w': `${p.w}px` } as CSSProperties}
          >
            <ClaimCard view={view} size={p.focus ? 'focus' : 'small'} showBets={showBets} />
          </div>
        );
      })}
    </div>
  );
}

function layout(cards: CardView[], focusId: string | null, W: number, H: number, showBets: boolean): Pose[] {
  const n = cards.length;
  const floor = H - Math.round(H * 0.09); // the subtitle band crosses the bottom of this zone
  // The focus card's text ends above the subtitle band (only its bottom margin dips in); with 6+ cards
  // it narrows so the set-aside ones fit two columns a side instead of a tall overlapping stack.
  let focusW = Math.round(Math.min(((H - 2 * PAD - Math.round(H * 0.04)) * 2) / 3, W * 0.46));
  if (Math.ceil((n - 1) / 2) >= 3) focusW = Math.min(focusW, W - 2 * (2 * MIN_W + 2 * GAP + PAD));
  const fit = Math.floor(((W - 2 * PAD) / Math.max(n, 1)) * 1.08);
  const w = Math.max(MIN_W, Math.min(Math.round(focusW / 2), fit));
  const hasBets = showBets && cards.some((v) => v.bets.trueCredits > 0 || v.bets.falseCredits > 0);
  const betsH = (cardW: number) => (hasBets ? (cardW >= 136 ? 44 : 76) : 0); // two chip tallies wrap below 136px
  const fi = focusId === null ? -1 : cards.findLastIndex((v) => v.claim.id === focusId);
  const poses: Pose[] = [];

  if (fi < 0) {
    // A smile-shaped arc around the crystal ball: edges lifted, each card's top leaning toward the centre.
    const lift = n < 2 ? 0 : Math.min(34, 6 * n);
    const step = n < 2 ? 0 : Math.min(w + 14, (W - 2 * PAD - w) / (n - 1));
    const tilt = Math.min(9, 2.5 * (n - 1));
    const baseY = floor - betsH(w) - w * 0.75;
    cards.forEach((_, i) => {
      const t = n < 2 ? 0 : (2 * i) / (n - 1) - 1;
      poses.push({ x: W / 2 + (t * step * (n - 1)) / 2, y: baseY - lift * t * t, r: -t * tilt, w, z: i + 1, focus: false });
    });
    return poses;
  }

  poses[fi] = { x: W / 2, y: PAD + focusW * 0.75, r: 0, w: focusW, z: 50, focus: true };
  const rest = cards.map((_, i) => i).filter((i) => i !== fi);
  const leftN = Math.ceil(rest.length / 2);
  const regionW = (W - focusW) / 2 - GAP - PAD;
  const availH = floor - 2 * PAD - betsH(MIN_W);
  // The widest set-aside card that stacks the fuller side in one or two columns without overlap.
  const widthFor = (cols: number) => {
    const rows = Math.ceil(leftN / cols);
    return Math.min((regionW - (cols - 1) * GAP) / cols, (availH - (rows - 1) * GAP) / rows / 1.5);
  };
  const sw = Math.floor(Math.max(MIN_W, Math.min(w, Math.max(widthFor(1), widthFor(2)))));
  const sh = sw * 1.5;
  const aside = (idx: number[], dir: -1 | 1) => {
    const k = idx.length;
    const cols = k > 1 && k * sh + (k - 1) * GAP > availH && 2 * sw + GAP <= regionW ? 2 : 1;
    const rows = Math.ceil(k / cols);
    const stepY = rows < 2 ? 0 : Math.min(sh + GAP, (availH - sh) / (rows - 1));
    const top = PAD + availH - sh - stepY * (rows - 1); // bottom-aligned so they rest on the table
    const cx = dir < 0 ? PAD + regionW / 2 : W - PAD - regionW / 2;
    idx.forEach((ci, j) => {
      poses[ci] = {
        x: cx + (cols === 2 ? ((j % cols) - 0.5) * (sw + GAP) : 0),
        y: top + sh / 2 + Math.floor(j / cols) * stepY,
        r: dir * ASIDE_TILT[j % ASIDE_TILT.length],
        w: sw,
        z: 10 + j,
        focus: false,
      };
    });
  };
  aside(rest.slice(0, leftN), -1);
  aside(rest.slice(leftN), 1);
  return poses;
}

// A case may repeat a claim id, so keys carry a duplicate count.
function keysOf(cards: CardView[]): string[] {
  const seen = new Map<string, number>();
  return cards.map((v) => {
    const base = v.claim.id;
    const dup = seen.get(base) ?? 0;
    seen.set(base, dup + 1);
    return dup ? `${base}#${dup}` : base;
  });
}

const place = (p: Pose, scale = 1) =>
  `translate(${p.x - p.w / 2}px, ${p.y - p.w * 0.75}px) rotate(${p.r}deg) scale(${scale})`;

const moved = (a: Pose, b: Pose) =>
  Math.abs(a.x - b.x) > 0.5 || Math.abs(a.y - b.y) > 0.5 || Math.abs(a.r - b.r) > 0.1 || a.w !== b.w;

// Sampled quadratic Bézier from the ball to the slot; easing lives in u so keyframes stay evenly timed.
function deal(el: HTMLElement, p: Pose, ox: number, oy: number, delay: number, calm: boolean) {
  if (calm) {
    el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 320, delay, easing: 'ease-out', fill: 'backwards' });
    return;
  }
  const cx = (ox + p.x) / 2;
  const cy = Math.min(oy, p.y) - 120;
  const frames: Keyframe[] = [];
  for (let i = 0; i <= 12; i++) {
    const t = i / 12;
    const u = 1 - (1 - t) ** 3;
    const x = (1 - u) ** 2 * ox + 2 * (1 - u) * u * cx + u * u * p.x;
    const y = (1 - u) ** 2 * oy + 2 * (1 - u) * u * cy + u * u * p.y;
    frames.push({ opacity: Math.min(1, t * 4), transform: place({ ...p, x, y, r: -24 + (p.r + 24) * u }, 0.16 + 0.84 * u) });
  }
  el.animate(frames, { duration: 720, delay, fill: 'backwards' });
}

// FLIP: start the resized box at the old centre, scaled to the old width, then settle into the new pose.
function glide(el: HTMLElement, a: Pose, b: Pose, calm: boolean) {
  for (const running of el.getAnimations()) running.cancel();
  if (calm) return;
  el.animate([{ transform: place({ ...a, w: b.w }, a.w / b.w) }, { transform: place(b) }], {
    duration: 480,
    easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
  });
}
