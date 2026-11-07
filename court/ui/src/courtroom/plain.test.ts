import { expect, it } from 'vitest';
import { pct, plainClaim } from './plain';

it('says claims without CSS selectors', () => {
  expect(plainClaim("Typing 'Buy milk' into #item and clicking #add creates an item")).toBe("Typing 'Buy milk' into “item” and clicking “add” creates an item");
  expect(plainClaim('New items appear at the top of #todo li after adding')).toBe('New items appear at the top of “todo” after adding');
  expect(plainClaim('Clicking the .complete control (#add)')).toBe('Clicking the “complete” control (“add”)');
  expect(plainClaim('divide: 1 / 8 rounds to 0.13')).toBe('divide: 1 / 8 rounds to 0.13');
});

it('turns scores into percentages', () => {
  expect(pct(0.89)).toBe('89%');
  expect(pct(89)).toBe('89%');
  expect(pct(undefined)).toBeNull();
});
