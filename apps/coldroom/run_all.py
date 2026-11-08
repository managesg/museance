"""Start the whole cold-room backend in one terminal: original :8101, patched :8102, court :8103.

python apps/coldroom/run_all.py        (Ctrl+C to stop)
"""
import pathlib
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from apps.coldroom.controller import make_server as controller  # noqa: E402
from court.coldroom import make_server as court  # noqa: E402

servers = [controller(8101, False), controller(8102, True),
           court(8103, out_dir=str(ROOT / "runs" / "coldroom"))]
for s in servers:
    threading.Thread(target=s.serve_forever, daemon=True).start()
print("ORIGINAL  http://127.0.0.1:8101/state  (legacy, no auth)")
print("PATCHED   http://127.0.0.1:8102/state  (PIN + limits)")
print("COURT     POST http://127.0.0.1:8103/run")
try:
    threading.Event().wait()
except KeyboardInterrupt:
    for s in servers:
        s.shutdown()
