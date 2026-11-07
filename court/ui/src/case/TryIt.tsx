import { useCallback, useEffect, useState } from 'react';
import type { Verdict } from '../contracts';
import { benchRun, ruledLocally } from '../bench/benchRun';
import { prettyOutput } from '../engine/format';
import { labelFrom, stepText } from './steps';
import './tryit.css';

interface Target { sel: string; action: 'type' | 'click'; name: string }
type Label = (sel: string) => string | null;

const TYPE_SEL = 'input[id]:not([type=submit]):not([type=button]):not([type=hidden]), textarea[id], select[id]';
const CLICK_SEL = 'button[id], a[id], [role=button][id], input[type=submit][id], input[type=button][id]';

const idSel = (el: Element) => `#${CSS.escape(el.id)}`;

/** The original's controls by #id. */
function scan(doc: Document): { targets: Target[]; label: Label } {
  const label = labelFrom(doc);
  const seen = new Set<string>();
  const targets: Target[] = [];
  const add = (el: Element, action: Target['action']) => {
    const sel = idSel(el);
    if (seen.has(sel)) return;
    seen.add(sel);
    targets.push({ sel, action, name: label(sel) ?? sel });
  };
  doc.querySelectorAll(TYPE_SEL).forEach((el) => add(el, 'type'));
  doc.querySelectorAll(CLICK_SEL).forEach((el) => add(el, 'click'));
  return { targets, label };
}

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function TryIt(p: {
  app: string;
  originalFrame: HTMLIFrameElement | null;
  revivalFrame: HTMLIFrameElement | null;
  originalSrc: string;
  revivalSrc: string;
  observeDefault: string;
  onVerdict: (v: Verdict) => void;
}) {
  const [found, setFound] = useState<ReturnType<typeof scan> | null>(null);
  const [steps, setSteps] = useState<string[]>([]);
  const [typing, setTyping] = useState<Target | null>(null);
  const [text, setText] = useState('');
  // One test, kept light: it watches the case's own first observe target.
  const observe = p.observeDefault;
  const [running, setRunning] = useState(false);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [error, setError] = useState('');

  const rescan = useCallback(() => {
    const doc = p.originalFrame?.contentDocument;
    setFound(doc && doc.URL !== 'about:blank' ? scan(doc) : null);
  }, [p.originalFrame]);

  useEffect(() => {
    rescan();
    const frame = p.originalFrame;
    frame?.addEventListener('load', rescan);
    return () => frame?.removeEventListener('load', rescan);
  }, [p.originalFrame, rescan]);

  const label = found?.label;
  const say = (s: string) => stepText(s, label);
  const push = (s: string) => {
    setSteps((cur) => [...cur, s]);
    setVerdict(null);
  };
  const pick = (t: Target) => {
    if (t.action === 'click') push(`click:${t.sel}`);
    else setTyping(t);
  };
  const addTyped = () => {
    if (!typing || !text) return;
    push(`type:${typing.sel}:${text}`);
    setText('');
    setTyping(null);
  };

  async function run() {
    setRunning(true);
    setError('');
    setVerdict(null);
    try {
      const v = await benchRun(p.originalFrame, p.revivalFrame, steps, observe, p.app, { original: p.originalSrc, revival: p.revivalSrc });
      setVerdict(v);
      p.onVerdict(v);
    } catch (e) {
      setError(message(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="tryit" aria-label="Run your own test">
      <h2 className="tryit-label">Run your own test</h2>

      {!found && (
        <p className="tryit-error" role="alert">
          The original app is not readable yet. Wait until it shows on the left. If it never shows, serve it under /exhibits/ from this
          page's origin.
        </p>
      )}
      {found && found.targets.length === 0 && (
        <p className="tryit-error" role="alert">
          Found no inputs or buttons with an id in the original. SÉANCE drives an app by #id selectors: give its controls ids, then reload.
        </p>
      )}

      <span className="tryit-sub">1. Pick what to do</span>
      <div className="tryit-targets">
        {found?.targets.map((t) => (
          <button type="button" key={t.sel} className="tryit-chip" aria-pressed={typing?.sel === t.sel} onClick={() => pick(t)}>
            {t.action === 'type' ? 'type into ' : 'click '}
            {t.name}
          </button>
        ))}
        <button type="button" className="tryit-chip" onClick={() => push('key:Enter')}>press Enter</button>
      </div>
      {typing && (
        <form className="tryit-row" onSubmit={(e) => { e.preventDefault(); addTyped(); }}>
          <label className="tryit-type">
            <span>Text for {typing.name}</span>
            <input autoFocus value={text} onChange={(e) => setText(e.target.value)} maxLength={150} />
          </label>
          <button type="submit" disabled={!text}>Add</button>
        </form>
      )}

      <ol className="tryit-steps" aria-label="Steps">
        {steps.map((s, i) => <li key={i}>{say(s)}</li>)}
        {steps.length === 0 && <li className="tryit-empty">No steps yet</li>}
      </ol>

      <button type="button" className="tryit-run" disabled={running || !steps.length || !observe} onClick={run}>
        {running ? 'Running on both…' : 'Run on both'}
      </button>

      {error && (
        <p className="tryit-error" role="alert">{error}</p>
      )}

      {verdict && (
        <div className={`tryit-ruling ${verdict.flaky ? 'is-flaky' : verdict.match ? 'is-match' : 'is-diff'}`} aria-live="polite">
          <p className="tryit-verdict">{verdict.flaky ? 'FLAKY' : verdict.match ? 'MATCH' : 'DIFFERENT'}</p>
          <dl>
            <dt>Original showed</dt>
            <dd>{prettyOutput(verdict.original) || '(nothing)'}</dd>
            <dt>Revival showed</dt>
            <dd>{prettyOutput(verdict.revival) || '(nothing)'}</dd>
          </dl>
          {verdict.flaky && <p>A build gave two different answers to the same steps, so the court does not rule on it.</p>}
          {!!verdict.shrunk_steps?.length && (
            <>
              <p className="tryit-sub">Smallest steps that still differ</p>
              <ol className="tryit-steps">{verdict.shrunk_steps.map((s, i) => <li key={i}>{say(s)}</li>)}</ol>
            </>
          )}
          {ruledLocally(verdict) && (
            <p className="tryit-note">Ruled in this browser: the court's bench endpoint did not answer. Start P1's court (COURT_URL) to rule with Playwright.</p>
          )}
        </div>
      )}
    </section>
  );
}
