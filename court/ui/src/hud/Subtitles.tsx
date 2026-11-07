import { useState } from 'react';
import './hud.css';

type Line = { who: string; text: string };
type Shown = { line: Line; n: number };

const same = (a: Line | null, b: Line | null) => a === b || (!!a && !!b && a.who === b.who && a.text === b.text);

function Plate({ line, out, onDone }: { line: Line; out?: boolean; onDone?: () => void }) {
  return (
    <p className={`hud-sub ${out ? 'is-out' : 'is-in'}`} aria-hidden={out || undefined} onAnimationEnd={onDone}>
      <span className="hud-sub__who">{line.who}</span>
      <span className="hud-sr">: </span>
      {line.text}
    </p>
  );
}

/** Film subtitles on a dark plate, anchored to the bottom of their zone (1000x64 design px) and growing upward. */
export function Subtitles({ line }: { line: { who: string; text: string } | null }) {
  const [now, setNow] = useState<{ line: Line | null; n: number }>({ line, n: 0 });
  const [gone, setGone] = useState<Shown | null>(null);
  // Compare by content: the director rebuilds the object every beat, and only a new line should crossfade.
  if (!same(line, now.line)) {
    setGone(now.line ? { line: now.line, n: now.n } : null);
    setNow({ line, n: now.n + 1 });
  }
  return (
    <div className="hud-subs" aria-live="polite">
      {gone && <Plate key={gone.n} line={gone.line} out onDone={() => setGone(null)} />}
      {now.line && <Plate key={now.n} line={now.line} />}
    </div>
  );
}
