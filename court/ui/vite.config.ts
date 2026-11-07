/// <reference types="vitest/config" />
import { existsSync } from 'node:fs'
import { readFile, realpath, stat } from 'node:fs/promises'
import { extname, join, resolve, sep } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig, type Connect, type Plugin } from 'vite'

const REPO_ROOT = resolve(import.meta.dirname, '../..')

const TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
}

// /exhibits/<app>/<side>/* serves each case's builds same-origin, so the stage can drive them from the iframes.
const EXHIBITS: Record<string, Record<string, string>> = {
  app1: { original: 'fixtures/app1', revival: 'revive/out/app1' },
  todo: { original: 'apps/todo/original', revival: 'revive/out/todo' },
  '2048': { original: 'apps/2048/original', revival: 'revive/out/2048' },
}

const serveExhibits: Connect.NextHandleFunction = async (req, res) => {
  try {
    const { pathname, search } = new URL(req.url ?? '/', 'http://stage')
    const [, app, side, ...rest] = pathname.split('/')
    const dir = Object.hasOwn(EXHIBITS, app) && Object.hasOwn(EXHIBITS[app], side) ? EXHIBITS[app][side] : null
    if (!dir) throw new Error('unknown exhibit')
    const root = await realpath(join(REPO_ROOT, dir))
    // realpath before the prefix check, so neither ../ nor a symlink reaches outside the exhibit.
    const within = async (path: string) => {
      const real = await realpath(path)
      if (real !== root && !real.startsWith(root + sep)) throw new Error('outside the exhibit')
      return real
    }
    let file = await within(join(root, decodeURIComponent(rest.join('/'))))
    if ((await stat(file)).isDirectory()) {
      // The page's relative asset URLs only resolve under a trailing slash.
      const asked = new URL(req.originalUrl ?? '/', 'http://stage').pathname
      if (!asked.endsWith('/')) {
        res.writeHead(301, { Location: `${asked}/${search}` }).end()
        return
      }
      file = await within(join(file, 'index.html'))
    }
    const body = await readFile(file)
    res.writeHead(200, {
      'Content-Type': TYPES[extname(file).toLowerCase()] ?? 'application/octet-stream',
      'Cache-Control': 'no-cache',
    })
    res.end(body)
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Not found')
  }
}

function exhibits(): Plugin {
  return {
    name: 'seance-exhibits',
    configureServer(server) {
      for (const [app, sides] of Object.entries(EXHIBITS))
        for (const [side, dir] of Object.entries(sides))
          if (!existsSync(join(REPO_ROOT, dir))) server.config.logger.warn(`exhibits/${app}/${side}: ${dir} does not exist, so that frame will 404`)
      server.middlewares.use('/exhibits', serveExhibits)
    },
    configurePreviewServer(server) {
      server.middlewares.use('/exhibits', serveExhibits)
    },
  }
}

export default defineConfig({
  plugins: [react(), exhibits()],
  server: {
    // The fixture bundle imports JSON from the repo's fixtures/ folder, outside this Vite root.
    fs: { allow: [REPO_ROOT] },
    // The feed binds 127.0.0.1 only, so skip localhost's IPv6 answer.
    proxy: { '/api': 'http://127.0.0.1:8787' },
  },
  test: { environment: 'node' },
})
