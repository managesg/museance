import { describe, expect, it } from 'vitest';
import { verifyLedger } from '../engine/hash';
import { celsius, EVENTS, hms, ITEMS, MAX_SIM, regs, simSeconds, SUMMARY, writeTaken } from './model';

describe('cold room court model', () => {
  it('parses observe strings and register units', () => {
    expect(regs('hr1=40,coil0=1,coil2=0')).toEqual({ hr1: 40, coil0: 1, coil2: 0 });
    expect(celsius(250)).toBe('25.0');
    expect(simSeconds(['hr:0=100', 'tick:600'])).toBe(600);
    expect(hms(22800)).toBe('6 h 20 min');
    expect(MAX_SIM).toBe(22800);
  });

  it('reads the sample run: controls identical, every attack taken by the legacy build only', () => {
    expect(SUMMARY).toEqual({ controls: 6, identical: 6, locked: 6, attacks: 3, blocked: 3, flaky: 0 });
    const unauth = ITEMS.find((i) => i.id === 'sec-setpoint-unauth')!;
    expect(unauth.text).toBe('Unauthenticated write: setpoint → 25.0 °C');
    expect(writeTaken(unauth, 'original')).toBe(true);
    expect(writeTaken(unauth, 'revival')).toBe(false);
    expect(writeTaken(ITEMS[0], 'original')).toBeNull();
  });

  it('recomputes the ledger chain', async () => {
    expect(EVENTS).toHaveLength(24);
    expect(await verifyLedger(EVENTS)).toBe(true);
    const tampered = EVENTS.map((e, i) => (i === 12 ? { ...e, payload: { ...(e.payload as object), flaky: true } } : e));
    expect(await verifyLedger(tampered)).toBe(false);
  });
});
