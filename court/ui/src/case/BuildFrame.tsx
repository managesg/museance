import { useCallback, useEffect, useRef, type CSSProperties, type Ref } from 'react';
import { prettyOutput } from '../engine/format';
import { Explain } from './Explain';
import type { Term } from './glossary';

type Output = { text: string; tone: 'match' | 'diverge' | 'neutral' };

// Each build starts fresh, as the court's fresh browser does; the UI's own 'seance:' keys stay.
function clearStorage(frame: HTMLIFrameElement) {
  try {
    const win = frame.contentWindow;
    if (!win) return;
    for (const store of [win.localStorage, win.sessionStorage]) {
      for (const k of Object.keys(store)) if (!k.startsWith('seance:')) store.removeItem(k);
    }
  } catch {
    // Cross-origin or storage-blocked frames keep what they have.
  }
}

/** One build of the app in a plain frame: a same-origin iframe rendered at box/scale and scaled up, with its output below. */
export function BuildFrame({ label, term, src, scale, output = null, frameRef }: {
  label: string;
  term?: Term;
  src: string;
  scale: number;
  output?: Output | null;
  frameRef?: Ref<HTMLIFrameElement>;
}) {
  const own = useRef<HTMLIFrameElement | null>(null);
  const s = Number.isFinite(scale) && scale > 0 ? scale : 1;

  // src is set here, not as a prop, so storage is cleared before the page changes. Reloads go through reloadFrame, which clears too.
  useEffect(() => {
    const frame = own.current;
    if (!frame || !src) return;
    clearStorage(frame);
    frame.src = src;
  }, [src]);

  // Stable, so a parent's state setter is not called with null and back on every render.
  const setRef = useCallback((el: HTMLIFrameElement | null) => {
    own.current = el;
    if (typeof frameRef === 'function') frameRef(el);
    else if (frameRef) frameRef.current = el;
  }, [frameRef]);

  return (
    <figure className="build">
      <figcaption className="case-label"><Explain term={term}>{label}</Explain></figcaption>
      <div className="build__box" style={{ '--build-scale': s } as CSSProperties}>
        {/* No allow-modals: an alert() in a same-origin app would freeze the page. */}
        <iframe ref={setRef} className="build__app" title={label} sandbox="allow-scripts allow-same-origin allow-forms" />
      </div>
      <p className={`build__out build__out--${output?.tone ?? 'none'}`} aria-live="polite">
        {output ? prettyOutput(output.text) || '(empty)' : ' '}
      </p>
    </figure>
  );
}
