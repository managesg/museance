import type { Builds } from '../contracts.ts';

// The one table of exhibit builds the stage frames. Paths are same-origin, served by vite.config.ts.
// No runtime imports: server/feed.ts loads this file under plain Node.
export const BUILDS: Record<string, Builds> = {
  app1: { original: '/exhibits/app1/original/', revival: '/exhibits/app1/revival/', revivalAfter: null, scale: 1.6 },
  todo: {
    original: '/exhibits/todo/original/', revival: '/exhibits/todo/revival/index.v1.html',
    revivalAfter: '/exhibits/todo/revival/index.v2.html', scale: 1,
  },
};

export const FIXTURE_BUILDS: Builds = {
  original: '/exhibits/app1/original/', revival: '/revival-fixture/index.html',
  revivalAfter: '/revival-fixture-repaired/index.html', scale: 1.7,
};

/** The table entry, or the same layout guessed for an app the table does not list yet. */
export const buildsFor = (app: string): Builds =>
  BUILDS[app] ?? { original: `/exhibits/${app}/original/`, revival: `/exhibits/${app}/revival/`, revivalAfter: null, scale: 1 };
