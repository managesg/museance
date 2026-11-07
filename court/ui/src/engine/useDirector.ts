import { useCallback, useEffect, useMemo, useState } from 'react';
import type { CaseBundle, LedgerEvent, Verdict } from '../contracts';
import { buildScript, foldStates, type BenchRuns } from './director';
import { appendEvent, synthesizeLedger } from './hash';
import { PHASES, type Phase, type StageState } from './types';

export interface Director {
  state: StageState | null; index: number; total: number;
  play(): void; pause(): void; toggle(): void; next(): void; prev(): void; jump(phase: Phase): void; restart(): void;
  setSpeed(n: number): void; submitBench(v: Verdict): void;
}

export function useDirector(bundle: CaseBundle | null, opts: { autoplay?: boolean; speed?: number } = {}): Director {
  const [synth, setSynth] = useState<{ of: CaseBundle; ledger: LedgerEvent[] } | null>(null);
  const [benchVerdicts, setBenchVerdicts] = useState<Verdict[]>([]);
  const [benchEvents, setBenchEvents] = useState<LedgerEvent[]>([]);
  const [benchPassed, setBenchPassed] = useState(false);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(opts.autoplay ?? false);
  const [speed, setSpeed] = useState(opts.speed ?? 1);
  const [app, setApp] = useState(bundle?.app);

  // A different case starts the show over (state adjusted during render, as the React docs recommend).
  if (bundle?.app !== app) {
    setApp(bundle?.app);
    setIndex(0);
    setBenchVerdicts([]);
    setBenchPassed(false);
  }

  useEffect(() => {
    if (!bundle || bundle.ledger.length) return;
    let live = true;
    void synthesizeLedger(bundle).then((ledger) => live && setSynth({ of: bundle, ledger }));
    return () => {
      live = false;
    };
  }, [bundle]);

  const full = useMemo(
    () => (bundle && !bundle.ledger.length && synth?.of === bundle ? { ...bundle, ledger: synth.ledger } : bundle),
    [bundle, synth],
  );

  // Bench verdicts are re-chained onto the ledger whenever either changes, so every hash links to the one before.
  useEffect(() => {
    let live = true;
    void (async () => {
      const chain = [...(full?.ledger ?? [])];
      const out: LedgerEvent[] = [];
      for (const v of benchVerdicts) {
        const ev = await appendEvent(chain, 'verdict', v);
        chain.push(ev);
        out.push(ev);
      }
      if (live) setBenchEvents(out);
    })();
    return () => {
      live = false;
    };
  }, [full, benchVerdicts]);

  const runs = useMemo<BenchRuns>(
    () => ({ verdicts: benchVerdicts, events: benchEvents.slice(0, benchVerdicts.length) }),
    [benchVerdicts, benchEvents],
  );
  const script = useMemo(() => (full ? buildScript(full, runs) : []), [full, runs]);
  const states = useMemo(() => (full ? foldStates(full, script) : []), [full, script]);
  const total = script.length;
  const last = Math.max(0, total - 1);
  const at = Math.min(index, last);
  const ms = script[at]?.ms ?? 0;
  // Autoplay waits at the bench until someone presses next or a bench verdict lands.
  const hold = script[at]?.kind === 'bench' && !benchPassed;

  // benchVerdicts.length restarts the clock, so every bench run gets its full beat on screen.
  useEffect(() => {
    if (!playing || hold || at >= last) return;
    const t = setTimeout(() => setIndex(at + 1), ms / Math.max(speed, 0.05));
    return () => clearTimeout(t);
  }, [playing, hold, at, last, ms, speed, benchVerdicts.length]);

  const play = useCallback(() => setPlaying(true), []);
  const pause = useCallback(() => setPlaying(false), []);
  const toggle = useCallback(() => setPlaying((p) => !p), []);
  const next = useCallback(() => setIndex((i) => Math.min(i + 1, last)), [last]);
  const prev = useCallback(() => setIndex((i) => Math.max(0, Math.min(i, last) - 1)), [last]);
  const jump = useCallback(
    (phase: Phase) => {
      const j = script.findIndex((b) => PHASES.indexOf(b.phase) >= PHASES.indexOf(phase));
      if (j < 0) return;
      setIndex(j);
      setBenchPassed(false);
    },
    [script],
  );
  const restart = useCallback(() => {
    setIndex(0);
    setBenchVerdicts([]);
    setBenchPassed(false);
  }, []);
  const submitBench = useCallback((v: Verdict) => {
    setBenchVerdicts((vs) => [...vs, v]);
    setBenchPassed(true);
  }, []);

  const state = useMemo(() => (states[at] ? { ...states[at], playing } : null), [states, at, playing]);
  return { state, index: at, total, play, pause, toggle, next, prev, jump, restart, setSpeed, submitBench };
}
