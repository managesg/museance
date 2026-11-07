import { useEffect, useId, useRef, useState, type CSSProperties, type FormEvent, type KeyboardEvent } from 'react';
import type { Verdict } from '../contracts';
import type { BenchSuggestion } from '../engine/types';
import { stepLabel } from '../cards/keys';
import { benchRun, FIXTURE_KEYS, parseShortcut, readKeys, ruledLocally, type BenchKey } from './benchRun';
import './bench.css';

interface BenchConsoleProps {
  open: boolean;
  app: string;
  observe: string;
  originalFrame: HTMLIFrameElement | null;
  revivalFrame: HTMLIFrameElement | null;
  originalSrc: string;
  revivalSrc: string;
  suggestions: BenchSuggestion[];
  onVerdict: (v: Verdict) => void;
  onClose: () => void;
}

// A mouse press on a key leaves the caret in the field, so Enter still runs.
const holdFocus = (e: { preventDefault(): void }) => e.preventDefault();

const LIP = 'M6 16C260 9 640 14 954 7C957 26 956 46 958 66C640 72 300 68 4 74C6 54 4 34 6 16Z';
const CAP_L = 'M6 16C22 15 40 14 58 13C61 33 61 53 58 71C40 72 22 73 4 74C6 54 4 34 6 16Z';
const CAP_R = 'M902 9C920 8 938 8 954 7C957 26 956 46 958 66C940 67 920 68 903 68C900 50 899 30 902 9Z';
const BELL = 'M24 17C14.6 17.2 11.2 25 11.3 33.4C11.4 39.6 8.3 43.6 5.2 46.6C4.6 49.8 43.6 50 43 46.6C39.8 43.5 36.8 39.4 36.9 33.2C37 25 33.6 17 24 17Z';

function DrawerArt() {
  return (
    <svg className="bench-body" viewBox="0 0 960 520" aria-hidden="true" focusable="false">
      <g stroke="var(--ink)" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 60C250 56 600 63 944 57C949 200 946 380 950 540L10 540C13 380 11 210 16 60Z" fill="var(--wood)" strokeWidth="6" />
        <path
          d="M24 120C26 220 21 330 25 470M936 110C933 230 938 350 934 480M44 508C220 502 400 511 560 504M600 512C700 506 820 514 918 507"
          fill="none"
          stroke="var(--wood-deep)"
          strokeWidth="3"
        />
        <path d={LIP} fill="var(--wood-light)" stroke="none" />
        <path d="M5 60C300 55 640 58 957 52L958 66C640 72 300 68 4 74Z" fill="var(--wood)" stroke="none" />
        <path d={LIP} fill="none" strokeWidth="6" />
        <path d={CAP_L} fill="var(--brass)" stroke="none" />
        <path d="M5 60C22 59 40 58 59 57L58 71C40 72 22 73 4 74Z" fill="var(--brass-deep)" stroke="none" />
        <path d={CAP_L} fill="none" strokeWidth="5" />
        <path d={CAP_R} fill="var(--brass)" stroke="none" />
        <path d="M902 54C920 53 938 53 957 52L958 66C940 67 920 68 903 68Z" fill="var(--brass-deep)" stroke="none" />
        <path d={CAP_R} fill="none" strokeWidth="5" />
        <g fill="var(--brass-deep)" strokeWidth="3">
          <circle cx="31" cy="29" r="4.5" />
          <circle cx="31.5" cy="45" r="4.5" />
          <circle cx="929" cy="23" r="4.5" />
          <circle cx="928.5" cy="39" r="4.5" />
        </g>
      </g>
    </svg>
  );
}

function BellArt() {
  return (
    <svg className="bench-bell-art" viewBox="0 0 48 56" aria-hidden="true" focusable="false">
      <g stroke="var(--ink)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="24" cy="51.5" r="3.4" fill="var(--brass-deep)" />
        <path d="M20.5 4.5C20.6 2.6 27.3 2.5 27.4 4.4L27.9 15.6C27.8 17.6 20.3 17.7 20.2 15.7Z" fill="var(--wood-light)" />
        <path d={BELL} fill="var(--brass)" stroke="none" />
        <path
          d="M30.5 19.5C34.6 23.4 36.4 28 36.4 33.6C36.3 39.7 39.4 43.7 43 46.6C41.5 48.3 37.5 48.9 33.8 49C33 45 31.6 40.5 31.9 33.6C32.1 28.2 31.9 23.2 30.5 19.5Z"
          fill="var(--brass-deep)"
          stroke="none"
        />
        <path d={BELL} fill="none" />
        <path d="M18.5 17.4C21.8 16.4 26.2 16.4 29.5 17.4" fill="none" />
      </g>
    </svg>
  );
}

// Puffs sit on the stamp's lower edge (percent of its box, whatever the word's width) and drift outward.
const DUST = [
  ['3%', '87%', 10, -16, 6],
  ['15%', '98%', 7.5, -9, 11],
  ['51%', '102%', 6.5, 0, 13],
  ['85%', '98%', 9, 9, 11],
  ['97%', '85%', 10, 16, 5],
] as const;

function DustArt() {
  return (
    <svg className="bench-dust" aria-hidden="true" focusable="false">
      {DUST.map(([x, y, r, dx, dy]) => (
        <circle key={x} cx={x} cy={y} r={r} style={{ '--dx': `${dx}px`, '--dy': `${dy}px` } as CSSProperties} />
      ))}
    </svg>
  );
}

const outClass = (s: string) => (s.length > 9 ? 'bench-out bench-out--long' : 'bench-out');

function Ruling({ v, labelOf }: { v: Verdict; labelOf: (step: string) => string }) {
  const stamp = v.flaky ? 'flaky' : v.match ? 'match' : 'diverges';
  const shrunk = v.shrunk_steps ?? [];
  return (
    <div className="bench-ruling">
      <dl className="bench-outs">
        <dt>Original</dt>
        <dd className={outClass(v.original)}>{v.original || '(blank)'}</dd>
        <dt>Revival</dt>
        <dd className={outClass(v.revival)}>{v.revival || '(blank)'}</dd>
      </dl>
      <div className="bench-verdict">
        <p className={`bench-stamp bench-stamp--${stamp}`}>
          {stamp}
          <DustArt />
        </p>
        <p className="bench-flag">{v.flaky ? 'A build changed its answer.' : 'Same answer on both runs.'}</p>
      </div>
      {shrunk.length > 0 && (
        <div className="bench-smallest">
          <span>Smallest input</span>
          <ol className="bench-caps" aria-label="Smallest input that still diverges">
            {shrunk.map((s, i) => (
              <li key={i} className="bench-cap">
                {labelOf(s)}
              </li>
            ))}
          </ol>
        </div>
      )}
      <p className="bench-by">Ruled by {ruledLocally(v) ? 'the local bench runner' : 'the court'}</p>
    </div>
  );
}

export function BenchConsole({ open, app, observe, originalFrame, revivalFrame, originalSrc, revivalSrc, suggestions, onVerdict, onClose }: BenchConsoleProps) {
  const id = useId();
  const field = useRef<HTMLInputElement>(null);
  const [keys, setKeys] = useState<BenchKey[]>(FIXTURE_KEYS);
  const [steps, setSteps] = useState<string[]>([]);
  const [draft, setDraft] = useState('');
  const [typo, setTypo] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ruling, setRuling] = useState<{ v: Verdict; n: number } | null>(null);

  useEffect(() => {
    if (open) field.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open || !originalFrame) return;
    // Mid-reload the frame has no buttons yet; keep the last keys instead of flashing the fallback.
    const read = () => {
      const found = readKeys(originalFrame);
      if (found.length) setKeys(found);
    };
    read();
    originalFrame.addEventListener('load', read);
    return () => originalFrame.removeEventListener('load', read);
  }, [open, originalFrame]);

  const labelOf = (step: string) => keys.find((k) => k.step === step)?.label ?? stepLabel(step);

  const compose = (next: string[]) => {
    if (running) return;
    setSteps(next);
    setDraft(next.every((s) => keys.some((k) => k.step === s)) ? next.map(labelOf).join('') : '');
    setTypo(null);
  };

  const type = (text: string) => {
    const parsed = parseShortcut(text, keys);
    setDraft(text);
    setSteps(parsed.steps);
    setTypo(parsed.bad === undefined ? null : `No "${parsed.bad}" key on the original. Use the keys shown.`);
  };

  const ready = steps.length > 0 && !typo && !running;

  const run = async () => {
    if (!ready) return;
    setRunning(true);
    setError(null);
    try {
      const v = await benchRun(originalFrame, revivalFrame, steps, observe, app, { original: originalSrc, revival: revivalSrc });
      setRuling((r) => ({ v, n: (r?.n ?? 0) + 1 }));
      onVerdict(v);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
      // runSteps focuses the exhibit buttons it clicks; take the keyboard back so Enter and Escape reach the bench.
      field.current?.focus();
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void run();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLElement>) => {
    e.stopPropagation(); // while the judge types, the stage's own shortcuts stay quiet
    if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    } else if (e.key === 'Enter' && !(e.target as Element).closest('button, input')) {
      e.preventDefault();
      void run();
    }
  };

  // aria-disabled, not disabled: a disabled control drops focus to <body>, where Escape and Enter no longer reach the bench.
  return (
    <section
      className={`bench${open ? ' bench--open' : ''}${running ? ' bench--running' : ''}`}
      role="dialog"
      aria-labelledby={`${id}-title`}
      tabIndex={-1}
      inert={!open}
      onKeyDown={onKeyDown}
    >
      <DrawerArt />
      <header className="bench-lip">
        <h2 id={`${id}-title`} className="bench-plate">
          The Judge's Cross
        </h2>
        <button type="button" className="bench-bell" onClick={onClose}>
          <BellArt />
          Ring for sentence
        </button>
      </header>
      <form className="bench-desk" onSubmit={onSubmit}>
        <div className="bench-compose">
          <div className="bench-keys" role="group" aria-label="Keys of the original">
            {keys.map((k) => (
              <button
                key={k.step}
                type="button"
                className={k.label.length > 3 ? 'bench-key bench-key--wide' : 'bench-key'}
                aria-disabled={running}
                onMouseDown={holdFocus}
                onClick={() => compose([...steps, k.step])}
              >
                {k.label}
              </button>
            ))}
          </div>
          <div className="bench-type">
            <label htmlFor={`${id}-field`}>Type</label>
            <input
              id={`${id}-field`}
              ref={field}
              className="bench-field"
              value={draft}
              placeholder={keys.some((k) => k.label === "7") ? "7/0=" : ""}
              readOnly={running}
              autoComplete="off"
              spellCheck={false}
              aria-invalid={typo !== null}
              aria-describedby={`${id}-typo`}
              onChange={(e) => type(e.target.value)}
            />
          </div>
          <p id={`${id}-typo`} className="bench-typo" aria-live="polite">
            {typo}
          </p>
          <div className="bench-tape">
            <ol className="bench-caps" aria-label="Input to run">
              {steps.length > 0 ? (
                steps.map((s, i) => (
                  <li key={i} className="bench-cap">
                    {labelOf(s)}
                  </li>
                ))
              ) : (
                <li className="bench-none">No keys yet</li>
              )}
            </ol>
            <button
              type="button"
              className="bench-tool"
              aria-disabled={!steps.length || running}
              onMouseDown={holdFocus}
              onClick={() => compose(steps.slice(0, -1))}
            >
              Undo
            </button>
            <button type="button" className="bench-tool" aria-disabled={!steps.length || running} onMouseDown={holdFocus} onClick={() => compose([])}>
              Clear
            </button>
          </div>
          {suggestions.length > 0 && (
            <div className="bench-suggest" role="group" aria-label="Suggested cross-examinations">
              <span>Or try</span>
              {suggestions.map((s) => (
                <button key={s.label} type="button" className="bench-slip" aria-disabled={running} onMouseDown={holdFocus} onClick={() => compose(s.steps)}>
                  {s.label}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="bench-rule">
          <button type="submit" className="bench-run" aria-disabled={!ready}>
            {running ? 'Running on both' : 'Run on both'}
          </button>
          <div className="bench-paper" aria-live="polite" aria-busy={running}>
            {running ? (
              <p className="bench-note bench-note--wait">Each build runs the input twice.</p>
            ) : error ? (
              <p className="bench-problem">{error}</p>
            ) : ruling ? (
              <Ruling key={ruling.n} v={ruling.v} labelOf={labelOf} />
            ) : (
              <p className="bench-note">No ruling yet. Press keys or type an input, then run it on both builds.</p>
            )}
          </div>
        </div>
      </form>
    </section>
  );
}
