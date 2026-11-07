import { useEffect, useState, type ComponentProps } from 'react';
import type { LockStatus, Verdict } from './contracts';
import { BenchConsole } from './bench/BenchConsole';
import { ClaimSpread } from './cards/ClaimSpread';
import { DrHoot } from './cast/DrHoot';
import { Faux } from './cast/Faux';
import { Ghost } from './cast/Ghost';
import { LittleGuy } from './cast/LittleGuy';
import { McClusky } from './cast/McClusky';
import { Stenographer } from './cast/Stenographer';
import type { CardStatus } from './engine/types';
import { useDirector } from './engine/useDirector';
import { ExhibitFrame } from './exhibits/ExhibitFrame';
import { reloadFrame, runSteps } from './exhibits/runSteps';
import { useCaseFeed } from './feed/useCaseFeed';
import { BENCH_SUGGESTIONS } from './fixtures';
import { CredibilityMeter } from './hud/CredibilityMeter';
import { DigTicker } from './hud/DigTicker';
import { LedgerTape } from './hud/LedgerTape';
import { Masthead } from './hud/Masthead';
import { NumbersBar } from './hud/NumbersBar';
import { PhaseDocket } from './hud/PhaseDocket';
import { ReaderSheet } from './hud/ReaderSheet';
import { StressCandle } from './hud/StressCandle';
import { Subtitles } from './hud/Subtitles';
import { SentenceScreen } from './sentence/SentenceScreen';
import { CourtroomBackdrop } from './set/Courtroom';
import { GUY_SLOTS, place, ZONES } from './stage/layout';
import { Stage } from './stage/Stage';
import { useKeyboard } from './stage/useKeyboard';
import { CaseView } from './case/CaseView';
import { CourtroomView } from './courtroom/CourtroomView';

type Tag = NonNullable<ComponentProps<typeof ExhibitFrame>['output']>;

const SPEEDS = [0.25, 0.5, 1, 1.5, 2, 3, 5];
const STEP_MS = 250;
const RULED: Record<LockStatus, string> = {
  LOCKED: 'sworn and locked',
  STRUCK: 'struck for perjury',
  UNSWORN: 'unsworn, the court could not rule',
  FABRICATED: 'fabricated',
};
const isRuled = (s: CardStatus): s is LockStatus => s in RULED;

// A bare URL opens the real todo case; useCaseFeed reads the location at first render, after this runs.
if (!location.search) history.replaceState(null, '', '?source=runs&app=todo');
// Same reading as useCaseFeed, for the masthead before the bundle lands.
const QUERY = new URLSearchParams(location.search);

// A replay leaves focus on the exhibit key it clicked last. useKeyboard hears keys inside the frames, but not while
// one reloads, so focus goes back to the stage before the next replay reloads them.
function releaseKeyboard(frames: HTMLIFrameElement[]) {
  const active = document.activeElement;
  if (active instanceof HTMLIFrameElement && frames.includes(active)) active.blur();
}

// The original is judged against the claim, the revival against the original.
function tagsOf(v: Verdict): { original: Tag; revival: Tag } {
  return {
    original: { text: v.original, tone: v.flaky || v.claim_true == null ? 'neutral' : v.claim_true ? 'match' : 'diverge' },
    revival: { text: v.revival, tone: v.flaky ? 'neutral' : v.match ? 'match' : 'diverge' },
  };
}

export default function App() {
  const view = QUERY.get('view');
  return view === 'stage' ? <CourtStage /> : view === 'case' ? <CaseView /> : <CourtroomView />;
}

// The courtroom show, kept whole behind ?view=stage.
function CourtStage() {
  const feed = useCaseFeed();
  const director = useDirector(feed.bundle, { autoplay: true });
  const { state } = director;
  const [speed, setSpeed] = useState(1);
  const [dev, setDev] = useState(false);
  // State, not refs: the bench console and the replay effect must see the iframes once they mount.
  const [original, setOriginal] = useState<HTMLIFrameElement | null>(null);
  const [revival, setRevival] = useState<HTMLIFrameElement | null>(null);

  const focus = state?.cards.findLast((k) => k.claim.id === state.focusId) ?? null;
  // The claim whose test replays in both exhibits: chosen by its cross beat and held through its ruling.
  const crossing = state?.phase === 'cross' && state.exhibits.revival === 'cross' ? (focus?.claim ?? null) : null;
  const stepDelayMs = Math.round(STEP_MS / Math.max(1, speed));

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
      await runSteps(frame, crossing.test.steps, crossing.test.observe, { stepDelayMs, onStep: halt });
    };
    // The replay is for the room; the ruling comes from the court's verdict whatever the frames show.
    const replays = [original, revival].map((frame) =>
      replay(frame).catch((e: unknown) => {
        if (live) console.warn(`exhibit replay of ${crossing.id} failed:`, e);
      }),
    );
    void Promise.all(replays).then(() => live && releaseKeyboard([original, revival]));
    return () => {
      live = false;
      releaseKeyboard([original, revival]);
    };
  }, [crossing, original, revival, stepDelayMs]);

  useKeyboard({
    toggle: director.toggle,
    next: director.next,
    prev: director.prev,
    jump: director.jump,
    bench: () => director.jump('bench'),
    restart: director.restart,
    fullscreen: () => {
      // A refused request (no user gesture, kiosk policy) leaves the stage as it was.
      const done = document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
      done.catch(() => {});
    },
    speed: (step) => {
      const next = SPEEDS[Math.min(SPEEDS.length - 1, Math.max(0, SPEEDS.indexOf(speed) + step))];
      setSpeed(next);
      director.setSpeed(next);
    },
    dev: () => setDev((d) => !d),
  }, [original, revival]);

  const rail = (
    <div className="stage-zone stage-rail" style={place(ZONES.rail)}>
      <Masthead appLabel={state?.appLabel ?? (QUERY.get('app') || 'app1')} source={feed.source} status={feed.status} />
      {state && <PhaseDocket phase={state.phase} />}
    </div>
  );

  if (!state) {
    return (
      <Stage>
        <CourtroomBackdrop />
        {rail}
        <div className="stage-zone" style={place(ZONES.subtitles)}>
          <Subtitles line={{ who: 'THE CLERK', text: feed.error ?? 'Waiting for the case file.' }} />
        </div>
      </Stage>
    );
  }

  const tags = focus?.verdict ? tagsOf(focus.verdict) : null;
  const ruling = focus && isRuled(focus.status) ? `Claim ${focus.claim.id}, ${focus.claim.text}: ${RULED[focus.status]}.` : '';
  const fixture = state.source === 'fixture';

  return (
    <Stage>
      <CourtroomBackdrop tension={state.stress} />
      <div className="stage-zone" style={place(ZONES.original)}>
        <ExhibitFrame
          which="original"
          mode={state.exhibits.original}
          src={state.exhibits.originalSrc}
          scale={state.exhibits.scale}
          title={`${state.appLabel}, the original`}
          output={tags?.original}
          frameRef={setOriginal}
        >
          <DigTicker items={state.evidenceShown} total={feed.bundle?.evidence.length ?? state.evidenceShown.length} />
        </ExhibitFrame>
      </div>
      <div className="stage-zone" style={place(ZONES.revival)}>
        <ExhibitFrame
          which="revival"
          mode={state.exhibits.revival}
          src={state.exhibits.revivalSrc}
          scale={state.exhibits.scale}
          title={`${state.appLabel}, the revival`}
          output={tags?.revival}
          frameRef={setRevival}
        >
          <ReaderSheet lines={state.sheetShown} wordCount={state.wordCount} />
        </ExhibitFrame>
      </div>
      <div className="stage-zone" style={place(ZONES.ghost)}>
        <Ghost mood={state.moods.ghost} />
      </div>
      <div className="stage-zone" style={place(ZONES.faux)}>
        <Faux mood={state.moods.faux} />
      </div>
      <div className="stage-zone" style={place(ZONES.candle)}>
        <StressCandle stress={state.stress} />
      </div>
      <div className="stage-zone" style={place(ZONES.meter)}>
        <CredibilityMeter credibility={state.scores.credibility} start={state.scores.credibilityStart} />
      </div>
      <div className="stage-zone" style={place(ZONES.mcclusky)}>
        <McClusky mood={state.moods.mcclusky} stress={state.stress} />
      </div>
      <div className="stage-zone" style={place(ZONES.ledger)}>
        <LedgerTape events={state.ledgerTail} />
      </div>
      <div className="stage-zone" style={place(ZONES.hoot)}>
        <DrHoot mood={state.moods.hoot} />
      </div>
      <div className="stage-zone" style={place(ZONES.steno)}>
        <Stenographer mood={state.moods.steno} />
      </div>
      <div className="stage-zone" style={place(ZONES.cards)}>
        <ClaimSpread cards={state.cards} focusId={state.focusId} showBets={state.phase === 'swear'} width={ZONES.cards[2]} height={ZONES.cards[3]} />
      </div>
      {/* shortcut: screens past the sixth get no little guy; add floor slots if a case has more */}
      {state.guys.slice(0, GUY_SLOTS.length).map((g, i) => (
        <div key={g.screen} className="stage-zone" style={place(GUY_SLOTS[i])}>
          <LittleGuy kind={g.kind} glyph={g.glyph} state={g.state} label={g.screen} />
        </div>
      ))}
      <div className="stage-zone" style={place(state.bench.open ? ZONES.subtitlesBeside : ZONES.subtitles)}>
        <Subtitles line={state.subtitle} />
      </div>
      {rail}
      <div className="stage-zone" style={place(ZONES.numbers)}>
        <NumbersBar scores={state.scores} source={state.source} />
      </div>
      <BenchConsole
        open={state.bench.open}
        app={state.app}
        observe={feed.bundle?.claims[0]?.test.observe ?? 'body'}
        originalFrame={original}
        revivalFrame={revival}
        originalSrc={state.exhibits.originalSrc}
        revivalSrc={state.exhibits.revivalSrc}
        suggestions={fixture ? BENCH_SUGGESTIONS : []}
        onVerdict={director.submitBench}
        onClose={director.next}
      />
      {state.phase === 'sentence' && (
        <SentenceScreen state={state} caseFile={feed.bundle?.caseFile ?? null} leaderboard={state.leaderboard} />
      )}
      <p className="stage-sr" role="status">
        {ruling}
      </p>
      {dev && (
        <p className="stage-dev">
          beat {director.index + 1}/{director.total} · {state.phase} · {state.playing ? 'playing' : 'paused'} · {speed}x ·{' '}
          {state.source}
          {feed.status === state.source ? '' : ` (${feed.status})`}
        </p>
      )}
    </Stage>
  );
}
