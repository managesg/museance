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

// The original exhibit frame loads the dead app from ORIGINAL_DIR, or the fixture calculator.
function originalExhibit(): Plugin {
  const dir = resolve(process.env.ORIGINAL_DIR ?? join(REPO_ROOT, 'fixtures/app1'))
  const serve: Connect.NextHandleFunction = async (req, res) => {
    try {
      const root = await realpath(dir)
      // realpath before the prefix check, so neither ../ nor a symlink reaches outside the exhibit.
      const within = async (path: string) => {
        const real = await realpath(path)
        if (real !== root && !real.startsWith(root + sep)) throw new Error('outside the exhibit')
        return real
      }
      const { pathname, search } = new URL(req.url ?? '/', 'http://stage')
      let file = await within(join(root, decodeURIComponent(pathname)))
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
  return {
    name: 'seance-original-exhibit',
    configureServer(server) {
      if (!existsSync(dir)) server.config.logger.warn(`exhibits/original: ${dir} does not exist, so that frame will 404`)
      server.middlewares.use('/exhibits/original', serve)
    },
    configurePreviewServer(server) {
      server.middlewares.use('/exhibits/original', serve)
    },
  }
}

export default defineConfig({
  plugins: [react(), originalExhibit()],
  server: {
    // The fixture bundle imports JSON from the repo's fixtures/ folder, outside this Vite root.
    fs: { allow: [REPO_ROOT] },
    // The feed binds 127.0.0.1 only, so skip localhost's IPv6 answer.
    proxy: { '/api': 'http://127.0.0.1:8787' },
  },
  test: { environment: 'node' },
})
