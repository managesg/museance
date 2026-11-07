// Replays CONTRACTS.md steps inside a same-origin exhibit iframe, mirroring court/steps.py (Playwright),
// so the audience watches the same presses the court ruled on. Callers reloadFrame() first for a fresh page.

type Win = Window & typeof globalThis;
type Step =
  | { kind: 'click' | 'key' | 'wait'; arg: string }
  | { kind: 'type'; arg: string; text: string };

const LOAD_TIMEOUT_MS = 10_000;
const SETTLE_MS = 40;
const PRESSED = 'data-exhibit-pressed';
const POINTER_FOCUS = 'data-exhibit-pointer-focus';
// Literal colours: the stage's CSS variables do not reach into the app's document. A real mouse click focuses
// without the keyboard focus ring, but replayed clicks are untrusted, so the ring is hidden by hand until blur.
const REPLAY_CSS =
  `[${POINTER_FOCUS}]:focus-visible{outline:none!important}` +
  `[${PRESSED}],[${PRESSED}]:focus-visible{background:#C29A45!important;color:#2B211C!important;outline:3px solid #2B211C!important;transform:translateY(2px)!important}`;
const KEY_CODES: Record<string, number> = {
  Enter: 13, Escape: 27, Backspace: 8, Tab: 9, ' ': 32, Delete: 46, ArrowLeft: 37, ArrowUp: 38, ArrowRight: 39, ArrowDown: 40,
};
// Reloads in flight: a run that starts before the new page commits waits for it instead of pressing the old one.
const reloading = new WeakMap<HTMLIFrameElement, Promise<void>>();

const sleep = (ms: number) => new Promise<void>((done) => setTimeout(done, ms));

// Same grammar as court/steps.py: type splits on the first ':' after the selector, so its text may hold ':'.
function parse(step: string): Step {
  const cut = step.indexOf(':');
  const kind = step.slice(0, cut);
  const arg = step.slice(cut + 1);
  if (cut > 0 && arg) {
    if (kind === 'click' || kind === 'key') return { kind, arg };
    if (kind === 'wait' && /^\d+$/.test(arg)) return { kind, arg };
    const sep = arg.indexOf(':');
    if (kind === 'type' && sep > 0) return { kind, arg: arg.slice(0, sep), text: arg.slice(sep + 1) };
  }
  throw new Error(`bad step: ${step}`);
}

function nextLoad(frame: HTMLIFrameElement): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      frame.removeEventListener('load', done);
      reject(new Error(`exhibit did not load: ${frame.src}`));
    }, LOAD_TIMEOUT_MS);
    function done() {
      clearTimeout(timer);
      resolve();
    }
    frame.addEventListener('load', done, { once: true });
  });
}

// A same-origin frame always has a document (about:blank while it navigates); null means cross-origin or detached.
async function documentOf(frame: HTMLIFrameElement): Promise<Document> {
  await reloading.get(frame);
  let doc = frame.contentDocument;
  if (doc && (doc.readyState !== 'complete' || doc.URL === 'about:blank')) {
    await nextLoad(frame);
    doc = frame.contentDocument;
  }
  if (!doc?.defaultView) throw new Error(`exhibit is not readable (cross-origin or detached): ${frame.src}`);
  return doc;
}

function find(doc: Document, sel: string): Element {
  const el = doc.querySelector(sel);
  if (!el) throw new Error(`missing selector: ${sel}`);
  return el;
}

function styleReplay(doc: Document) {
  if (doc.getElementById('exhibit-replay-style')) return;
  const style = doc.createElement('style');
  style.id = 'exhibit-replay-style';
  style.textContent = REPLAY_CSS;
  (doc.head ?? doc.documentElement).append(style);
}

function pressFor(el: Element, ms: number) {
  el.setAttribute(PRESSED, '');
  setTimeout(() => el.removeAttribute(PRESSED), ms);
}

// The event sequence of a real mouse click at the element's centre, built in the app's own realm.
function click(win: Win, el: Element) {
  const doc = el.ownerDocument;
  styleReplay(doc);
  const box = el.getBoundingClientRect();
  const at = {
    bubbles: true, cancelable: true, composed: true, view: win, button: 0, detail: 1,
    clientX: box.left + box.width / 2, clientY: box.top + box.height / 2,
  };
  const pointer = { ...at, pointerId: 1, pointerType: 'mouse', isPrimary: true };
  el.dispatchEvent(new win.PointerEvent('pointerdown', { ...pointer, buttons: 1 }));
  // A mousedown the app cancels does not move focus, as in a browser.
  if (el.dispatchEvent(new win.MouseEvent('mousedown', { ...at, buttons: 1 }))) {
    (el as HTMLElement).focus?.({ preventScroll: true });
    if (doc.activeElement === el && !el.hasAttribute(POINTER_FOCUS)) {
      el.setAttribute(POINTER_FOCUS, '');
      el.addEventListener('blur', () => el.removeAttribute(POINTER_FOCUS), { once: true });
    }
  }
  el.dispatchEvent(new win.PointerEvent('pointerup', pointer));
  el.dispatchEvent(new win.MouseEvent('mouseup', at));
  el.dispatchEvent(new win.MouseEvent('click', at));
}

function type(win: Win, el: Element, text: string) {
  (el as HTMLElement).focus?.({ preventScroll: true });
  // Frameworks such as React watch the prototype's value setter, so a plain assignment would go unseen.
  const proto = [win.HTMLInputElement, win.HTMLTextAreaElement, win.HTMLSelectElement].find((C) => el instanceof C)?.prototype;
  const setValue = proto && Object.getOwnPropertyDescriptor(proto, 'value')?.set;
  if (setValue) setValue.call(el, text);
  else el.textContent = text;
  el.dispatchEvent(new win.InputEvent('input', { bubbles: true, composed: true, inputType: 'insertText', data: text }));
  el.dispatchEvent(new win.Event('change', { bubbles: true }));
}

// Two frames replaying at once steal focus from each other, so a key goes where this page's last press or typing was, as in Playwright's own page.
const lastTouched = new WeakMap<Document, Element>();

function key(win: Win, doc: Document, name: string) {
  const active = doc.activeElement && doc.activeElement !== doc.body ? doc.activeElement : null;
  const el = active ?? lastTouched.get(doc) ?? doc.body ?? doc.documentElement;
  const keyCode = KEY_CODES[name] ?? (name.length === 1 ? name.toUpperCase().charCodeAt(0) : 0);
  const code = /^[a-z]$/i.test(name) ? `Key${name.toUpperCase()}` : /^\d$/.test(name) ? `Digit${name}` : name === ' ' ? 'Space' : name;
  const init = { key: name, code, keyCode, which: keyCode, bubbles: true, cancelable: true, composed: true, view: win };
  el.dispatchEvent(new win.KeyboardEvent('keydown', init));
  // Older apps listen for keypress, which Playwright's press also sends for printable keys and Enter.
  if (name.length === 1 || name === 'Enter') {
    el.dispatchEvent(new win.KeyboardEvent('keypress', { ...init, charCode: name === 'Enter' ? 13 : name.charCodeAt(0) }));
  }
  el.dispatchEvent(new win.KeyboardEvent('keyup', init));
}

/** Runs `steps` in the exhibit and returns the trimmed innerText of `observe`. */
export async function runSteps(
  frame: HTMLIFrameElement,
  steps: string[],
  observe: string,
  opts: { stepDelayMs?: number; onStep?: (i: number, step: string) => void } = {},
): Promise<string> {
  const plan = steps.map(parse);
  const delay = Math.max(0, opts.stepDelayMs ?? 0);
  // ExhibitFrame watches this attribute to hold its magnifier over the observed element.
  frame.dataset.exhibitObserve = observe;
  for (const [i, step] of plan.entries()) {
    const doc = await documentOf(frame);
    const win = doc.defaultView as Win;
    opts.onStep?.(i, steps[i]);
    if (step.kind === 'click') {
      const el = find(doc, step.arg);
      lastTouched.set(doc, el);
      click(win, el);
      if (delay > 0) pressFor(el, Math.min(260, delay * 0.8));
    } else if (step.kind === 'type') {
      const el = find(doc, step.arg);
      lastTouched.set(doc, el);
      type(win, el, step.text);
      if (delay > 0) pressFor(el, Math.min(400, delay));
    }
    else if (step.kind === 'key') key(win, doc, step.arg);
    else await sleep(Number(step.arg));
    // Always yield a task between steps so framework renders land before the next press, as with real input.
    await sleep(delay);
  }
  await sleep(SETTLE_MS);
  const doc = await documentOf(frame);
  const el = find(doc, observe);
  return (el instanceof (doc.defaultView as Win).HTMLElement ? el.innerText : (el.textContent ?? '')).trim();
}

// Each replay starts from a fresh app, as the court's fresh browser does; the stage's own 'seance:' keys stay.
function clearStorage(frame: HTMLIFrameElement) {
  try {
    const win = frame.contentWindow;
    if (!win || frame.contentDocument?.URL === 'about:blank') return;
    for (const store of [win.localStorage, win.sessionStorage]) {
      for (const k of Object.keys(store)) if (!k.startsWith('seance:')) store.removeItem(k);
    }
  } catch {
    // Cross-origin or storage-blocked frames keep what they have.
  }
}

/** Reloads the exhibit's page, with its storage cleared, and resolves on its load event. */
export function reloadFrame(frame: HTMLIFrameElement): Promise<void> {
  clearStorage(frame);
  const loaded = nextLoad(frame);
  reloading.set(frame, loaded);
  const settle = () => {
    if (reloading.get(frame) === loaded) reloading.delete(frame);
  };
  loaded.then(settle, settle);
  try {
    frame.contentWindow?.location.reload();
  } catch {
    // Cross-origin frames refuse location.reload(), so navigate to the same address instead.
    const { src } = frame;
    frame.src = src;
  }
  return loaded;
}
