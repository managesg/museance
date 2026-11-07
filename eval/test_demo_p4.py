import pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_demo_p4_offline_replay():
    p = subprocess.run([sys.executable, str(ROOT / "eval/demo_p4.py"), "--fast"], capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, p.stdout + p.stderr
    for s in ("seal.py --verify", "OK", "19/20", "20/20", "68/105", "0/105", "35 -> 100", "1000 -> 930",
              "codex", "attack mismatches 68->0", "cases/before_after.json", "cases/todo.case.yml"):
        assert s in p.stdout, s
    assert "matches repairs.jsonl: True" in p.stdout and "False" not in p.stdout
