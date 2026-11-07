import { describe, expect, it } from 'vitest';
import { labelFrom, stepText } from './steps';

const label = (sel: string) => ({ '#item': 'Item', '#add': 'Add' })[sel] ?? null;

describe('stepText', () => {
  it('reads type, click, key and wait steps with labels', () => {
    expect(stepText('type:#item:Buy milk', label)).toBe('type "Buy milk" into the Item field (#item)');
    expect(stepText('click:#add', label)).toBe('click "Add" (#add)');
    expect(stepText('key:Enter', label)).toBe('press Enter');
    expect(stepText('wait:500', label)).toBe('wait 0.5 s');
  });
  it('falls back to the selector without a label', () => {
    expect(stepText('type:#item:Buy milk')).toBe('type "Buy milk" into #item');
    expect(stepText('click:#add')).toBe('click #add');
    expect(stepText('type:#other:x', label)).toBe('type "x" into #other');
    expect(stepText('click:#todo li:nth-child(2)', label)).toBe('click #todo li:nth-child(2)');
  });
  it('keeps unknown steps raw', () => {
    expect(stepText('hover:#x')).toBe('hover:#x');
    expect(stepText('')).toBe('');
  });
});

describe('labelFrom', () => {
  it('returns null for a null doc and never throws', () => {
    expect(labelFrom(null)('#item')).toBeNull();
    expect(labelFrom(null)('::bad[')).toBeNull();
  });
  it('falls back to title, then value, then the id as words', () => {
    const doc = (id: string, attrs: Record<string, string> = {}, text = '') =>
      ({ querySelector: () => ({ id, innerText: text, textContent: text, getAttribute: (k: string) => attrs[k] ?? null }) }) as unknown as Document;
    expect(labelFrom(doc('add', { title: 'Add item', value: 'Go' }))('#add')).toBe('Add item');
    expect(labelFrom(doc('add', { value: 'Go' }))('#add')).toBe('Go');
    expect(labelFrom(doc('add'))('#add')).toBe('Add');
    expect(labelFrom(doc('todo-list'))('#todo-list')).toBe('Todo list');
    expect(labelFrom(doc('newTodo'))('#newTodo')).toBe('New todo');
    expect(labelFrom(doc('add', { title: 'Add item' }, ' Save '))('#add')).toBe('Save');
    expect(labelFrom(doc(''))('.x')).toBeNull();
  });
});
