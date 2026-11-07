import { useEffect, useEffectEvent } from 'react';
import { PHASES, type Phase } from '../engine/types';

export interface StageKeys {
  toggle(): void;
  next(): void;
  prev(): void;
  jump(phase: Phase): void;
  bench(): void;
  restart(): void;
  fullscreen(): void;
  speed(step: 1 | -1): void;
  dev(): void;
}

// Duck-typed: a key from inside an exhibit comes from the iframe's realm, where instanceof HTMLElement fails.
const typing = (t: EventTarget | null) => {
  const el = t as Partial<HTMLElement> | null;
  return !!el && (el.isContentEditable === true || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName ?? ''));
};

/**
 * The operator's remote: Space, arrows, 1-8 for phases, B bench, R restart, F fullscreen, + and - speed, D dev strip.
 * It also listens inside the exhibit frames, because runSteps focuses the keys it clicks and takes the keyboard with it.
 */
export function useKeyboard(keys: StageKeys, [original, revival]: readonly [HTMLIFrameElement | null, HTMLIFrameElement | null]) {
  const onKey = useEffectEvent((e: KeyboardEvent) => {
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || typing(e.target)) return;
    const k = e.key.toLowerCase();
    const n = Number(k);
    if (k === ' ') keys.toggle();
    else if (k === 'arrowright') keys.next();
    else if (k === 'arrowleft') keys.prev();
    else if (Number.isInteger(n) && n >= 1 && n <= PHASES.length) keys.jump(PHASES[n - 1]);
    else if (k === 'b') keys.bench();
    else if (k === 'r') keys.restart();
    else if (k === 'f') keys.fullscreen();
    else if (k === '+' || k === '=') keys.speed(1);
    else if (k === '-' || k === '_') keys.speed(-1);
    else if (k === 'd') keys.dev();
    else return;
    // Space would otherwise press whatever button holds focus.
    e.preventDefault();
  });

  // Bubble phase: the bench console stops propagation, so the judge's typing never reaches the stage.
  useEffect(() => {
    const listener = (e: KeyboardEvent) => onKey(e);
    // contentWindow keeps its identity across reloads while each page gets a fresh window, so listen on every load;
    // a repeat on the same page is a no-op.
    const hear = (frame: HTMLIFrameElement, on: boolean) => {
      try {
        if (on) frame.contentWindow?.addEventListener('keydown', listener);
        else frame.contentWindow?.removeEventListener('keydown', listener);
      } catch {
        // A cross-origin exhibit keeps its own keys; the stage hears them again once focus leaves it.
      }
    };
    const onLoad = (e: Event) => hear(e.currentTarget as HTMLIFrameElement, true);
    const frames = [original, revival].filter((f): f is HTMLIFrameElement => f !== null);
    window.addEventListener('keydown', listener);
    for (const f of frames) {
      hear(f, true);
      f.addEventListener('load', onLoad);
    }
    return () => {
      window.removeEventListener('keydown', listener);
      for (const f of frames) {
        f.removeEventListener('load', onLoad);
        hear(f, false);
      }
    };
  }, [original, revival]);
}
