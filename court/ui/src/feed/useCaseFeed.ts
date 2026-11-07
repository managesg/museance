import { useEffect, useState } from 'react';
import type { CaseBundle } from '../contracts';
import { loadFixtureBundle } from '../fixtures';
import { bundleProblem, toBundle } from './validate';

type Source = CaseBundle['source'];
type Status = 'fixture' | 'connecting' | 'live' | 'error';
interface Feed { bundle: CaseBundle | null; source: Source; status: Status; error?: string }

const REOPEN_MS = 3000;
// server/feed.ts pings every 5 s; a proxy can hold a dead feed's stream open and silent, so silence means reconnect.
const QUIET_MS = 12_000;

function fromLocation(): { source: Source; app: string } {
  const q = new URLSearchParams(location.search);
  const s = q.get('source');
  return { source: s === 'runs' || s === 'atlas' ? s : 'fixture', app: q.get('app') || 'app1' };
}

/** The case on stage: the repo fixture by default, or ?source=runs|atlas&app=<id> streamed from server/feed.ts. */
export function useCaseFeed(): Feed {
  const [{ source, app }] = useState(fromLocation);
  const [feed, setFeed] = useState<Feed>(() =>
    source === 'fixture'
      ? { bundle: loadFixtureBundle(), source, status: 'fixture' }
      : { bundle: null, source, status: 'connecting' });

  useEffect(() => {
    if (source === 'fixture') return;
    const url = `/api/feed?${new URLSearchParams({ app, source })}`;
    // Problems keep the last good bundle on stage and only change the status.
    const trouble = (error: string, status: Status = 'error') => setFeed((f) => ({ ...f, status, error }));
    let es: EventSource | null = null;
    let reopen: ReturnType<typeof setTimeout> | undefined;
    let quiet: ReturnType<typeof setTimeout> | undefined;

    const open = () => {
      const src = new EventSource(url);
      es = src;
      const alive = () => {
        clearTimeout(quiet);
        quiet = setTimeout(() => {
          src.close();
          trouble('feed went quiet, reconnecting', 'connecting');
          open();
        }, QUIET_MS);
      };
      alive();
      src.addEventListener('ping', alive);
      src.addEventListener('bundle', (e) => {
        alive();
        let data: unknown = null;
        try { data = JSON.parse(e.data); } catch { /* reported as not an object below */ }
        const bundle = toBundle(data, source);
        if (bundle) setFeed({ bundle, source, status: 'live' });
        else trouble(`bad bundle from the feed (${bundleProblem(data)})`);
      });
      src.addEventListener('problem', (e) => {
        alive();
        trouble(`feed: ${e.data}`);
      });
      src.onerror = () => {
        // CLOSED: the browser gave up for good (no feed server, or /api not proxied to it), so reopen by hand.
        if (src.readyState === EventSource.CLOSED) {
          clearTimeout(quiet);
          trouble('feed unavailable: is server/feed.ts running with /api proxied to it? Retrying.');
          reopen = setTimeout(open, REOPEN_MS);
        } else {
          trouble('feed connection lost, reconnecting', 'connecting');
        }
      };
    };

    open();
    return () => {
      clearTimeout(reopen);
      clearTimeout(quiet);
      es?.close();
    };
  }, [source, app]);

  return feed;
}
