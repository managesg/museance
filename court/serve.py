"""Serve a local folder on a free localhost port for the length of a `with` block."""
from __future__ import annotations

import contextlib
import functools
import http.server
import threading


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@contextlib.contextmanager
def folder(path: str):
    handler = functools.partial(_Quiet, directory=str(path))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    finally:
        httpd.shutdown()
        httpd.server_close()


@contextlib.contextmanager
def maybe(path: str | None):
    if not path:
        yield None
    else:
        with folder(path) as url:
            yield url
