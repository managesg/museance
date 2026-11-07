// Turns a visitor's clicks, typing and keys in the original's same-origin frame into CONTRACTS.md steps.

export type Rec =
  | { kind: 'click'; sel: string | null }
  | { kind: 'input'; sel: string | null; value: string }
  | { kind: 'key'; key: string };

// Keys that act on their own; printable keys arrive as the field's value instead.
const KEYS = new Set(['Enter', 'Escape', 'Tab', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight']);
const esc = (s: string) => globalThis.CSS?.escape?.(s) ?? s.replace(/[^\w-]/g, '\\$&');

/** The steps after one more event: typing into the same field keeps one type step with its latest value. */
export function addRec(steps: string[], e: Rec): string[] {
  if (e.kind === 'key') return KEYS.has(e.key) ? [...steps, `key:${e.key}`] : steps;
  if (!e.sel) return steps;
  if (e.kind === 'click') return [...steps, `click:${e.sel}`];
  const head = `type:${e.sel}:`;
  return steps.at(-1)?.startsWith(head) ? [...steps.slice(0, -1), head + e.value] : [...steps, head + e.value];
}

/** '#id', else the nearest ancestor with an id plus the child's position, e.g. '#todo > li:nth-child(2) .complete'. */
export function selectorOf(el: Element | null): string | null {
  if (!el) return null;
  if (el.id) return `#${esc(el.id)}`;
  let child: Element = el;
  let anchor = el.parentElement;
  while (anchor && !anchor.id) {
    child = anchor;
    anchor = anchor.parentElement;
  }
  if (!anchor) return null;
  const nth = `${child.tagName.toLowerCase()}:nth-child(${Array.from(anchor.children).indexOf(child) + 1})`;
  const base = `#${esc(anchor.id)} > ${nth}`;
  if (child === el) return base;
  const cls = el.classList[0];
  return `${base} ${cls ? `.${esc(cls)}` : el.tagName.toLowerCase()}`;
}

const TEXT_FIELD = /^(INPUT|TEXTAREA|SELECT)$/;
const CLICKABLE = 'button, a, [role=button], input[type=submit], input[type=button], input[type=checkbox], input[type=radio], label, li';

/** Listens on the frame's document; returns the detach. Only real (trusted) input counts, never a replay. */
export function record(doc: Document, push: (e: Rec) => void): () => void {
  const onClick = (e: MouseEvent) => {
    if (!e.isTrusted) return;
    const t = e.target as Element | null;
    // Clicking into a text field only focuses it; the type step that follows already clicks it.
    if (!t || (TEXT_FIELD.test(t.tagName) && !/^(submit|button|checkbox|radio)$/.test((t as HTMLInputElement).type))) return;
    push({ kind: 'click', sel: selectorOf(t.closest(CLICKABLE) ?? t) });
  };
  const onInput = (e: Event) => {
    const t = e.target as HTMLInputElement | null;
    if (!e.isTrusted || !t || !TEXT_FIELD.test(t.tagName)) return;
    push({ kind: 'input', sel: selectorOf(t), value: t.value });
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.isTrusted) push({ kind: 'key', key: e.key });
  };
  doc.addEventListener('click', onClick, true);
  doc.addEventListener('input', onInput, true);
  doc.addEventListener('keydown', onKey, true);
  return () => {
    doc.removeEventListener('click', onClick, true);
    doc.removeEventListener('input', onInput, true);
    doc.removeEventListener('keydown', onKey, true);
  };
}

/** A court output in plain words: the court's ERROR strings become what a person would say. */
export function plainOutput(out: string | null | undefined): string {
  if (out == null) return '';
  const obs = /^ERROR:observe (.+?): \w+$/.exec(out);
  if (obs) return `nothing to read: it has no ${obs[1]}`;
  const missing = /^ERROR:missing selector: (.+)$/.exec(out) ?? /^missing selector: (.+)$/.exec(out);
  if (missing) return `it has no ${missing[1]}`;
  const step = /^ERROR:step (\d+) (.+): \w+$/.exec(out);
  if (step) return `could not do step ${Number(step[1]) + 1} (${step[2]})`;
  if (out.startsWith('ERROR:load')) return 'it did not load';
  return out.replace(/\s*\n\s*/g, ' · ');
}
