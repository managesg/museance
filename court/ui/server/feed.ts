// Stage feed: streams one CaseBundle per app as server-sent events, read from runs/<app>/ files or MongoDB Atlas,
// and relays the judge's bench input to the court. Run from court/ui with `node server/feed.ts` (Node 24 strips the types).
// Env, from the shell first and then the repo .env: PORT (8787), COURT_URL (http://127.0.0.1:8798), MONGODB_URI, MONGODB_DB (default: the URI's database).
import { createHash } from 'node:crypto';
import { existsSync, watch } from 'node:fs';
import type { FSWatcher } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { join, resolve } from 'node:path';
import type { MongoClient } from 'mongodb';
import type { CaseBundle } from '../src/contracts.ts';
import { buildsFor } from '../src/feed/builds.ts';
import { fromLedger, jsonLines, parseCase, parseRepairs } from '../src/feed/parse.ts';

const ROOT = resolve(import.meta.dirname, '../../..');
const ENV_FILE = join(ROOT, '.env');
if (existsSync(ENV_FILE)) process.loadEnvFile(ENV_FILE);

const PORT = Number(process.env.PORT) || 8787;
const COURT_URL = process.env.COURT_URL?.replace(/\/+$/, '') || 'http://127.0.0.1:8798';
const STAGE_ORIGIN = 'http://127.0.0.1:5175'; // where the court loads the exhibits when the request names no usable Host
const HOST_RE = /^([a-z0-9.-]+|\[[0-9a-f:]+\])(:\d{1,5})?$/i;
const MONGODB_URI = process.env.MONGODB_URI || undefined;
const RUNS = join(ROOT, 'runs');
const POLL_MS = 1500;
const SETTLE_MS = 100; // let a burst of file writes land before reading
// A real event, not a comment: behind Vite's proxy a dead feed leaves the stream open, so the stage watches for silence.
const PING_MS = 5000;
const BENCH_TIMEOUT_MS = 70_000; // the court itself gives up at 60 s
const BODY_LIMIT = 64 * 1024;
const APP_RE = /^[a-z0-9-]+$/;

type Source = 'runs' | 'atlas';
// Every CaseBundle key, values unchecked: the stage validates each bundle (src/feed/validate.ts).
type Wire = Record<keyof CaseBundle, unknown>;

// Driver errors can echo a connection string, so credentials never reach the log or the stage.
const scrub = (msg: string) =>
  (MONGODB_URI ? msg.replaceAll(MONGODB_URI, '<MONGODB_URI>') : msg).replace(/\/\/[^\s/@]+@/g, '//***@');
const errText = (e: unknown) => {
  const cause = e instanceof Error && e.cause instanceof Error && !e.message.includes(e.cause.message) ? `: ${e.cause.message}` : '';
  const msg = e instanceof Error ? e.message + cause : String(e);
  return scrub(msg).replace(/\s+/g, ' ');
};
const rel = (path: string) => path.slice(ROOT.length + 1);

async function readText(path: string): Promise<string | null> {
  try {
    return await readFile(path, 'utf8');
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === 'ENOENT') return null;
    throw e;
  }
}

async function readJson(path: string): Promise<unknown> {
  const text = await readText(path);
  if (text === null) return null;
  try {
    return JSON.parse(text);
  } catch (e) {
    throw new Error(`${rel(path)}: ${errText(e)}`);
  }
}

async function readCase(...paths: string[]) {
  for (const path of paths) {
    const text = await readText(path);
    if (text === null) continue;
    try {
      return parseCase(text);
    } catch (e) {
      throw new Error(`${rel(path)}: ${errText(e)}`);
    }
  }
  return null;
}

// One judging of the claims and attacks: P1's verdicts and locks, or while live, the latest of each in the ledger.
async function judged(dir: string, ...caseFallback: string[]) {
  const [verdicts, locks, ledgerText, caseFile] = await Promise.all([
    readJson(join(dir, 'verdicts.json')), readJson(join(dir, 'locks.json')), readText(join(dir, 'ledger.jsonl')),
    readCase(join(dir, 'case.yml'), ...caseFallback),
  ]);
  const ledger = jsonLines(ledgerText); // a half-written last line is skipped until it lands
  const live = verdicts === null || locks === null ? fromLedger(ledger) : null;
  return { verdicts: verdicts ?? live?.verdicts, locks: locks ?? live?.locks, caseFile, ledger, found: ledgerText !== null || verdicts !== null };
}

async function appLabel(app: string): Promise<string> {
  const apps = await readJson(join(ROOT, 'fixtures', 'apps.json')).catch(() => null);
  const name: unknown = Array.isArray(apps) ? apps.find((a) => a?.id === app)?.name : undefined;
  return typeof name === 'string' ? name : app;
}

async function fromRuns(app: string): Promise<Wire> {
  const dir = join(RUNS, app);
  const file = (name: string) => readJson(join(dir, name));
  const [evidence, sheet, claims, attacks, now, after, repairs, label] = await Promise.all([
    file('evidence.json'), file('sheet.json'), file('claims.json'), file('attacks.json'),
    judged(dir, join(ROOT, 'cases', `${app}.case.yml`)), judged(join(dir, 'after')),
    readText(join(dir, 'repairs.jsonl')).then((t) => t ?? readText(join(ROOT, 'cases', app, 'repairs.jsonl'))),
    appLabel(app),
  ]);
  return {
    app, appLabel: label, source: 'runs', evidence: evidence ?? [], sheet, claims: claims ?? [], attacks: attacks ?? [],
    verdicts: now.verdicts, locks: now.locks, ledger: now.ledger, caseFile: now.caseFile,
    repairs: parseRepairs(repairs), builds: buildsFor(app),
    after: after.found ? { verdicts: after.verdicts, locks: after.locks, caseFile: after.caseFile } : null,
  };
}

let mongo: Promise<MongoClient> | null = null;

async function fromAtlas(app: string): Promise<Wire> {
  if (!MONGODB_URI) throw new Error('MONGODB_URI is not set (shell or repo .env)');
  const uri = MONGODB_URI;
  const connecting = (mongo ??= import('mongodb').then(({ MongoClient }) =>
    new MongoClient(uri, { serverSelectionTimeoutMS: 5000 }).connect()));
  const client = await connecting.catch((e: unknown) => {
    if (mongo === connecting) mongo = null; // reconnect on the next poll
    throw e;
  });
  const db = client.db(process.env.MONGODB_DB || undefined);
  const all = (name: string, sort: Record<string, 1 | -1> = { _id: 1 }) =>
    db.collection(name).find({ app }, { projection: { _id: 0 }, sort }).toArray();
  const latest = (name: string) => db.collection(name).findOne({ app }, { projection: { _id: 0 }, sort: { _id: -1 } });
  const [evidence, sheet, claims, attacks, verdicts, locks, ledger, caseFile, label] = await Promise.all([
    all('evidence'), latest('behavior_sheet'), all('claims'), all('attacks'), all('verdicts'), all('locks'),
    all('ledger', { seq: 1 }), latest('cases'), appLabel(app),
  ]);
  return {
    app, appLabel: label, source: 'atlas', evidence, sheet, claims, attacks, verdicts, locks, ledger, caseFile, repairs: [],
    builds: buildsFor(app), after: null,
  };
}

function stream(res: ServerResponse, app: string, source: Source) {
  res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache', connection: 'keep-alive' });
  res.write(`retry: ${POLL_MS}\n\n`);
  let closed = false;
  let running = false;
  let again = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let due = Infinity;
  let watcher: FSWatcher | null = null;
  let sentHash = '';
  let lastProblem = '';
  let failures = 0;

  // Refresh at the earliest time anyone asked for, so a steady stream of file events never postpones it.
  const schedule = (ms: number) => {
    if (closed || (timer && Date.now() + ms >= due)) return;
    clearTimeout(timer);
    due = Date.now() + ms;
    timer = setTimeout(refresh, ms);
  };

  const watchRuns = () => {
    if (source !== 'runs' || watcher) return;
    try {
      watcher = watch(join(RUNS, app), () => schedule(SETTLE_MS));
      watcher.on('error', () => {
        watcher?.close();
        watcher = null;
      });
    } catch {
      // runs/<app> does not exist yet; the poll keeps looking
    }
  };

  async function refresh() {
    timer = undefined;
    due = Infinity;
    if (running) {
      again = true;
      return;
    }
    running = true;
    try {
      watchRuns();
      const json = JSON.stringify(source === 'runs' ? await fromRuns(app) : await fromAtlas(app));
      const hash = createHash('sha256').update(json).digest('hex');
      failures = 0;
      lastProblem = '';
      if (hash !== sentHash && !closed) {
        sentHash = hash;
        res.write(`event: bundle\ndata: ${json}\n\n`);
      }
    } catch (e) {
      const msg = errText(e);
      // One failed read can be a file caught mid-write, so only a failure that repeats is reported.
      if (++failures >= 2 && msg !== lastProblem && !closed) {
        lastProblem = msg;
        sentHash = ''; // resend once it loads again, so the stage leaves its error state
        res.write(`event: problem\ndata: ${msg}\n\n`);
        console.warn(`feed ${source}/${app}: ${msg}`);
      }
    } finally {
      running = false;
    }
    schedule(again ? 0 : POLL_MS);
    again = false;
  }

  const ping = setInterval(() => res.write('event: ping\ndata: ok\n\n'), PING_MS);
  res.on('close', () => {
    closed = true;
    clearTimeout(timer);
    clearInterval(ping);
    watcher?.close();
  });
  void refresh();
}

// The registry for the stage's app picker (src/feed/apps.ts AppEntry): a broken case file reads as no fidelity, not an error.
async function apps() {
  const list = await readJson(join(ROOT, 'fixtures', 'apps.json'));
  if (!Array.isArray(list)) return [];
  return Promise.all(list.filter((a) => typeof a?.id === 'string' && APP_RE.test(a.id)).map(async (a) => {
    const caseFile = await readCase(join(RUNS, a.id, 'case.yml'), join(ROOT, 'cases', `${a.id}.case.yml`)).catch(() => null);
    return {
      id: a.id, name: typeof a.name === 'string' ? a.name : a.id,
      license: typeof a.license === 'string' ? a.license : undefined, source: typeof a.source === 'string' ? a.source : undefined,
      hasRun: existsSync(join(RUNS, a.id, 'claims.json')), fidelity: caseFile?.fidelity ?? null,
    };
  }));
}

function reply(res: ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { 'content-type': 'application/json' }).end(JSON.stringify(body));
}

async function bench(req: IncomingMessage, res: ServerResponse) {
  // Requiring JSON makes browsers preflight cross-site posts, and this server never approves a preflight.
  if (!/^application\/json\b/i.test(req.headers['content-type'] ?? '')) {
    return reply(res, 415, { error: 'send JSON with content-type: application/json' });
  }
  req.setEncoding('utf8');
  let raw = '';
  for await (const chunk of req) {
    raw += chunk;
    if (raw.length > BODY_LIMIT) return reply(res, 413, { error: 'body too large' });
  }
  let body: unknown;
  try {
    body = JSON.parse(raw);
  } catch {
    return reply(res, 400, { error: 'body must be JSON' });
  }
  const { app, steps, observe, original, revival } = (typeof body === 'object' && body !== null ? body : {}) as Record<string, unknown>;
  if (typeof app !== 'string' || !APP_RE.test(app)) return reply(res, 400, { error: 'app must match ^[a-z0-9-]+$' });
  if (!Array.isArray(steps) || steps.length > 50 || !steps.every((s) => typeof s === 'string' && s.length <= 200)) {
    return reply(res, 400, { error: 'steps must be a list of at most 50 strings of at most 200 characters' });
  }
  if (typeof observe !== 'string' || observe.length > 200) {
    return reply(res, 400, { error: 'observe must be a string of at most 200 characters' });
  }
  // The court loads these builds, so they may only name the stage's own exhibits, never another site.
  // Vite's proxy rewrites Host to this feed's own port, so trust the browser's Origin first (local http only).
  const LOCAL_ORIGIN = /^http:\/\/(127\.0\.0\.1|localhost):\d{2,5}$/;
  const sent = typeof req.headers.origin === 'string' && LOCAL_ORIGIN.test(req.headers.origin) ? req.headers.origin : null;
  const host = req.headers.host ?? '';
  const viaHost = HOST_RE.test(host) && !host.endsWith(`:${PORT}`) ? `http://${host}` : null;
  const origin = sent ?? process.env.STAGE_ORIGIN ?? viaHost ?? STAGE_ORIGIN;
  const exhibit = (p: unknown) => {
    if (typeof p !== 'string' || p.length > 200 || !p.startsWith('/exhibits/')) return null;
    const url = new URL(p, origin);
    return url.origin === origin && url.pathname.startsWith('/exhibits/') ? url.href : null;
  };
  const originalUrl = exhibit(original);
  const revivalUrl = exhibit(revival);
  if (!originalUrl || !revivalUrl) {
    return reply(res, 400, { error: "original and revival must be same-origin paths starting with '/exhibits/'" });
  }
  let court: Response;
  try {
    court = await fetch(`${COURT_URL}/${app}/bench`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ app, steps, observe, original: originalUrl, revival: revivalUrl }),
      signal: AbortSignal.timeout(BENCH_TIMEOUT_MS),
    });
  } catch (e) {
    // Unreachable court: 501, so the stage drives both exhibits itself instead.
    const timeout = e instanceof Error && e.name === 'TimeoutError';
    return reply(res, timeout ? 504 : 501, { error: `court: ${errText(e)}` });
  }
  try {
    reply(res, court.status, await court.json());
  } catch (e) {
    reply(res, 502, { error: `court: ${errText(e)}` });
  }
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url ?? '/', 'http://localhost');
    const route = `${req.method} ${url.pathname}`;
    if (route === 'GET /api/health') {
      return reply(res, 200, { ok: true, atlas: Boolean(MONGODB_URI), court: Boolean(COURT_URL) });
    }
    if (route === 'GET /api/feed') {
      const app = url.searchParams.get('app') ?? 'app1';
      const source = url.searchParams.get('source') ?? 'runs';
      if (!APP_RE.test(app)) return reply(res, 400, { error: 'app must match ^[a-z0-9-]+$' });
      if (source !== 'runs' && source !== 'atlas') return reply(res, 400, { error: 'source must be runs or atlas' });
      return stream(res, app, source);
    }
    if (route === 'POST /api/bench') return await bench(req, res);
    if (route === 'GET /api/apps') return reply(res, 200, await apps());
    reply(res, 404, { error: 'not found' });
  } catch (e) {
    console.error('feed:', errText(e));
    if (!res.headersSent) reply(res, 500, { error: 'internal error' });
    else res.destroy();
  }
});

server.on('error', (e: NodeJS.ErrnoException) => {
  console.error(e.code === 'EADDRINUSE'
    ? `feed: port ${PORT} is taken (P1's court/feed.py also defaults to 8787); set PORT`
    : `feed: ${errText(e)}`);
  process.exit(1);
});

server.listen(PORT, '127.0.0.1', () => {
  const court = COURT_URL ? (URL.parse(COURT_URL)?.origin ?? 'COURT_URL is not a URL') : 'off (no COURT_URL)';
  console.log(`feed on http://127.0.0.1:${PORT} | files ${rel(RUNS)}/<app>/ | atlas ${MONGODB_URI ? 'configured' : 'off (no MONGODB_URI)'} | court ${court}`);
});
