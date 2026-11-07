// The pastry gallery: deterministic bots that bet on every claim, so the same case always plays the same.
import type { Claim, Verdict } from '../contracts';
import type { LeaderRow, Pastry } from './types';

export const STAKE = 100;
export const BANKROLL = 1000;

export interface Bet { claimId: string; pastry: Pastry; onTrue: boolean; }

type Pick = (claim: Claim, rand: () => number, crowd: boolean[]) => boolean;

// Order matters: the follower reads the bets placed before it on the same claim.
export const BOTS: readonly { name: string; pastry: Pastry; pick: Pick }[] = [
  { name: 'Croissant', pastry: 'croissant', pick: () => true }, // believer
  { name: 'Bagel', pastry: 'bagel', pick: (c) => c.tier !== 'C' && c.tier !== 'D' }, // doubts testimony and silence
  { name: 'Eclair', pastry: 'eclair', pick: (c, rand) => rand() < c.confidence }, // calibrated by confidence
  { name: 'Pretzel', pastry: 'pretzel', pick: (c) => c.confidence < 0.5 }, // contrarian
  { name: 'Canele', pastry: 'canele', pick: (_c, rand) => rand() < 0.5 }, // coin flipper
  {
    name: 'Kouign-amann', pastry: 'kouign', // follower: sides with the crowd, with the medium on a tie
    pick: (c, _rand, crowd) => {
      const yes = crowd.filter(Boolean).length * 2;
      return yes === crowd.length ? c.confidence >= 0.5 : yes > crowd.length;
    },
  },
];

export function mulberry32(seed: number): () => number {
  let a = seed | 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** FNV-1a, so an app name seeds mulberry32. */
export function seedFrom(text: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 0x01000193);
  return h >>> 0;
}

/** Every bot stakes STAKE on every claim, true or false. */
export function placeBets(claims: Claim[], seed: string | number): Bet[] {
  const rand = mulberry32(typeof seed === 'number' ? seed : seedFrom(seed));
  return claims.flatMap((c) => {
    const crowd: boolean[] = [];
    for (const bot of BOTS) crowd.push(bot.pick(c, rand, crowd));
    return BOTS.map((bot, i) => ({ claimId: c.id, pastry: bot.pastry, onTrue: crowd[i] }));
  });
}

export function betTotals(bets: Bet[], claimId: string): { trueCredits: number; falseCredits: number } {
  const mine = bets.filter((b) => b.claimId === claimId);
  const yes = mine.filter((b) => b.onTrue).length;
  return { trueCredits: yes * STAKE, falseCredits: (mine.length - yes) * STAKE };
}

/** Leaderboard after the verdicts that have landed; a flaky or truthless verdict is a push. */
export function settle(bets: Bet[], verdicts: Verdict[]): LeaderRow[] {
  const truth = new Map<string, boolean>();
  for (const v of verdicts) if (v.kind !== 'attack' && !v.flaky && typeof v.claim_true === 'boolean') truth.set(v.ref, v.claim_true);
  return BOTS.map(({ name, pastry }) => {
    let wins = 0;
    let losses = 0;
    for (const b of bets) {
      if (b.pastry !== pastry || !truth.has(b.claimId)) continue;
      if (b.onTrue === truth.get(b.claimId)) wins++;
      else losses++;
    }
    return { name, pastry, credits: BANKROLL + STAKE * (wins - losses), wins, losses };
  }).sort((a, b) => b.credits - a.credits);
}
