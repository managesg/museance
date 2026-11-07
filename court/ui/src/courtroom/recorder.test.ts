import { describe, expect, it } from 'vitest';
import { addRec, plainOutput, record, selectorOf, type Rec } from './recorder';

// A tiny element tree: enough of the DOM for selectorOf (id, tagName, classList, parentElement, children).
type El = { id: string; tagName: string; classList: string[]; parentElement: El | null; children: El[] };
function el(tag: string, id = '', cls: string[] = [], kids: El[] = []): El {
  const e: El = { id, tagName: tag.toUpperCase(), classList: cls, parentElement: null, children: kids };
  kids.forEach((k) => (k.parentElement = e));
  return e;
}
const sel = (e: El | null) => selectorOf(e as unknown as Element);

describe('addRec', () => {
  const run = (...events: Rec[]) => events.reduce<string[]>(addRec, []);
  it('maps a click on an element with an id to click:#id', () => {
    expect(run({ kind: 'click', sel: '#add' })).toEqual(['click:#add']);
  });
  it('keeps one type step per field with its latest value', () => {
    expect(run(
      { kind: 'input', sel: '#item', value: 'B' },
      { kind: 'input', sel: '#item', value: 'Bu' },
      { kind: 'input', sel: '#item', value: 'Buy milk' },
      { kind: 'click', sel: '#add' },
    )).toEqual(['type:#item:Buy milk', 'click:#add']);
  });
  it('starts a new type step after another action, so typing twice adds twice', () => {
    expect(run(
      { kind: 'input', sel: '#item', value: 'a' },
      { kind: 'key', key: 'Enter' },
      { kind: 'input', sel: '#item', value: 'b' },
    )).toEqual(['type:#item:a', 'key:Enter', 'type:#item:b']);
  });
  it('keeps text with colons whole, as the step grammar allows', () => {
    expect(run({ kind: 'input', sel: '#item', value: 'at 9:30' })).toEqual(['type:#item:at 9:30']);
  });
  it('records Enter, Escape, Tab and arrows, but not printable keys', () => {
    expect(run({ kind: 'key', key: 'a' }, { kind: 'key', key: 'Shift' }, { kind: 'key', key: 'Enter' }, { kind: 'key', key: 'ArrowLeft' }))
      .toEqual(['key:Enter', 'key:ArrowLeft']);
  });
  it('drops events on elements it cannot name', () => {
    expect(run({ kind: 'click', sel: null }, { kind: 'input', sel: null, value: 'x' })).toEqual([]);
  });
});

describe('selectorOf', () => {
  it('uses the id when there is one', () => {
    expect(sel(el('button', 'add'))).toBe('#add');
  });
  it('names a control without an id by its ancestor with an id and its row', () => {
    const done = el('button', '', ['complete']);
    const row2 = el('li', '', [], [el('div', '', ['buttons'], [el('button', '', ['remove']), done])]);
    el('ul', 'todo', [], [el('li'), row2]);
    expect(sel(done)).toBe('#todo > li:nth-child(2) .complete');
    expect(sel(row2)).toBe('#todo > li:nth-child(2)');
  });
  it('is null with no id anywhere above', () => {
    expect(sel(el('div', '', [], [el('span')]).children[0])).toBeNull();
    expect(sel(null)).toBeNull();
  });
});

describe('record', () => {
  // A fake document that keeps its listeners, so a test can fire events at it.
  function fakeDoc() {
    const on: Record<string, (e: unknown) => void> = {};
    return {
      doc: { addEventListener: (t: string, f: (e: unknown) => void) => (on[t] = f), removeEventListener: (t: string) => delete on[t] } as unknown as Document,
      fire: (t: string, e: unknown) => on[t]?.(e),
      count: () => Object.keys(on).length,
    };
  }
  const target = (tag: string, id: string, extra: Record<string, unknown> = {}) =>
    ({ ...el(tag, id), closest: () => null, ...extra });

  it('turns trusted clicks, typing and Enter into steps, and ignores replayed events', () => {
    const { doc, fire, count } = fakeDoc();
    const got: Rec[] = [];
    const stop = record(doc, (e) => got.push(e));
    fire('click', { isTrusted: true, target: target('input', 'item', { type: 'text' }) }); // focusing a field is not a step
    fire('input', { isTrusted: true, target: target('input', 'item', { value: 'Buy milk' }) });
    fire('click', { isTrusted: true, target: target('button', 'add') });
    fire('click', { isTrusted: false, target: target('button', 'add') }); // a replay of the court's own steps
    fire('keydown', { isTrusted: true, key: 'Enter' });
    expect(got.reduce<string[]>(addRec, [])).toEqual(['type:#item:Buy milk', 'click:#add', 'key:Enter']);
    stop();
    expect(count()).toBe(0);
  });
});

describe('plainOutput', () => {
  it('says what a court ERROR means in words', () => {
    expect(plainOutput('ERROR:observe #todo li: TimeoutError')).toBe('nothing to read: it has no #todo li');
    expect(plainOutput('ERROR:missing selector: #k7')).toBe('it has no #k7');
    expect(plainOutput('ERROR:step 1 click:#k7: TimeoutError')).toBe('could not do step 2 (click:#k7)');
    expect(plainOutput('ERROR:load TimeoutError')).toBe('it did not load');
  });
  it('keeps ordinary output, joining lines', () => {
    expect(plainOutput('Walk dog\nBuy milk')).toBe('Walk dog · Buy milk');
    expect(plainOutput('')).toBe('');
    expect(plainOutput(null)).toBe('');
  });
});
