import type { Verdict } from '../contracts';
import { isVerdict } from './validate';

/**
 * Ask the court, through server/feed.ts, to rule on the judge's ad hoc input.
 * Null when no court is wired (501) or anything else fails, so the bench can fall back instead of hanging.
 */
export async function postBench(app: string, steps: string[], observe: string): Promise<Verdict | null> {
  try {
    const res = await fetch('/api/bench', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ app, steps, observe }),
    });
    const body: unknown = await res.json().catch(() => null);
    if (res.ok && isVerdict(body)) return body;
    if (res.status !== 501) console.warn('bench: no verdict', res.status, body);
    return null;
  } catch (e) {
    console.warn('bench: network error', e);
    return null;
  }
}
