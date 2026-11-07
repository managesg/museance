import type { Verdict } from '../contracts';
import { KEY_LABELS } from '../cards/keys';
import { reloadFrame, runSteps } from '../exhibits/runSteps';
import { postBench } from '../feed/benchClient';

export interface BenchKey {
  label: string;
  step: string;
}

type Run = (steps: string[], pace?: { stepDelayMs: number }) => Promise<string>;

// Shrink candidates run fast: the room watches the two full runs, not the search.
const SHRINK_PACE = { stepDelayMs: 40 };
const SHRINK_CAP = 20;

const ruledHere = new WeakSet<Verdict>();
let benchCount = 0;

/** True when this browser ruled `v` because the court's bench endpoint returned nothing. */
export const ruledLocally = (v: Verdict): boolean => ruledHere.has(v);

export const FIXTURE_KEYS: BenchKey[] = Object.entries(KEY_LABELS).map(([id, label]) => ({ label, step: `click:#${id}` }));

/** The original's own buttons as keys; empty when its document cannot be read. */
export function readKeys(frame: HTMLIFrameElement | null): BenchKey[] {
  return Array.from(frame?.contentDocument?.querySelectorAll<HTMLElement>('button[id]') ?? [], (b) => ({
    label: b.innerText.trim() || (Object.hasOwn(KEY_LABELS, b.id) ? KEY_LABELS[b.id] : b.id),
    step: `click:#${CSS.escape(b.id)}`,
  }));
}

// Typed '/' and '*' reach keys whose faces read '÷' and '×', and the reverse.
const fold = (s: string) => s.toLowerCase().replace(/÷/g, '/').replace(/[×*]/g, 'x');

/** '7/0=' to steps by key face, longest face first; `bad` is the first character no key shows. */
export function parseShortcut(text: string, keys: BenchKey[]): { steps: string[]; bad?: string } {
  const faces = keys
    .map((k) => ({ face: fold(k.label), step: k.step }))
    .filter((k) => k.face)
    .sort((a, b) => b.face.length - a.face.length);
  const t = fold(text);
  const steps: string[] = [];
  for (let i = 0; i < t.length; ) {
    const hit = faces.find((k) => t.startsWith(k.face, i));
    if (hit) {
      steps.push(hit.step);
      i += hit.face.length;
    } else if (/\s/.test(t[i])) i++;
    else return { steps, bad: t[i] };
  }
  return { steps };
}

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

// The original is the reference: a step it cannot perform is a bad input, not a ruling.
function checkSteps(doc: Document, steps: string[]): void {
  steps.forEach((step, i) => {
    const sel = step.startsWith('click:') ? step.slice(6) : step.startsWith('type:') ? step.slice(5).split(':')[0] : '';
    if (!sel) return;
    let found: Element | null = null;
    try {
      found = doc.querySelector(sel);
    } catch {
      // An unparsable selector finds nothing and gets the same message.
    }
    if (!found) {
      throw new Error(`Step ${i + 1} presses ${sel}, but the original has no ${sel}. Clear the input and compose it from the keys on the bench.`);
    }
  });
}

function build(frame: HTMLIFrameElement | null, name: string, observe: string): Run {
  if (!frame || frame.contentDocument?.URL === 'about:blank') {
    throw new Error(`The ${name} exhibit is not on stage. Wait until it shows, then run again.`);
  }
  if (!frame.contentDocument) {
    throw new Error(`The ${name} exhibit is served from another origin, so the bench cannot press its keys. Serve both builds from the stage's origin, or start the court's bench endpoint.`);
  }
  return async (steps, pace) => {
    await reloadFrame(frame).catch((e: unknown) => {
      throw new Error(`The ${name} exhibit did not reload (${message(e)}). Check that it shows, then run again.`);
    });
    return runSteps(frame, steps, observe, pace).catch((e: unknown) => {
      // As in court/steps.py, a key the build lacks is an observation, so a revival missing a key diverges.
      if (message(e).startsWith('missing selector')) return `ERROR:${message(e)}`;
      throw new Error(`The ${name} exhibit could not run the input (${message(e)}). Check that it shows, then run again.`);
    });
  };
}

/** court/shrink.py under a run budget: drop one step at a time, restarting after each drop that keeps the builds apart. */
async function shrink(steps: string[], differs: (cand: string[]) => Promise<boolean>): Promise<string[]> {
  let cur = steps;
  for (let i = 0, runs = 0; i < cur.length && runs < SHRINK_CAP; runs++) {
    const cand = cur.toSpliced(i, 1);
    if (await differs(cand)) {
      cur = cand;
      i = 0;
    } else i++;
  }
  return cur;
}

/** Rule the judge's input: the court's bench endpoint first, else this browser drives both exhibits. */
export async function benchRun(
  original: HTMLIFrameElement | null,
  revival: HTMLIFrameElement | null,
  steps: string[],
  observe: string,
  app?: string,
  srcs?: { original: string; revival: string },
): Promise<Verdict> {
  const doc = original?.contentDocument;
  if (doc) checkSteps(doc, steps);
  const court = app && srcs ? await postBench(app, steps, observe, srcs.original, srcs.revival) : null;
  if (court) return court;

  const orig = build(original, 'original', observe);
  const rev = build(revival, 'revival', observe);
  const twice = async (run: Run): Promise<[string, string]> => [await run(steps), await run(steps)];
  const [[o1, o2], [r1, r2]] = await Promise.all([twice(orig), twice(rev)]);
  // Same rule as court/court.py: a flaky build is neither a match nor a divergence.
  const flaky = o1 !== o2 || r1 !== r2;
  const match = !flaky && o1 === r1;
  let shrunk: string[] = [];
  if (!flaky && !match) {
    shrunk = await shrink(steps, async (cand) => {
      const [a, b] = await Promise.all([orig(cand, SHRINK_PACE), rev(cand, SHRINK_PACE)]);
      return a !== b;
    });
    // Leave both exhibits showing the input the ruling reports, not the last shrink candidate.
    await Promise.all([orig(steps), rev(steps)]);
  }
  const v: Verdict = {
    ref: `bench-${++benchCount}`,
    kind: 'attack',
    original: o1,
    revival: r1,
    claim_true: null,
    match,
    flaky,
    shrunk_steps: shrunk,
  };
  ruledHere.add(v);
  return v;
}
