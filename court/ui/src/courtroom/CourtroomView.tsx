import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import type { CaseBundle, Claim, LockStatus, Verdict } from '../contracts';
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
import { plainClaim, pct } from './plain';
import { addRec, plainOutput, record } from './recorder';
import './courtroom.css';

const STEP_MS = 900;
const APP = new URLSearchParams(location.search).get('app') || 'todo';
const FIXTURE_APP = loadFixtureBundle().app;
// Names and the original's year for the room; the registry's ids mean nothing to a stranger.
const NAMES: Record<string, { name: string; year?: string }> = { todo: { name: 'Todo list', year: '2016' }, app1: { name: 'Calculator' }, '2048': { name: '2048', year: '2014' } };
// Larger than the builds table's scale so app text reads on a projector; each stand still shrinks to fit its card.
const COURT_SCALE: Record<string, number> = { todo: 1.3 };

// The exhibits share this page's origin, so an app's saved data (todo keeps its list in localStorage) would
// survive between visits and make the two stands disagree before any test. Every visit starts clean.
function clearAppStorage() {
  try {
    for (const k of Object.keys(localStorage)) if (!k.startsWith('seance:')) localStorage.removeItem(k);
  } catch {
    // Storage blocked: the stands reload per test anyway.
  }
}
clearAppStorage();

type Word = 'SAME' | 'DIFFERENT' | 'UNSURE' | 'NO RULING';
interface Result { word: Word; why: string; ai: string | null; who: 'McCLUSKY' | 'DR. HOOT'; line: string; note?: string }
interface Outs { original: string; revival: string }
interface Match { id: string; kind?: string; tier?: string; text: string; score: number }

const TONE: Record<Word, 'same' | 'diff' | 'unsure'> = { SAME: 'same', DIFFERENT: 'diff', UNSURE: 'unsure', 'NO RULING': 'unsure' };
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
// A missing element is what the app showed: nothing there. Say it without the selector.
function shown(s: string | null | undefined): string {
  const out = plainOutput(s);
  const none = /^(?:nothing to read: )?it has no (.+)$/.exec(out);
  return none ? `nothing in ${plainClaim(none[1])}` : out;
}
const said = (s: string | null | undefined) => {
  const out = shown(s);
  return out && !out.startsWith('nothing in ') ? `“${out}”` : out || 'nothing';
};
const diffs = (vs: Verdict[]) => vs.filter((v) => !v.match && !v.flaky).length;

// What the AI claimed about the original, and whether the court found it true there. The stage says it; it never decides it.
function aiLine(claim: Claim, status: LockStatus, v: Verdict | undefined): string {
  const sure = pct(claim.confidence);
  if (status === 'LOCKED') return `The AI's claim about the original was true${sure ? ` (scored ${sure} by SubQ)` : ''}, so it is locked into the record.`;
  if (status === 'STRUCK') return `The AI claimed ${claim.test.expect ? said(claim.test.expect) : 'an empty entry'}, but the original showed ${said(v?.original)}. Perjury: it loses its ${claim.bond}-credit bond.`;
  if (status === 'FABRICATED') return 'The AI admitted it had no evidence for this claim.';
  return 'The court could not get a stable answer on the original, so the claim is unsworn.';
}

// The headline answers one question: did the revival do what the original did? The court's recorded verdict decides it.
function witnessResult(claim: Claim, status: LockStatus, v: Verdict | undefined, live: Outs): Result {
  const res = recordedResult(claim, status, v, live);
  const replaySame = live.original === live.revival;
  return v && !v.flaky && replaySame !== v.match
    ? { ...res, note: `The replay on this screen came out ${replaySame ? 'the same' : 'different'}; the court's recorded run says ${v.match ? 'same' : 'different'}.` }
    : res;
}

function recordedResult(claim: Claim, status: LockStatus, v: Verdict | undefined, live: Outs): Result {
  const ai = aiLine(claim, status, v);
  if (v?.flaky) return { word: 'UNSURE', why: 'The court ran this twice and got two different answers, so it will not rule.', ai, who: 'DR. HOOT', line: 'Two answers is no answer.' };
  const same = v ? v.match : live.original === live.revival;
  const o = v?.original ?? live.original;
  const r = v?.revival ?? live.revival;
  if (same) {
    return status === 'STRUCK'
      ? { word: 'SAME', why: `Both apps showed ${said(o)}.`, ai, who: 'DR. HOOT', line: 'The rebuild is faithful. The AI\'s claim was not.' }
      : { word: 'SAME', why: `Both apps showed ${said(o)}.`, ai, who: 'McCLUSKY', line: 'The revival held up.' };
  }
  return { word: 'DIFFERENT', why: `The original showed ${said(o)}; the revival showed ${said(r)}.`, ai, who: 'DR. HOOT', line: 'There. A real difference in the rebuild.' };
}

// Runs one test visibly in one stand; a missing element is a finding said in words, never a crash.
async function live(frame: HTMLIFrameElement | null, steps: string[], observe: string, onStep?: (i: number) => void): Promise<string> {
  if (!frame) return 'not on the stand';
  try {
    await reloadFrame(frame);
    return await runSteps(frame, steps, observe, { stepDelayMs: STEP_MS, onStep });
  } catch (e) {
    return plainOutput(message(e));
  }
}

// Outlines what the court reads in the app, so the room sees where to look. Literal colours: our CSS variables
// do not reach into the app's own document (same reason as runSteps' replay style).
function markObserved(frame: HTMLIFrameElement | null, sel: string, tone: 'same' | 'diff' | 'unsure') {
  try {
    const doc = frame?.contentDocument;
    const el = doc?.querySelector(sel);
    if (!doc || !el) return;
    const style = doc.createElement('style');
    const color = tone === 'same' ? '#2F8F6B' : tone === 'diff' ? '#B1454A' : '#C28A2B';
    style.textContent = `[data-mu-observed]{outline:4px solid ${color}!important;outline-offset:4px!important;border-radius:4px}`;
    (doc.head ?? doc.documentElement).append(style);
    el.setAttribute('data-mu-observed', '');
  } catch {
    // Cross-origin or a bad selector: nothing to outline.
  }
}

function Stand({ side, label, src, base, out, tone, frameRef, recording }: {
  side: 'original' | 'revival'; label: string; src: string; base: number; out: string | null; tone: 'same' | 'diff' | 'unsure' | null;
  frameRef: (el: HTMLIFrameElement | null) => void; recording: boolean;
}) {
  const own = useRef<HTMLIFrameElement | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(base);
  useEffect(() => {
    setScale(base);
    if (own.current && src) own.current.src = src;
  }, [src, base]);
  const setRef = useCallback((el: HTMLIFrameElement | null) => {
    own.current = el;
    frameRef(el);
  }, [frameRef]);
  // Each stand fits its own app: shrink below the base scale when the page is bigger than the card, never crop it.
  const fit = () => {
    const doc = own.current?.contentDocument;
    const el = box.current;
    if (!doc || !el) return;
    const cw = doc.documentElement.scrollWidth;
    const ch = doc.documentElement.scrollHeight;
    if (!cw || !ch) return;
    setScale((s) => Math.max(0.5, Math.min(s, (el.clientWidth / cw) * s, (el.clientHeight / ch) * s)));
  };
  return (
    <figure className={`cr-card cr-card--${side}${recording ? ' is-recording' : ''}`}>
      <figcaption className="cr-card__head">
        <span className="cr-card__name"><Explain term={side}>{label}</Explain></span>
        {recording && <span className="cr-card__turn">Your turn: use this app</span>}
      </figcaption>
      <div className="cr-card__app" ref={box} style={{ '--s': scale } as CSSProperties}>
        {/* No allow-modals: an alert() in a same-origin app would freeze the page. */}
        <iframe ref={setRef} title={`${label} app`} sandbox="allow-scripts allow-same-origin allow-forms" onLoad={fit} />
      </div>
      <p className={`cr-card__out${tone ? ` is-${tone}` : ''}`}>
        <span className="cr-card__out-label">Showed</span>
        <span className="cr-card__out-value">{out === null ? '—' : shown(out) || 'nothing'}</span>
      </p>
    </figure>
  );
}

// The AI's work on this case, step by step, from the case data. The court is the one step with no AI in it.
function Story({ b }: { b: CaseBundle }) {
  if (b.source === 'fixture') {
    return <p className="cr-story__note">Practice case: hand-written fixture data. No AI wrote these claims.</p>;
  }
  const lines = b.sheet?.lines ?? [];
  const seen = lines.filter((l) => l.label === 'SEEN').length;
  const steps = [
    { name: 'Evidence', value: `${b.evidence.length} items`, who: 'dug from the web' },
    { name: 'Behavior sheet', value: `${lines.length} lines`, who: `SubQ reader · ${seen} seen` },
    { name: 'Claims', value: `${b.claims.length} sworn`, who: 'ASI-1 medium · SubQ scores' },
    { name: 'Revival', value: 'rebuilt', who: 'Codex, from the sheet only' },
    { name: 'Attacks', value: `${b.attacks.length} sealed`, who: 'Skeptic, before the claims' },
    { name: 'Court', value: `${b.verdicts.length} checks`, who: 'no AI · real browser' },
    { name: 'Repair', value: b.after ? 'v2' : '—', who: 'Codex; Muse matched it' },
  ];
  return (
    <ol className="cr-story" aria-label="How the AI built this case">
      {steps.map((s) => (
        <li key={s.name} className={s.name === 'Court' ? 'is-court' : undefined}>
          <span className="cr-story__name">{s.name}</span>
          <span className="cr-story__value">{s.value}</span>
          <span className="cr-story__who">{s.who}</span>
        </li>
      ))}
    </ol>
  );
}

/** The default view: the original and its AI rebuild side by side, one test at a time, and the court's answer. */
export function CourtroomView() {
  const feed = useCaseFeed();
  const b = feed.bundle;
  const [apps, setApps] = useState<AppEntry[]>([]);
  const [original, setOriginal] = useState<HTMLIFrameElement | null>(null);
  const [revival, setRevival] = useState<HTMLIFrameElement | null>(null);
  const [next, setNext] = useState(0);
  const [called, setCalled] = useState<string | null>(null);
  const [stepAt, setStepAt] = useState<number | null>(null);
  const [heard, setHeard] = useState<Record<string, Word>>({});
  const [busy, setBusy] = useState<'witness' | 'court' | null>(null);
  const [outs, setOuts] = useState<Outs | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [rec, setRec] = useState<string[] | null>(null);
  const [matches, setMatches] = useState<{ model: string; byClaim: Record<string, Match[]> } | null>(null);
  const docket = useRef<HTMLOListElement>(null);
  const running = useRef(false);
  // A replay focuses fields inside the app's frame; hand focus back so N, T and Enter keep working.
  const nextBtn = useRef<HTMLButtonElement>(null);

  const app = b?.app ?? APP;
  useEffect(() => {
    void fetchApps().then(setApps);
  }, []);
  // MongoDB AI (embeddings) ranks the evidence pile for each claim; the panel stays hidden if the feed has no key.
  useEffect(() => {
    let alive = true;
    fetch(`/api/match?app=${encodeURIComponent(app)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive && j?.matches) setMatches({ model: String(j.model ?? ''), byClaim: j.matches }); })
      .catch(() => {});
    return () => { alive = false; };
  }, [app]);

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

  const claims = useMemo(() => b?.claims ?? [], [b]);
  const verdictOf = useCallback((id: string) => b?.verdicts.find((v) => v.kind === 'claim' && v.ref === id), [b]);
  const statusOf = useCallback(
    (c: Claim): LockStatus => b?.locks.find((l) => l.claim_id === c.id)?.status ?? deriveLock(c, verdictOf(c.id)) ?? 'UNSWORN',
    [b, verdictOf],
  );
  // Demo order: one faithful test, one real difference, one false claim first, so a short run shows every outcome.
  const order = useMemo(() => {
    const isDiff = (c: Claim) => {
      const v = verdictOf(c.id);
      return !!v && !v.match && !v.flaky;
    };
    const lead = [
      claims.find((c) => statusOf(c) === 'LOCKED' && !isDiff(c)),
      claims.find(isDiff),
      claims.find((c) => statusOf(c) === 'STRUCK'),
    ].filter((c, i, all): c is Claim => !!c && all.indexOf(c) === i);
    return [...lead, ...claims.filter((c) => !lead.includes(c))];
  }, [claims, statusOf, verdictOf]);

  const judged = claims.length > 0 && (b?.verdicts.length ?? 0) > 0;
  // The stands show exactly the builds the court judged: a practice case was judged against the practice revival,
  // so showing another rebuild there would contradict the recorded verdicts.
  const builds = b?.source === 'fixture' ? b.builds : BUILDS[app] ?? b?.builds ?? BUILDS.todo;
  const base = COURT_SCALE[app] ?? builds.scale;
  const observe = claims[0]?.test.observe ?? 'body';
  const label = (sel: string) => labelFrom(original?.contentDocument ?? null)(sel);
  const names = NAMES[app] ?? { name: b?.appLabel ?? app };

  const reset = async () => {
    setOuts(null);
    setResult(null);
    setStepAt(null);
    await Promise.all([original, revival].map((f) => (f ? reloadFrame(f).catch(() => {}) : null)));
  };

  async function callWitness() {
    const claim = order[next % order.length];
    if (!claim || running.current) return;
    running.current = true;
    setRec(null);
    setBusy('witness');
    setCalled(claim.id);
    setResult(null);
    setOuts(null);
    setStepAt(0);
    const [o, r] = await Promise.all([
      live(original, claim.test.steps, claim.test.observe, (i) => setStepAt(i)),
      live(revival, claim.test.steps, claim.test.observe),
    ]);
    const res = witnessResult(claim, statusOf(claim), verdictOf(claim.id), { original: o, revival: r });
    // Practice cases were hand-written: say "the claim", never "the AI".
    if (b?.source === 'fixture' && res.ai) res.ai = res.ai.replace("The AI's claim", 'The claim').replace('The AI claimed', 'The claim said').replace('The AI admitted', 'The claim admitted');
    setOuts({ original: o, revival: r });
    setResult(res);
    setStepAt(null);
    markObserved(original, claim.test.observe, TONE[res.word]);
    markObserved(revival, claim.test.observe, TONE[res.word]);
    setHeard((h) => ({ ...h, [claim.id]: res.word }));
    setNext((n) => n + 1);
    setBusy(null);
    running.current = false;
    window.setTimeout(() => nextBtn.current?.focus({ preventScroll: true }), 60);
  }

  async function startOwnTest() {
    if (running.current) return;
    setCalled(null);
    await reset();
    setRec([]);
  }

  async function cancelOwnTest() {
    setRec(null);
    await reset();
  }

  async function askCourt() {
    if (running.current || !rec?.length) return;
    running.current = true;
    const steps = rec;
    setRec(null);
    setBusy('court');
    try {
      const v = await benchRun(original, revival, steps, observe, app, { original: builds.original, revival: builds.revival });
      // P1's court ruled in its own browser; replay the steps on the revival stand so the room sees what it did.
      if (!ruledLocally(v)) await live(revival, steps, observe);
      setOuts({ original: v.original, revival: v.revival });
      const note = ruledLocally(v) ? 'Checked in this browser: P1’s court did not answer.' : 'Checked by P1’s court in a real browser, twice per app.';
      const res: Result = v.flaky
        ? { word: 'UNSURE', why: 'An app gave two different answers to your steps, so the court will not rule.', ai: null, who: 'DR. HOOT', line: 'Two answers is no answer.', note }
        : v.match
          ? { word: 'SAME', why: `Both apps showed ${said(v.original)}.`, ai: null, who: 'McCLUSKY', line: 'The revival held up.', note }
          : { word: 'DIFFERENT', why: `The original showed ${said(v.original)}; the revival showed ${said(v.revival)}.`, ai: null, who: 'DR. HOOT', line: 'There. A real difference in the rebuild.', note };
      setResult(res);
      markObserved(original, observe, TONE[res.word]);
      markObserved(revival, observe, TONE[res.word]);
    } catch (e) {
      setResult({ word: 'NO RULING', why: `The court could not run these steps: ${plainOutput(message(e))}.`, ai: null, who: 'DR. HOOT', line: 'Try a shorter test.' });
    } finally {
      setBusy(null);
      running.current = false;
      window.setTimeout(() => nextBtn.current?.focus({ preventScroll: true }), 60);
    }
  }

  // Presenter keys: N runs the next test, T starts (or asks about) your own test, Escape cancels it.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || (e.target instanceof HTMLElement && e.target.closest('input, textarea, select, [contenteditable]'))) return;
      const k = e.key.toLowerCase();
      if (k === 'n') void callWitness();
      else if (k === 't') void (recording ? askCourt() : startOwnTest());
      else if (k === 'escape' && recording) void cancelOwnTest();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const claim = claims.find((c) => c.id === called) ?? null;
  const tone = result ? TONE[result.word] : null;
  // With a repaired revival the case file is the after result; the first rebuild's fidelity is its own verdicts.
  const fBefore = b ? (b.after ? fidelity(b.verdicts) : (b.caseFile?.fidelity ?? fidelity(b.verdicts))) : null;
  const fAfter = b?.after ? (b.after.caseFile?.fidelity ?? fidelity(b.after.verdicts)) : null;
  const dBefore = b ? diffs(b.verdicts) : null;
  const dAfter = b?.after ? diffs(b.after.verdicts) : null;
  const fs = b?.caseFile?.counts?.false_strikes;
  const fsOf = b?.caseFile?.counts?.false_strikes_of;
  const evidence = claim ? matches?.byClaim[claim.id] ?? [] : [];

  const heading = busy === 'witness' && claim ? plainClaim(claim.text)
    : busy === 'court' ? 'The court is checking your test'
      : recording ? 'Your test'
        : claim ? plainClaim(claim.text)
          : result ? 'Your test'
            : judged ? 'Does the rebuild behave like the original?' : `${names.name} is not judged yet`;
  const sub = busy === 'court' ? 'Both apps run your steps; the court compares what they show.'
    : recording ? (rec.length ? `Recorded: ${rec.map((s) => stepText(s, label)).join(', then ')}.` : 'Type and click in the original on the left. Each action becomes a step.')
      : !b ? (feed.error ?? 'Loading the case file.')
        : !judged ? 'The court has not run on this app yet. You can still test it yourself.'
          : !claim && !result ? 'Run a test: both apps do the same steps side by side, and the court says SAME or DIFFERENT.' : null;

  return (
    <div className="cr">
      <header className="cr-top">
        <h1 className="cr-mark">MUSÉANCE</h1>
        <p className="cr-tag">A dead app, rebuilt by AI, on trial. The court checks the rebuild behaves exactly like the original.</p>
        <nav className="cr-apps" aria-label="Choose the app">
          {apps.map((a) => {
            // A run judged by the court, else the repo's judged fixture case for that app.
            const source = a.hasRun || a.fidelity !== null ? 'runs' : a.id === FIXTURE_APP ? 'fixture' : null;
            const n = NAMES[a.id]?.name ?? a.name;
            return source ? (
              <a key={a.id} className="cr-app" href={`?source=${source}&app=${encodeURIComponent(a.id)}`} aria-current={a.id === app ? 'page' : undefined}>
                {n}
              </a>
            ) : (
              <span key={a.id} className="cr-app is-off" title={`${n}: not judged yet`}>{n}</span>
            );
          })}
        </nav>
      </header>

      <section className="cr-band" aria-label="The case so far">
        {b && <Story b={b} />}
        {judged && (
          <dl className="cr-nums">
            <div>
              <dt><Explain term="fidelity">Fidelity</Explain></dt>
              <dd>{fBefore ?? '—'}{fAfter !== null && <> <span className="cr-nums__to">→</span> {fAfter}</>}</dd>
            </div>
            <div>
              <dt><Explain term="mismatch">Differences</Explain></dt>
              <dd>{dBefore ?? '—'}{dAfter !== null && <> <span className="cr-nums__to">→</span> {dAfter}</>}</dd>
            </div>
            <div>
              <dt><Explain term="falseStrikes">False strikes</Explain></dt>
              <dd>{fs ?? '—'}{typeof fsOf === 'number' && <span className="cr-nums__of"> of {fsOf}</span>}</dd>
            </div>
            <p className="cr-nums__src">
              {fAfter !== null ? 'First rebuild → after repair. ' : ''}Measured by the court: runs/{app}/verdicts.json{b?.after ? `, runs/${app}/after/` : ''}
            </p>
          </dl>
        )}
      </section>

      <main className="cr-room">
        <Stand side="original" label={`Original${names.year ? ` (${names.year})` : ''}`} src={builds.original} base={base}
          out={outs?.original ?? null} tone={null} frameRef={setOriginal} recording={recording} />
        <Stand side="revival" label="Revival (rebuilt today)" src={builds.revival} base={base}
          out={outs?.revival ?? null} tone={tone} frameRef={setRevival} recording={false} />

        <aside className="cr-rail" aria-label="The court">
          <section className={`cr-verdict${tone ? ` is-${tone}` : ''}`}>
            <h2 className="cr-verdict__claim">
              {claim && <span className="cr-verdict__id">{claim.id}</span>}
              {heading}
            </h2>
            {sub && <p className="cr-verdict__sub">{sub}</p>}
            {busy === 'witness' && claim && (
              <ol className="cr-steps">
                {claim.test.steps.map((s, i) => (
                  <li key={i} aria-current={i === stepAt || undefined}>{stepText(s, label)}</li>
                ))}
              </ol>
            )}
            {result && !busy && !recording && (
              <>
                <p className="cr-verdict__word">{result.word === 'DIFFERENT' ? <Explain term="mismatch">DIFFERENT</Explain> : result.word}</p>
                <p className="cr-verdict__why">{result.why}</p>
                {result.ai && <p className="cr-verdict__ai">{result.ai}</p>}
                {evidence.length > 0 && (
                  <p className="cr-verdict__evidence">
                    <span>Closest evidence, found by MongoDB AI{matches?.model ? ` (${matches.model})` : ''}:</span>{' '}
                    <span className="cr-mono">{evidence[0].id}</span> {evidence[0].text}
                  </p>
                )}
                {result.note && <p className="cr-verdict__note">{result.note}</p>}
              </>
            )}
            <div className="cr-narrator" aria-hidden={!result || !!busy || recording}>
              {result && !busy && !recording && (
                <>
                  <span className="cr-narrator__who">{result.who === 'McCLUSKY' ? <McClusky mood="relieved" stress={0} /> : <DrHoot mood="unimpressed" />}</span>
                  <p><b>{result.who}</b> {result.line}</p>
                </>
              )}
            </div>
            <p className="cr-sr" aria-live="polite">{result && !busy ? `${result.word}. ${result.why}` : ''}</p>
          </section>

          <div className="cr-actions">
            {recording ? (
              <>
                <button type="button" className="cr-btn cr-btn--main" onClick={() => void askCourt()} disabled={!rec.length}>Ask the court</button>
                <button type="button" className="cr-btn" onClick={() => void cancelOwnTest()}>Cancel</button>
              </>
            ) : (
              <>
                <button type="button" ref={nextBtn} className="cr-btn cr-btn--main" onClick={() => void callWitness()} disabled={!judged || !!busy}>Run the next test</button>
                <button type="button" className="cr-btn" onClick={() => void startOwnTest()} disabled={!!busy}>Test it yourself</button>
              </>
            )}
          </div>

          {judged && (
            <ol className="cr-docket" ref={docket} aria-label="Tests, in the order they run">
              {order.map((c) => {
                const w = heard[c.id];
                const struck = !!w && statusOf(c) === 'STRUCK';
                return (
                  <li key={c.id} aria-current={c.id === called || undefined}>
                    <span className="cr-mono cr-docket__id">{c.id}</span>
                    <span className="cr-docket__text" title={plainClaim(c.text)}>{plainClaim(c.text)}</span>
                    <span className="cr-docket__pills">
                      {struck && <span className="cr-pill is-diff"><Explain term="struck">Perjury</Explain></span>}
                      <span className={`cr-pill${w ? ` is-${TONE[w]}` : ''}`}>{w ? (w === 'SAME' ? 'Same' : w === 'DIFFERENT' ? 'Different' : 'Unsure') : 'Not run'}</span>
                    </span>
                  </li>
                );
              })}
            </ol>
          )}
          <p className="cr-keys">Keys: N next test · T test it yourself · Esc cancel</p>
        </aside>
      </main>
    </div>
  );
}
