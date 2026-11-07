import json, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from p4_fixture import run
from seal import seal, verify

ROOT = pathlib.Path(__file__).resolve().parent.parent
REG = ROOT / "eval/regression/app1-fixture.json"
SEAL = ROOT / "eval/seal.py"


def _sealed(tmp_path):
    atk = tmp_path / "attacks.json"
    run(attacks_out=atk, case_out=tmp_path / "case.yml", revival=tmp_path / "none.html")
    out = tmp_path / "commits.json"
    cmd = [sys.executable, str(SEAL), "--app", "app1", "--regression", str(REG), "--attacks", str(atk), "--out", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return cmd, atk, out


def test_pipeline_runs_without_revival(tmp_path, capsys):
    res = run(attacks_out=tmp_path / "a.json", case_out=tmp_path / "case.yml", revival=tmp_path / "none.html")
    assert res["attacks"] == len(json.loads((tmp_path / "a.json").read_text())) > 0
    assert res["regression"].startswith("skipped")
    assert "credibility_end" in res and (tmp_path / "case.yml").read_text().startswith("app:")
    assert "regression:    skipped" in capsys.readouterr().out


def test_seal_verify_passes(tmp_path):
    cmd, _, out = _sealed(tmp_path)
    assert subprocess.run(cmd + ["--verify"], capture_output=True).returncode == 0
    s = json.loads(out.read_text())
    assert {"app", "created_utc", "regression_sha256", "attacks", "attacks_sha256"} <= s.keys()


def test_tampered_attack_fails_verify(tmp_path):
    cmd, atk, _ = _sealed(tmp_path)
    rows = json.loads(atk.read_text())
    rows[0]["steps"] = rows[0]["steps"] + ["click:#k7"]
    atk.write_text(json.dumps(rows))
    r = subprocess.run(cmd + ["--verify"], capture_output=True, text=True)
    assert r.returncode != 0 and "MISMATCH" in r.stdout


def test_tampered_regression_fails_verify():
    reg = json.loads(REG.read_text())
    sealed = seal("app1", reg, [])
    reg["good"][0]["expect"] = "X"
    assert verify(sealed, reg, [])


def test_default_run_leaves_cases_untouched(capsys):
    tracked = ROOT / "cases/app1-fixture.case.yml"
    before = tracked.read_bytes()
    run(attacks_out=ROOT / "runs/app1/attacks.json", revival=ROOT / "runs/none.html")
    assert tracked.read_bytes() == before
    assert "runs" in capsys.readouterr().out.split("case file:")[1]
    assert (ROOT / "runs/app1/app1-fixture.case.yml").is_file()
