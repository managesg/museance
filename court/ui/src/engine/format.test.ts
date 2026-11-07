import { describe, expect, it } from 'vitest';
import { prettyOutput } from './format';

describe('prettyOutput', () => {
  it('turns court failure text into words and leaves real output alone', () => {
    expect(prettyOutput('ERROR:observe #todo li: TimeoutError')).toBe('no #todo li on the page');
    expect(prettyOutput('ERROR:observe #todo li:nth-child(2): TimeoutError')).toBe('no #todo li:nth-child(2) on the page');
    expect(prettyOutput('ERROR:step 3 click:#add: TimeoutError')).toBe('step 3 failed');
    expect(prettyOutput('Buy milk')).toBe('Buy milk');
    expect(prettyOutput('')).toBe('');
  });
});
