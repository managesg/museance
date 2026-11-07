export interface AppEntry { id: string; name: string; license?: string; source?: string; hasRun: boolean; fidelity: number | null }

// Shown when the feed is down, so the picker still offers the two apps the team has run.
const FALLBACK: AppEntry[] = [
  { id: 'todo', name: 'todo (themaxsandelin)', license: 'MIT', hasRun: true, fidelity: null },
  { id: 'app1', name: 'fixture-calc', license: 'MIT', hasRun: false, fidelity: null },
];

/** The app registry (fixtures/apps.json) through server/feed.ts GET /api/apps; the fallback when that fails. */
export async function fetchApps(): Promise<AppEntry[]> {
  try {
    const res = await fetch('/api/apps');
    const body: unknown = res.ok ? await res.json() : null;
    if (Array.isArray(body) && body.every((a) => typeof a?.id === 'string' && typeof a?.name === 'string')) return body as AppEntry[];
  } catch {
    // fall through to the fallback
  }
  return FALLBACK;
}
