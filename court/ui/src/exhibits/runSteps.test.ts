import { expect, it } from 'vitest';
import { parse } from './runSteps';

it('parses the seeding steps the way court/steps.py does', () => {
  expect(parse('reload')).toEqual({ kind: 'reload', arg: '' });
  expect(parse('storage:bestScore=0')).toEqual({ kind: 'storage', arg: 'bestScore', text: '0' });
  expect(parse('storage:gameState={"a":"b=c"}')).toEqual({ kind: 'storage', arg: 'gameState', text: '{"a":"b=c"}' });
  expect(() => parse('storage:=1')).toThrow();
  expect(() => parse('storage:noEquals')).toThrow();
});
