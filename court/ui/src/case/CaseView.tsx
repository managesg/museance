import { useEffect, useState } from 'react';
import type { Verdict } from '../contracts';
import { prettyOutput } from '../engine/format';
import { useDirector } from '../engine/useDirector';
import { reloadFrame, runSteps } from '../exhibits/runSteps';
import { BUILDS } from '../feed/builds';
import { useCaseFeed } from '../feed/useCaseFeed';
import { NumbersBar } from '../hud/NumbersBar';
import { useKeyboard } from '../stage/useKeyboard';
import { AppPicker } from './AppPicker';
import { BuildFrame } from './BuildFrame';
import { ClaimDetail } from './ClaimDetail';
import { ClaimList } from './ClaimList';
import { Explain } from './Explain';
import { Narrators } from './Narrators';
import { Pipeline } from './Pipeline';
import { labelFrom, stepText } from './steps';
import { TryIt } from './TryIt';
import './case.css';

const STEP_MS = 250;
const APP = new URLSearchParams(location.search).get('app') || 'app1';
const noop = () => {};

type Tag = { text: string; tone: 'match' | 'diverge' | 'neutral' };

// The original is judged against the claim, the revival against the original.
function tagsOf(v: Verdict): { original: Tag; revival: Tag } {
  return {
    original: { text: v.original, tone: v.flaky || v.claim_true == null ? 'neutral' : v.claim_true ? 'match' : 'diverge' },
    revival: { text: v.revival, tone: v.flaky ? 'neutral' : v.match ? 'match' : 'diverge' },
  };
}

const buildName = (src: string) => /index\.(v\d+)\.html$/.exec(src)?.[1] ?? null;

// A replay leaves focus inside a frame; useKeyboard cannot hear it there while the frame reloads.
function releaseKeyboard(frames: HTMLIFrameElement[]) {
  const active = document.activeElement;
  if (active instanceof HTMLIFrameElement && frames.includes(active)) active.blur();
}

/** The app-agnostic case screen: what SÉANCE did to the app, both builds side by side, and the claims with their rulings. */
export function CaseView() {
  const feed = useCaseFeed();
  // Starts paused on the first beat; the one Play button (or Space) runs the show.
  const director = useDirector(feed.bundle, { autoplay: false });
  const { state } = director;
  const [tryOpen, setTryOpen] = useState(false);
  // State, not refs: the replay effect and Try it must see the iframes once they mount.
  const [original, setOriginal] = useState<HTMLIFrameElement | null>(null);
  const [revival, setRevival] = useState<HTMLIFrameElement | null>(null);

  const focus = state?.cards.findLast((k) => k.claim.id === state.focusId) ?? null;
  const crossing = state?.phase === 'cross' && state.exhibits.revival === 'cross' ? (focus?.claim ?? null) : null;

  useEffect(() => {
    if (!crossing || !original || !revival) return;
    let live = true;
    // runSteps calls onStep before every press, so throwing there stops a replay whose beat has moved on.
    const halt = () => {
      if (!live) throw new Error('the beat moved on');
    };
    const replay = async (frame: HTMLIFrameElement) => {
      await reloadFrame(frame);
      halt();
      await runSteps(frame, crossing.test.steps, crossing.test.observe, { stepDelayMs: STEP_MS, onStep: halt });
    };
    // The replay is for the room; the ruling comes from the court's verdict whatever the frames show.
    const replays = [original, revival].map((frame) =>
      replay(frame).catch((e: unknown) => {
        if (live) console.warn(`replay of ${crossing.id} failed:`, e);
      }),
    );
    void Promise.all(replays).then(() => live && releaseKeyboard([original, revival]));
    return () => {
      live = false;
      releaseKeyboard([original, revival]);
    };
  }, [crossing, original, revival]);

  const toggleTry = () => setTryOpen((o) => !o);
  useKeyboard(
    {
      toggle: director.toggle,
      next: director.next,
      prev: director.prev,
      jump: director.jump,
      bench: toggleTry,
      restart: director.restart,
      fullscreen: () => {
        const done = document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
        done.catch(() => {});
      },
      speed: noop,
      dev: noop,
    },
    [original, revival],
  );

  // useKeyboard has no T; this hears it on the page (not inside the frames).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as Partial<HTMLElement> | null;
      if (e.ctrlKey || e.metaKey || e.altKey || t?.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t?.tagName ?? '')) return;
      if (e.key.toLowerCase() === 't') setTryOpen((o) => !o);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const app = state?.app ?? APP;
  const intro = !!state && !state.playing && director.index === 0;
  const badge = feed.status === 'live' ? 'live' : feed.source === 'fixture' ? 'fixture' : feed.status;
  const header = (
    <header className="case-head">
      <h1 className="case-head__mark">MUSÉANCE</h1>
      {state && (
        <div className="case-play">
          <button type="button" className="case-play__btn" onClick={director.toggle}>
            {state.playing ? 'Pause' : 'Play'}
          </button>
          {intro && (
            <p className="case-play__intro">
              MUSÉANCE checks whether a <Explain term="revival">rebuilt app</Explain> really behaves like the dead{' '}
              <Explain term="original">original</Explain>.
            </p>
          )}
        </div>
      )}
      {!intro && <p className="case-head__tag">Bring back a dead app. Prove what is real.</p>}
      <div className="case-head__pick">
        <AppPicker current={app} />
      </div>
      {state && <button type="button" className="case-try-btn" onClick={toggleTry} aria-expanded={tryOpen}>
        {tryOpen ? 'Close Try it' : 'Try it yourself'}
      </button>}
      <span className={`case-badge case-badge--${badge}`} title={feed.error}>
        {badge}
      </span>
    </header>
  );

  if (!state || !feed.bundle) {
    return (
      <div className="case">
        {header}
        <p className="case-wait">{feed.error ?? 'Waiting for the case file.'}</p>
      </div>
    );
  }

  const tags = focus?.verdict ? tagsOf(focus.verdict) : null;
  const v = buildName(state.exhibits.revivalSrc);
  // Read lazily: the original's document is replaced on every reload.
  const label = (sel: string) => labelFrom(original?.contentDocument ?? null)(sel);
  const d = state.divergence;
  // shortcut: the running feed keeps the builds.ts it started with, so the UI's own table sets the display scale; drop once the feed restarts.
  const scale = BUILDS[state.app]?.scale ?? state.exhibits.scale;

  return (
    <div className="case">
      {header}
      <aside className="case-left">
        <Pipeline bundle={feed.bundle} state={state} />
      </aside>
      <main className="case-mid">
        <div className="case-builds">
          <BuildFrame
            label="Original (oracle)"
            term="original"
            src={state.exhibits.originalSrc}
            scale={scale}
            output={tags?.original}
            frameRef={setOriginal}
          />
          <BuildFrame
            label={v ? `Revival ${v}` : 'Revival'}
            term="revival"
            src={state.exhibits.revivalSrc}
            scale={scale}
            output={tags?.revival}
            frameRef={setRevival}
          />
        </div>
        {d && (
          <p className="case-diverge">
            <span className="case-label"><Explain term="mismatch">Divergence</Explain> {d.ref}</span>
            <Explain term="original">original</Explain> <b>{prettyOutput(d.original) || '(empty)'}</b>, <Explain term="revival">revival</Explain> <b className="is-struck">{prettyOutput(d.revival) || '(empty)'}</b>
            {d.steps.length > 0 && <span className="case-diverge__steps"> after {d.steps.map((s) => stepText(s, label)).join(', then ')}</span>}
          </p>
        )}
        <Narrators moods={state.moods} subtitle={state.subtitle} stress={state.stress} />
      </main>
      <aside className="case-right">
        <ClaimDetail view={focus} label={label} />
        <ClaimList cards={state.cards} focusId={state.focusId} />
      </aside>
      {tryOpen && (
        <section className="case-try" aria-label="Try it yourself">
          <TryIt
            app={state.app}
            originalFrame={original}
            revivalFrame={revival}
            originalSrc={state.exhibits.originalSrc}
            revivalSrc={state.exhibits.revivalSrc}
            observeDefault={feed.bundle.claims[0]?.test.observe ?? 'body'}
            onVerdict={director.submitBench}
          />
        </section>
      )}
      <footer className="case-numbers">
        <NumbersBar scores={state.scores} source={state.source} explain />
      </footer>
    </div>
  );
}
