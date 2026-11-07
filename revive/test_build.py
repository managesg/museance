"""Offline tests; no coding model is invoked and no original source is opened."""
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from revive.build import build, builder_command, check_selectors, extract_html, make_prompt, run_builder
from revive.check_revival import check_revival

ROOT = Path(__file__).resolve().parent.parent
SHEET = ROOT / "revive/testdata/app1-sheet.json"
SELECTORS = ROOT / "eval/regression/app1-selectors.json"


def test_prompt_uses_only_supplied_inputs():
    sheet = json.loads(SHEET.read_text())
    selectors = json.loads(SELECTORS.read_text())
    prompt = make_prompt(sheet, selectors)
    assert json.dumps(sheet, ensure_ascii=False, indent=2) in prompt
    assert json.dumps(selectors, ensure_ascii=False, indent=2) in prompt
    assert "single" in prompt or "one complete self-contained" in prompt
    # Guard source access rather than opening the forbidden file to compare it.
    with patch.object(Path, "read_text", side_effect=AssertionError("unexpected file read")):
        assert make_prompt(sheet, selectors) == prompt
    assert "fixtures/app1/index.html" not in prompt
    assert "<script>" not in prompt and "function " not in prompt
    claims = json.loads((ROOT / "fixtures/claims.json").read_text())
    assert [line["text"] for line in sheet["lines"]] == [c["text"] for c in claims]
    assert set(sheet) == {"app", "lines"}
    assert all(set(line) == {"id", "screen", "text", "label", "citations", "conflicts"}
               and line["label"] in {"SEEN", "GUESSED"} for line in sheet["lines"])


@pytest.mark.parametrize("reply", [
    '<!doctype html><html><body id="display">0</body></html>',
    'Here it is:\n```html\n<!doctype html><html><body id="display">0</body></html>\n```\nDone.',
    '```HTML\n<html><body id="display">0</body></html>\n```',
])
def test_extract_html(reply):
    html = extract_html(reply)
    assert html.endswith("</html>\n")
    assert 'id="display"' in html
    assert "```" not in html and "Here it is" not in html


def test_reject_incomplete_reply():
    with pytest.raises(ValueError, match="complete HTML"):
        extract_html("<div>not a complete document</div>")


def test_selector_check_rejects_missing_id():
    with pytest.raises(ValueError, match="k7"):
        check_selectors('<html><div id="display"></div><!-- id="k7" --></html>',
                        {"digits": ["#k7"], "observe": "#display"})
    check_selectors("<html><div id='display'></div><button id='k7'></button></html>",
                    {"digits": ["#k7"], "observe": "#display"})


def test_cli_commands():
    assert builder_command("codex") == ["codex", "exec", "-s", "read-only", "--skip-git-repo-check", "--ephemeral", "-"]
    assert builder_command("claude") == ["claude", "-p", "--output-format", "text", "--permission-mode", "plan"]
    assert builder_command("glm")[0] == str(Path.home() / ".local/bin/glm")


def test_run_builder_resolves_executable_on_path():
    seen = []
    with patch("revive.build.shutil.which", return_value="C:/npm/codex.cmd"),             patch("revive.build.subprocess.run", side_effect=lambda c, **k: seen.append(c) or subprocess.CompletedProcess(c, 0, "ok", "")):
        assert run_builder("codex", "p") == "ok"
    assert seen[0][0] == "C:/npm/codex.cmd" and seen[0][1] == "exec"


def test_muse_builder_command_uses_prompt_file_and_no_tools():
    seen = {}

    def fake(c, **k):
        seen.update(cmd=c, input=k["input"], env=k["env"], prompt=(Path(k["cwd"]) / "prompt.txt").read_text(encoding="utf-8"))
        return subprocess.CompletedProcess(c, 0, "ok", "")
    with patch("revive.build.shutil.which", return_value="C:/muse/muse.cmd"), patch("revive.build.subprocess.run", side_effect=fake):
        assert run_builder("muse", "the prompt") == "ok"
    cmd = seen["cmd"]
    assert cmd[:2] == ["C:/muse/muse.cmd", "exec"] and cmd[-2:] == ["--prompt-file", "prompt.txt"]
    assert {"--disable-shell", "--disable-write"} <= set(cmd) and not {"--yolo", "--disable-approval", "--disable-sandbox"} & set(cmd)
    assert seen["input"] is None and seen["prompt"] == "the prompt" and seen["env"]["TMPDIR"] != seen["env"].get("PWD")


def test_build_isolated_and_validated(tmp_path):
    selectors = tmp_path / "selectors.json"
    selectors.write_text('{"observe":"#display"}')
    out = tmp_path / "revival/index.html"
    html = '<html><body id="display">0</body></html>'

    def fake_cli(command, **kwargs):
        assert Path(kwargs["cwd"]) != ROOT
        assert not list(Path(kwargs["cwd"]).iterdir())
        assert "fixtures/app1" not in kwargs["input"]
        return subprocess.CompletedProcess(command, 0, html, "")

    with patch("revive.build.subprocess.run", side_effect=fake_cli):
        assert build(SHEET, selectors, out, "codex") == out
    assert out.read_text() == html + "\n"
    assert out.with_suffix(".prompt.txt").exists()
    with patch("revive.build.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "<html></html>", "")):
        with pytest.raises(ValueError, match="Missing selector"):
            build(SHEET, selectors, out, "codex")
    assert out.read_text() == html + "\n"


def test_runner_observes_revival_not_fixture(tmp_path, capsys):
    html = tmp_path / "index.html"
    html.write_text('''<html><body><div id="display">0</div><button id="k7">7</button>
    <script>document.getElementById('k7').onclick = () => {
      document.getElementById('display').textContent = 'revival-only';
    };</script></body></html>''')
    checks = tmp_path / "checks.json"
    checks.write_text(json.dumps([{"id": "probe", "steps": ["click:#k7"], "observe": "#display", "expect": "revival-only"}]))
    assert check_revival(html, checks) == 0
    assert "Total: 1/1 passed" in capsys.readouterr().out


def test_runner_parses_real_elements_and_scripts(tmp_path, capsys):
    html = tmp_path / "index.html"
    html.write_text('''<html><body><div id=display>A&amp;<span>B</span></div>
    <!-- <div id="ghost"></div><script>throw new Error('comment is not code');</script> -->
    <script>if (document.getElementById('ghost')) throw new Error('comment is not an element');</script>
    </body></html>''')
    checks = tmp_path / "checks.json"
    checks.write_text(json.dumps([{"id": "markup", "steps": [], "observe": "#display", "expect": "A&B"}]))
    assert check_revival(html, checks) == 0
    assert "Total: 1/1 passed" in capsys.readouterr().out
