# todo (themaxsandelin) - original build / oracle

- Source: https://github.com/themaxsandelin/todo
- Vendored commit: `87d0205389edd6da8fdbf0732c6b0b589d0a57c2` (depth-1 clone; only index.html, resources/, LICENSE.md copied)
- License: MIT, (c) 2016 Max Sandelin (`original/LICENSE.md`)
- Why dead: GitHub repo is archived (`gh api repos/themaxsandelin/todo` -> archived: true); last commit 2021-09-09 (the API `pushed_at` reads 2024-04-08, the archive-time update; no code commits since 2021).
- Note: `index.html` links Google Fonts (Roboto). Left untouched; offline it falls back to sans-serif and the page still works.

## Serve

    python -m http.server 8011 -d apps/todo/original

then open http://localhost:8011

## Key selectors (from reading index.html and resources/js/main.js)

| Selector | What |
|---|---|
| `#item` | text input (placeholder "Enter an activity..") |
| `#add` | add button; adds only if the input is non-empty |
| `#todo` | `<ul>` of open items; newest item is inserted first |
| `#completed` | `<ul>` of completed items |
| `#todo li`, `#completed li` | an item; its innerText is the entered text |
| `.complete` (inside an li) | toggles the item between `#todo` and `#completed` |
| `.remove` (inside an li) | deletes the item |

Behaviour notes: Enter (`Enter`/`NumpadEnter`) in `#item` also adds; the input is cleared after adding; state persists in `localStorage` key `todoList` (stored as text values, so duplicate items are matched by value).

Court proof: `court/tests/test_app_todo.py` runs `court/tests/data/claims.todo.json` with this original as both builds; all claims LOCKED.
