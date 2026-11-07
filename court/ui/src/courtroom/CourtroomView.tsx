import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import type { Claim, LockStatus, Verdict } from '../contracts';
import { benchRun, ruledLocally } from '../bench/benchRun';
import { Explain } from '../case/Explain';
import { labelFrom, stepText } from '../case/steps';
import { DrHoot } from '../cast/DrHoot';
import { McClusky } from '../cast/McClusky';
import { deriveLock, fidelity } from '../engine/scoring';
import { reloadFrame, runSteps } from '../exhibits/runSteps';
import { fetchApps, type AppEntry } from '../feed/apps';
import { BUILDS } from '../feed/builds';
import { useCaseFeed } from '../feed/useCaseFeed';
import { loadFixtureBundle } from '../fixtures';
import { addRec, plainOutput, record } from './recorder';
import './courtroom.css';

const STEP_MS = 450;
const APP = new URLSearchParams(location.search).get('app') || 'todo';
const FIXTURE_APP = loadFixtureBundle().app;

type Word = 'LOCKED' | 'PERJURY' | 'UNSWORN' | 'FABRICATED' | 'MATCH' | 'MISMATCH' | 'NO RULING';
interface Ruling { word: Word; why: string; who: 'McCLUSKY' | 'DR. HOOT'; line: string; note?: string }
interface Outs { original: string; revival: string }

const TERM = { LOCKED: 'locked', PERJURY: 'struck', UNSWORN: 'unsworn', FABRICATED: 'fabricated', MATCH: undefined, MISMATCH: 'mismatch', 'NO RULING': undefined } as const;
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
const said = (s: string | null | undefined) => `“${plainOutput(s) || 'nothing'}”`;

// The court's recorded ruling for one claim, said in one sentence. The stage shows it; it never decides it.
function claimRuling(claim: Claim, status: LockStatus, v: Verdict | undefined): Ruling {
  if (status === 'LOCKED') return { word: 'LOCKED', why: `The original showed ${said(v?.original)}, as the medium swore.`, who: 'McCLUSKY', line: 'Sworn, tested, true.' };
  if (status === 'STRUCK') {
    return { word: 'PERJURY', why: `The medium swore ${said(claim.test.expect)}, but the original showed ${said(v?.original)}.`, who: 'DR. HOOT', line: 'Bond forfeit. Next witness.' };
  }
  if (status === 'FABRICATED') return { word: 'FABRICATED', why: 'The medium admitted it had no evidence for this claim.', who: 'DR. HOOT', line: 'Made up, and it said so.' };
  return {
    word: 'UNSWORN',
    why: v?.flaky ? 'The same steps gave two different answers, so the court will not rule.' : 'The court could not run this test on the original.',
    who: 'DR. HOOT',
    line: 'Two answers is no answer.',
  };
}

// Runs one test visibly in one stand; a missing element is a finding, said in words, never a crash.
async function live(frame: HTMLIFrameElement | null, steps: string[], observe: string): Promise<string> {
  if (!frame) return 'not on the stand';
  try {
    await reloadFrame(frame);
    return await runSteps(frame, steps, observe, { stepDelayMs: STEP_MS });
  } catch (e) {
    return plainOutput(message(e));
  }
}

function Stand({ side, src, scale, out, differs, frameRef, recording }: {
  side: 'original' | 'revival'; src: string; scale: number; out: string | null; differs: boolean;
  frameRef: (el: HTMLIFrameElement | null) => void; recording: boolean;
}) {
  const own = useRef<HTMLIFrameElement | null>(null);
  useEffect(() => {
    if (own.current && src) own.current.src = src;
  }, [src]);
  const setRef = useCallback((el: HTMLIFrameElement | null) => {
    own.current = el;
    frameRef(el);
  }, [frameRef]);
  return (
    <figure className={`cr-stand cr-stand--${side}${recording ? ' is-recording' : ''}`}>
      <figcaption className="cr-stand__name">
        <Explain term={side}>{side === 'original' ? 'The original' : 'The revival'}</Explain>
        {recording && <span className="cr-stand__rec">your turn: use it</span>}
      </figcaption>
      <div className="cr-stand__box" style={{ '--s': scale } as CSSProperties}>
        {/* No allow-modals: an alert() in a same-origin app would freeze the page. */}
        <iframe ref={setRef} title={`${side} app`} sandbox="allow-scripts allow-same-origin allow-forms" />
      </div>
      <div className="cr-stand__rail">
        <p className={`cr-out${out === null ? ' is-empty' : differs ? ' is-diff' : ''}`} aria-live="polite">
          {out === null ? 'Waiting for a question' : <><small>showed</small> {plainOutput(out) || '(nothing)'}</>}
        </p>
      </div>
    </figure>
  );
}

/** The default view: one courtroom, two witness stands, a bench that rules, a docket, and three choices. */
export function CourtroomView() {
  const feed = useCaseFeed();
  const b = feed.bundle;
  const [apps, setApps] = useState<AppEntry[]>([]);
  const [original, setOriginal] = useState<HTMLIFrameElement | null>(null);
  const [revival, setRevival] = useState<HTMLIFrameElement | null>(null);
  const [next, setNext] = useState(0);
  const [called, setCalled] = useState<string | null>(null);
  const [heard, setHeard] = useState<Record<string, Word>>({});
  const [busy, setBusy] = useState<'witness' | 'court' | null>(null);
  const [outs, setOuts] = useState<Outs | null>(null);
  const [ruling, setRuling] = useState<Ruling | null>(null);
  const [rec, setRec] = useState<string[] | null>(null);
  const docket = useRef<HTMLOListElement>(null);

  useEffect(() => {
    void fetchApps().then(setApps);
  }, []);

  // While recording, every real click, field and key in the original becomes a step; the frame reloads, so re-attach on load.
  const recording = rec !== null;
  useEffect(() => {
    if (!recording || !original) return;
    let stop = () => {};
    const attach = () => {
      stop();
      const doc = original.contentDocument;
      stop = doc ? record(doc, (e) => setRec((cur) => (cur ? addRec(cur, e) : cur))) : () => {};
    };
    attach();
    original.addEventListener('load', attach);
    return () => {
      original.removeEventListener('load', attach);
      stop();
    };
  }, [recording, original]);

  useEffect(() => {
    docket.current?.querySelector('[aria-current]')?.scrollIntoView({ block: 'nearest' });
  }, [called]);

  const app = b?.app ?? APP;
  const claims = b?.claims ?? [];
  const judged = claims.length > 0 && (b?.verdicts.length ?? 0) > 0;
  // The registered builds first: app1's fixture case is judged on its original, so P4's real revival takes the stand.
  const builds = BUILDS[app] ?? b?.builds ?? BUILDS.todo;
  const scale = BUILDS[app]?.scale ?? builds.scale;
  const observe = claims[0]?.test.observe ?? 'body';
  const verdictOf = (id: string) => b?.verdicts.find((v) => v.kind === 'claim' && v.ref === id);
  const statusOf = (c: Claim): LockStatus => b?.locks.find((l) => l.claim_id === c.id)?.status ?? deriveLock(c, verdictOf(c.id)) ?? 'UNSWORN';
  const label = (sel: string) => labelFrom(original?.contentDocument ?? null)(sel);

  async function callWitness() {
    const claim = claims[next % claims.length];
    if (!claim || busy) return;
    setRec(null);
    setBusy('witness');
    setCalled(claim.id);
    setRuling(null);
    setOuts(null);
    const [o, r] = await Promise.all([original, revival].map((f) => live(f, claim.test.steps, claim.test.observe)));
    const r0 = claimRuling(claim, statusOf(claim), verdictOf(claim.id));
    setOuts({ original: o, revival: r });
    setRuling({ ...r0, note: o === r ? 'The revival showed the same.' : 'The revival showed something different: a real finding about the rebuild.' });
    setHeard((h) => ({ ...h, [claim.id]: r0.word }));
    setNext((n) => n + 1);
    setBusy(null);
  }

  async function crossOrAsk() {
    if (busy) return;
    if (!recording) {
      setCalled(null);
      setRuling(null);
      setOuts(null);
      setRec([]);
      if (original) await reloadFrame(original).catch(() => {});
      return;
    }
    const steps = rec;
    setRec(null);
    setBusy('court');
    try {
      const v = await benchRun(original, revival, steps, observe, app, { original: builds.original, revival: builds.revival });
      // P1's court ruled in its own browser; replay the steps on the revival stand so the room sees what it did.
      if (!ruledLocally(v)) await live(revival, steps, observe);
      setOuts({ original: v.original, revival: v.revival });
      const here = ruledLocally(v) ? 'Ruled in this browser: P1’s court did not answer.' : 'Ruled by P1’s court in a real browser, twice per app.';
      setRuling(v.flaky
        ? { word: 'UNSWORN', why: 'An app gave two different answers to your steps, so the court will not rule.', who: 'DR. HOOT', line: 'Two answers is no answer.', note: here }
        : v.match
          ? { word: 'MATCH', why: `Both apps showed ${said(v.original)} in ${observe}.`, who: 'McCLUSKY', line: 'The revival held up.', note: here }
          : { word: 'MISMATCH', why: `The original showed ${said(v.original)}; the revival showed ${said(v.revival)}.`, who: 'DR. HOOT', line: 'There. A difference.', note: here });
    } catch (e) {
      setRuling({ word: 'NO RULING', why: message(e), who: 'DR. HOOT', line: 'The court cannot rule on that.' });
    } finally {
      setBusy(null);
    }
  }

  const locks = claims.map(statusOf);
  const count = (s: LockStatus) => locks.filter((x) => x === s).length;
  const fid = b?.caseFile?.fidelity ?? (b?.verdicts.length ? fidelity(b.verdicts) : null);
  const cred = b?.caseFile ? `${b.caseFile.credibility_start} → ${b.caseFile.credibility_end}` : '—';
  const claim = claims.find((c) => c.id === called) ?? null;
  const differs = !!outs && outs.original !== outs.revival;
  const word = busy === 'witness' ? 'ON THE STAND' : busy === 'court' ? 'THE COURT IS RULING' : recording ? 'YOUR WITNESS' : ruling?.word;

  return (
    <div className="cr">
      <header className="cr-top">
        <h1 className="cr-mark">MUSÉANCE</h1>
        <p className="cr-tag">A court for rebuilt apps. Two apps take the stand; the court checks they behave the same.</p>
        <nav className="cr-apps" aria-label="Choose the app">
          {apps.map((a) => {
            // A run judged by the court, else the repo's judged fixture case for that app.
            const source = a.hasRun || a.fidelity !== null ? 'runs' : a.id === FIXTURE_APP ? 'fixture' : null;
            return source ? (
              <a key={a.id} className="cr-app" href={`?source=${source}&app=${encodeURIComponent(a.id)}`} aria-current={a.id === app ? 'page' : undefined}>
                {a.id}{source === 'fixture' && <small>fixture case</small>}
              </a>
            ) : (
              <span key={a.id} className="cr-app is-off" title={`${a.name}: not judged yet`}>{a.id} <small>not judged yet</small></span>
            );
          })}
        </nav>
      </header>

      <main className="cr-room">
        <Stand side="original" src={builds.original} scale={scale} out={outs?.original ?? null} differs={false} frameRef={setOriginal} recording={recording} />

        <section className="cr-mid" aria-label="The bench">
          <div className={`cr-bench cr-bench--${(word ?? 'idle').toLowerCase().replace(/\s+/g, '-')}`}>
            <p className="cr-bench__word" role="status">
              {word ? <Explain term={ruling && !busy && !recording ? TERM[ruling.word] : undefined}>{word}</Explain> : 'IN SESSION'}
            </p>
            <p className="cr-bench__why">
              {busy === 'witness' && claim ? <>Claim {claim.id}: {claim.text}</>
                : busy === 'court' ? 'Both apps run your steps; the court compares what they show.'
                  : recording ? (rec.length ? `Recorded: ${rec.map((s) => stepText(s, label)).join(', then ')}.` : 'Type and click in the original on the left. Each action becomes a step.')
                    : ruling ? ruling.why
                      : !b ? (feed.error ?? 'Waiting for the case file.')
                        : judged ? 'Call a witness to test one claim on both apps, or cross-examine the original yourself.'
                          : `${app} is not judged yet. Run the court on it (python -m court.court --app ${app} … --out runs/${app}) and its claims appear here. You can still cross-examine it yourself.`}
            </p>
            {ruling?.note && !busy && !recording && <p className="cr-bench__note">{ruling.note}</p>}
          </div>

          {ruling && !busy && !recording && (
            <div className="cr-narrator">
              <div className="cr-narrator__who" aria-hidden="true">
                {ruling.who === 'McCLUSKY' ? <McClusky mood="relieved" stress={0} /> : <DrHoot mood="unimpressed" />}
              </div>
              <p><b>{ruling.who}</b> {ruling.line}</p>
            </div>
          )}

          <div className="cr-choices">
            <button type="button" className="cr-btn cr-btn--main" onClick={callWitness} disabled={!judged || !!busy}>
              Call the next witness
              <small>{judged ? `claim ${claims[next % claims.length]?.id} of ${claims.length}` : 'no sworn claims yet'}</small>
            </button>
            <button type="button" className="cr-btn" onClick={crossOrAsk} disabled={!!busy || (recording && !rec.length)}>
              {recording ? 'Ask the court' : 'Cross-examine it yourself'}
              <small>{recording ? `${rec.length} step${rec.length === 1 ? '' : 's'} recorded` : 'use the original, then ask'}</small>
            </button>
          </div>

          {judged && (
            <ol className="cr-docket" ref={docket} aria-label="The docket">
              {claims.map((c) => (
                <li key={c.id} aria-current={c.id === called || undefined} className={heard[c.id] ? `is-${heard[c.id].toLowerCase()}` : ''}>
                  <span className="cr-docket__id">{c.id}</span>
                  <span className="cr-docket__text" title={c.text}>{c.text}</span>
                  <span className="cr-docket__status">{heard[c.id] ?? 'not yet called'}</span>
                </li>
              ))}
            </ol>
          )}
        </section>

        <Stand side="revival" src={builds.revival} scale={scale} out={outs?.revival ?? null} differs={differs} frameRef={setRevival} recording={false} />
      </main>

      <footer className="cr-foot">
        {judged && (
          <dl className="cr-nums">
            <div><dt><Explain term="fidelity">Fidelity</Explain></dt><dd>{fid ?? '—'}</dd></div>
            <div><dt><Explain term="locked">Locked</Explain> / <Explain term="struck">struck</Explain></dt><dd>{count('LOCKED')} / {count('STRUCK')}</dd></div>
            <div><dt><Explain term="credibility">Credibility</Explain></dt><dd>{cred}</dd></div>
          </dl>
        )}
        <details className="cr-file">
          <summary>Case file</summary>
          <ul>
            <li>App: {b?.appLabel ?? app}{b ? ` · data from ${b.source}` : ''}</li>
            <li>Revival on the stand: {builds.revival}</li>
            {judged && <li>{claims.length} claims · {b?.attacks.length ?? 0} attacks · {count('UNSWORN')} unsworn · {count('FABRICATED')} fabricated · Brier {b?.caseFile?.brier ?? '—'}</li>}
            <li>Other views: <a href={`?view=case&source=runs&app=${app}`}>case view</a> · <a href={`?view=stage&source=runs&app=${app}`}>the old stage</a></li>
          </ul>
        </details>
      </footer>
    </div>
  );
}
