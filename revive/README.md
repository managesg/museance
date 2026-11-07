Revival builder
===============

The builder receives only a behavior sheet and selector map. It runs the chosen
coding CLI in an empty temporary working directory, saves the prompt alongside
the requested output as `index.prompt.txt`, extracts a complete HTML document,
and rejects missing selector IDs before writing `index.html`.

```sh
python revive/build.py --sheet revive/testdata/app1-sheet.json \
  --selectors eval/regression/app1-selectors.json \
  --out runs/app1/revival/index.html --builder codex
python revive/check_revival.py runs/app1/revival/index.html
python -m pytest -q revive eval
```

Builders: `codex`, `claude`, or `glm`. The chosen CLI must already be installed
and authenticated, with working backend connectivity and writable CLI state.
There are no direct API calls in this builder.

The example sheet transcribes only the fixture claim texts; claim IDs identify
citations. Uncertain and fabricated claims map to `GUESSED`, because behavior
sheets admit only `SEEN` and `GUESSED`. The selector map is passed separately.
The original calculator source is never an input to the builder or evaluator.

Evaluation uses the stub DOM approach of `eval/run_fixture.js` with a fresh
context for each check. It supports direct ID lookups, click handlers, and text
updates, rather than full browser layout or DOM behavior. Runtime errors are
reported as failed checks. The command exits 1 for mismatches and 2 when it
cannot run. It requires Linux, libseccomp and Node with `--permission` support
(verified here with Node 24). Node permissions restrict filesystem access and
process creation; a seccomp filter blocks network socket syscalls. Evaluation
fails closed if these sandbox facilities are unavailable.
