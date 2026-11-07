# Credits
Third-party apps, libraries and assets used, with license. Add a line when you add one.

| Item | Used for | License | Link |
| --- | --- | --- | --- |
| Playwright for Python | Browser driver for the court and screenshots (`court/`) | Apache-2.0 | https://github.com/microsoft/playwright-python |
| pytest | Test runner for `eval/`, `revive/`, `dig/` | MIT | https://github.com/pytest-dev/pytest |
| themaxsandelin/todo | The dead app we revive; original build vendored as the oracle in apps/todo/original (never shown to revival builders) | MIT, (c) 2016 Max Sandelin | https://github.com/themaxsandelin/todo |
| React, Vite, Vitest | Stage UI and its tests (`court/ui/`) | MIT | https://react.dev, https://vite.dev, https://vitest.dev |
| MongoDB Node.js driver | Optional Atlas source in the stage feed (`court/ui/server/feed.ts`) | Apache-2.0 | https://github.com/mongodb/node-mongodb-native |
| UnifrakturCook, Alfa Slab One, Courier Prime, Atkinson Hyperlegible (via Fontsource) | Stage typefaces (`court/ui/`) | SIL OFL 1.1 | https://fontsource.org |
| SÉANCE cast and set art | SVG cast, set and avatars in `court/ui/src/cast/`, `court/ui/src/set/`, `court/ui/public/avatars/` | Ours: drawn today by P3's agents from Vi's reference illustration; avatars are renders of those SVGs | this repo |
| CSS reset (`reset.min.css`) and Roboto (Google Fonts link) | Shipped inside the vendored todo oracle only (`apps/todo/original/`), covered by its MIT license file; Roboto is loaded from Google Fonts at view time, not vendored | Reset: as shipped upstream; Roboto: Apache-2.0 | https://github.com/themaxsandelin/todo, https://fonts.google.com/specimen/Roboto |
| OpenAI-compatible LLM APIs (ASI1 and others via `.env`); Codex, Claude, GLM CLIs | Builders and the Medium/Skeptic (`agents/llm.py`, `revive/build.py`); called as services, no code vendored | Provider terms | n/a |
| gabrielecirulli/2048 | Second dead app: original build vendored as the oracle in apps/2048/original (court-only case) | MIT | https://github.com/gabrielecirulli/2048 |
