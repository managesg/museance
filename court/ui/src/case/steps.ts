// Court step strings ('type:#item:Buy milk') read aloud for a viewer, for any app.

export function stepText(step: string, label?: (sel: string) => string | null): string {
  const name = (sel: string) => label?.(sel) ?? null;
  const type = /^type:([^:]+):(.*)$/s.exec(step);
  if (type) {
    const [, sel, text] = type;
    const l = name(sel);
    return l ? `type "${text}" into the ${l} field (${sel})` : `type "${text}" into ${sel}`;
  }
  if (step.startsWith('click:')) {
    const sel = step.slice(6);
    const l = name(sel);
    return l ? `click "${l}" (${sel})` : `click ${sel}`;
  }
  if (step.startsWith('key:')) return `press ${step.slice(4)}`;
  if (step === 'reload') return 'reload the page';
  const store = /^storage:([^=]+)=(.*)$/s.exec(step);
  if (store) {
    const [, key, value] = store;
    return value.length <= 12 ? `set saved ${words(key).toLowerCase()} to ${value}` : `load a saved ${words(key).toLowerCase()}`;
  }
  const wait = /^wait:(\d+(?:\.\d+)?)$/.exec(step);
  if (wait) return `wait ${Number(wait[1]) / 1000} s`;
  return step;
}

// '#todo-list' -> 'Todo list', 'newTodo' -> 'New todo'.
const words = (id: string) => {
  const w = id.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[-_\s]+/g, ' ').trim().toLowerCase();
  return w && w[0].toUpperCase() + w.slice(1);
};

export function labelFrom(doc: Document | null): (sel: string) => string | null {
  return (sel) => {
    try {
      const el = doc?.querySelector(sel);
      if (!el) return null;
      const text = (el as HTMLElement).innerText ?? el.textContent ?? '';
      const v =
        el.getAttribute('aria-label') || el.getAttribute('placeholder') || text.trim().slice(0, 24) ||
        el.getAttribute('title') || el.getAttribute('value') || words(el.id);
      return v || null;
    } catch {
      return null; // bad selector or a cross-origin frame document
    }
  };
}
