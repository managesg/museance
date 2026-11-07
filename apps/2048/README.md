# 2048 (demo app)

## Source
- Repo: https://github.com/gabrielecirulli/2048, commit `478b6ec346e3787f589e4af751378d06ded4cbbc`, MIT license (2014), vendored unmodified at `apps/2048/original/`. Commit date 2024-10-24 (code written 2014).
- Serve: `python -m http.server 8001 -d apps/2048/original`, open http://localhost:8001/

## Selectors
| Selector | Meaning |
|---|---|
| `.game-container` | board wrapper, holds `.game-message`, `.grid-container` (16 static `.grid-cell`), `.tile-container` |
| `.tile-container` | holds one `div.tile` per tile; each has a child `.tile-inner` whose text is the value |
| `.tile.tile-<value>.tile-position-<x+1>-<y+1>` | a tile; position classes are 1-based: column 1-4 from the left, row 1-4 from the top. Values above 2048 also get `tile-super` |
| `.tile-new` | on a freshly spawned tile (also on all tiles after a reload) |
| `.tile-merged` | on the tile created by a merge this move (it sits at the merge destination). The two source tiles are also rendered (no `tile-merged`) and slide into the same cell |
| `.score-container` | current score. innerText = score, plus a `+N` line (`.score-addition`) when the score rose since the last render: `4\n+4`. Caution: after a reload with a seeded score S > 0 the first render shows `S\n+S` |
| `.best-container` | best score, plain number |
| `.game-message` | overlay; gets class `game-won` ("You win!") or `game-over` ("Game over!"). innerText when shown is `You win!\n\nKeep going Try again` or `Game over!\n\nTry again` |
| `.keep-playing-button` | "Keep going" (visible only in `game-won`) |
| `.retry-button` | "Try again", restarts |
| `.restart-button` | "New Game", restarts |

Keys: ArrowUp/Right/Down/Left; W/D/S/A; K/L/J/H (vim: up/right/down/left); `r` restarts. Keys with Alt/Ctrl/Meta/Shift are ignored. Swipes work on touch.

## Storage (localStorage)
- `gameState`: JSON `{"grid":{"size":4,"cells":[[...4 columns...]]},"score":N,"over":false,"won":false,"keepPlaying":false}`. `cells[x][y]` is `null` or `{"position":{"x":x,"y":y},"value":v}`; x = column 0-3 from the left, y = row 0-3 from the top. Saved after every effective move and on load; **removed** when the game is over (and on restart, then re-saved with the fresh board).
- `bestScore`: number as a string, separate key. On load, a present `gameState` is restored as-is (no spawn); if absent a new game starts with 2 random tiles.

## Rules and seeded tests
Tiles spawn randomly, so every test seeds localStorage and reloads, then observes something a spawn cannot change. Steps use court syntax; the exact JSON is in `claims.example.json` (ids g01..g12). Rows below are given as board rows y=0 left to right (`_` empty).

1. **Moving slides every tile as far as possible in the arrow direction; two equal adjacent tiles that collide merge into one tile of double value, and the score increases by the new tile's value.**
   - Test `g01` (row0 `2 2 _ _`, ArrowLeft).
   - steps: `["storage:gameState={\"grid\":{\"size\":4,\"cells\":[[{\"position\":{\"x\":0,\"y\":0},\"value\":2},null,null,null],[{\"position\":{\"x\":1,\"y\":0},\"value\":2},null,null,null],[null,null,null,null],[null,null,null,null]]},\"score\":0,\"over\":false,\"won\":false,\"keepPlaying\":false}", "reload", "key:ArrowLeft"]`
   - observe: `.score-container`, expect: `"4\n+4"`

2. **A tile created by a merge cannot merge again in the same move: `2 2 2 2` left gives `4 4 _ _` (score +8), never 8.**
   - Test `g02` (row0 `2 2 2 2`, ArrowLeft).
   - steps: `["storage:gameState={\"grid\":{\"size\":4,\"cells\":[[{\"position\":{\"x\":0,\"y\":0},\"value\":2},null,null,null],[{\"position\":{\"x\":1,\"y\":0},\"value\":2},null,null,null],[{\"position\":{\"x\":2,\"y\":0},\"value\":2},null,null,null],[{\"position\":{\"x\":3,\"y\":0},\"value\":2},null,null,null]]},\"score\":0,\"over\":false,\"won\":false,\"keepPlaying\":false}", "reload", "key:ArrowLeft"]`
   - observe: `.score-container`, expect: `"8\n+8"`

3. **Merging starts from the wall side (the side the tiles move toward): `2 2 2 _` left gives `4 2 _ _`.**
   - Test `g03` (row0 `2 2 2 _`, ArrowLeft, observe the 2 at column 2).
   - steps: `["storage:gameState={\"grid\":{\"size\":4,\"cells\":[[{\"position\":{\"x\":0,\"y\":0},\"value\":2},null,null,null],[{\"position\":{\"x\":1,\"y\":0},\"value\":2},null,null,null],[{\"position\":{\"x\":2,\"y\":0},\"value\":2},null,null,null],[null,null,null,null]]},\"score\":0,\"over\":false,\"won\":false,\"keepPlaying\":false}", "reload", "key:ArrowLeft"]`
   - observe: `.tile-position-2-1`, expect: `"2"`

4. **Same toward the right: `_ 2 2 2` right gives `_ _ 2 4` (the merged 4 at column 4).**
   - Test `g04` (row0 `_ 2 2 2`, ArrowRight).
   - steps: `["storage:gameState={\"grid\":{\"size\":4,\"cells\":[[null,null,null,null],[{\"position\":{\"x\":1,\"y\":0},\"value\":2},null,null,null],[{\"position\":{\"x\":2,\"y\":0},\"value\":2},null,null,null],[{\"position\":{\"x\":3,\"y\":0},\"value\":2},null,null,null]]},\"score\":0,\"over\":false,\"won\":false,\"keepPlaying\":false}", "reload", "key:ArrowRight"]`
   - observe: `.tile-merged.tile-position-4-1`, expect: `"4"`

5. **A move in which no tile changes cell does nothing: no spawn, no score change, nothing re-saved.**
   - Test `g05` (single 2 at top-left, score 6, ArrowLeft, container shows only `2`).
   - steps: `["storage:gameState={\"grid\":{\"size\":4,\"cells\":[[{\"position\":{\"x\":0,\"y\":0},\"value\":2},null,null,null],[null,null,null,null],[null,null,null,null],[null,null,null,null]]},\"score\":6,\"over\":false,\"won\":false,\"keepPlaying\":false}", "reload", "key:ArrowLeft"]`
   - observe: `.tile-container`, expect: `"2"`

6. **Best score becomes the score as soon as score > best.**
   - Test `g06` (bestScore=2, merge two 2s, best shows 4).
   - steps: `["storage:bestScore=2", "storage:gameState={\"grid\":{\"size\":4,\"cells\":[[{\"position\":{\"x\":0,\"y\":0},\"value\":2},null,null,null],[{\"position\":{\"x\":1,\"y\":0},\"value\":2},null,null,null],[null,null,null,null],[null,null,null,null]]},\"score\":0,\"over\":false,\"won\":false,\"keepPlaying\":false}", "reload", "key:ArrowLeft"]`
   - observe: `.best-container`, expect: `"4"`

7. **Best score never decreases and is kept separately from the game.**
   - Test `g07` (bestScore=100, merge two 2s, best stays 100).
   - steps: `["storage:bestScore=100", "storage:gameState={\"grid\":{\"size\":4,\"cells\":[[{\"position\":{\"x\":0,\"y\":0},\"value\":2},null,null,null],[{\"position\":{\"x\":1,\"y\":0},\"value\":2},null,null,null],[null,null,null,null],[null,null,null,null]]},\"score\":0,\"over\":false,\"won\":false,\"keepPlaying\":false}", "reload", "key:ArrowLeft"]`
   - observe: `.best-container`, expect: `"100"`

8. **Creating a 2048 tile sets won and shows the `game-won` message; further moves are blocked until Keep going.**
   - Test `g08` (1024 1024 row, ArrowLeft).
   - steps: `["storage:gameState={\"grid\":{\"size\":4,\"cells\":[[{\"position\":{\"x\":0,\"y\":0},\"value\":1024},null,null,null],[{\"position\":{\"x\":1,\"y\":0},\"value\":1024},null,null,null],[null,null,null,null],[null,null,null,null]]},\"score\":0,\"over\":false,\"won\":false,\"keepPlaying\":false}", "reload", "key:ArrowLeft"]`
   - observe: `.game-message.game-won`, expect: `"You win!\n\nKeep going Try again"`

9. **After a move that spawns a tile, if the board is full and no two adjacent tiles are equal, the game is over: `game-over` message, moves blocked, saved game removed.**
   - Test `g09` (full board that is a dead end after the move (values 8..128 so no spawn of 2/4 can match), ArrowLeft).
   - steps: `["storage:gameState={\"grid\":{\"size\":4,\"cells\":[[null,{\"position\":{\"x\":0,\"y\":1},\"value\":16},{\"position\":{\"x\":0,\"y\":2},\"value\":8},{\"position\":{\"x\":0,\"y\":3},\"value\":16}],[{\"position\":{\"x\":1,\"y\":0},\"value\":8},{\"position\":{\"x\":1,\"y\":1},\"value\":32},{\"position\":{\"x\":1,\"y\":2},\"value\":16},{\"position\":{\"x\":1,\"y\":3},\"value\":32}],[{\"position\":{\"x\":2,\"y\":0},\"value\":16},{\"position\":{\"x\":2,\"y\":1},\"value\":64},{\"position\":{\"x\":2,\"y\":2},\"value\":32},{\"position\":{\"x\":2,\"y\":3},\"value\":64}],[{\"position\":{\"x\":3,\"y\":0},\"value\":32},{\"position\":{\"x\":3,\"y\":1},\"value\":128},{\"position\":{\"x\":3,\"y\":2},\"value\":64},{\"position\":{\"x\":3,\"y\":3},\"value\":128}]]},\"score\":0,\"over\":false,\"won\":false,\"keepPlaying\":false}", "reload", "key:ArrowLeft"]`
   - observe: `.game-message.game-over`, expect: `"Game over!\n\nTry again"`

10. **New Game (`.restart-button`, `.retry-button` or `r`) clears the state, score returns to 0, and the board has exactly 2 new tiles; best score is kept.**
   - Test `g10` (score 100 with 3 tiles, click `.restart-button`, score shows `0`).
   - steps: `["storage:bestScore=100", "storage:gameState={\"grid\":{\"size\":4,\"cells\":[[{\"position\":{\"x\":0,\"y\":0},\"value\":2},{\"position\":{\"x\":0,\"y\":1},\"value\":8},null,null],[{\"position\":{\"x\":1,\"y\":0},\"value\":2},null,null,null],[null,null,null,null],[null,null,null,null]]},\"score\":100,\"over\":false,\"won\":false,\"keepPlaying\":false}", "reload", "click:.restart-button"]`
   - observe: `.score-container`, expect: `"0"`

11. **WASD and vim keys behave identically to the arrows (a=left, d=right, w=up, s=down; h/l/k/j).**
   - Test `g11` (row0 `2 2 _ _`, key `d`, merged 4 at column 4).
   - steps: `["storage:gameState={\"grid\":{\"size\":4,\"cells\":[[{\"position\":{\"x\":0,\"y\":0},\"value\":2},null,null,null],[{\"position\":{\"x\":1,\"y\":0},\"value\":2},null,null,null],[null,null,null,null],[null,null,null,null]]},\"score\":0,\"over\":false,\"won\":false,\"keepPlaying\":false}", "reload", "key:d"]`
   - observe: `.tile-merged.tile-position-4-1`, expect: `"4"`

12. **After winning, Keep going clears the message and sets keepPlaying so moves work again (tiles may exceed 2048); the win message does not return.**
   - Test `g12` (win with 1024+1024, click `.keep-playing-button`, ArrowRight moves, score stays `2048` (no `+` line)).
   - steps: `["storage:gameState={\"grid\":{\"size\":4,\"cells\":[[{\"position\":{\"x\":0,\"y\":0},\"value\":1024},null,null,null],[{\"position\":{\"x\":1,\"y\":0},\"value\":1024},null,null,null],[null,null,null,null],[null,null,null,null]]},\"score\":0,\"over\":false,\"won\":false,\"keepPlaying\":false}", "reload", "key:ArrowLeft", "click:.keep-playing-button", "key:ArrowRight"]`
   - observe: `.score-container`, expect: `"2048"`

## Traps
- Double merge: a tile produced by a merge is not merge-eligible again in that move; evaluate tiles nearest the destination wall first.
- Merge order follows the move direction (`2 2 2` left = `4 2`, right = `2 4`).
- No spawn, no save and no score update when nothing moved (a blocked move on a full line must not add a tile).
- Score adds the value of each newly merged tile only (two 2s: +4), not the sum of the board; moving without merging adds nothing.
- Spawn: after every effective move, one tile in a random empty cell, value 2 with 90% and 4 with 10%. Game start spawns 2 tiles the same way.
- Game over is checked after the spawn; a full board is not over while any adjacent pair is equal. Game over removes `gameState` (reload starts a new game); win does not remove it.
- Won-then-keep-playing: reaching 2048 sets `won` and blocks input until Keep going sets `keepPlaying` (persisted). It is checked on `merged.value === 2048` only, so a later 2048 after keep-playing keeps `won` true but is not blocked.
- Best score persists across reloads and restarts in its own key and updates on every render when score > best.
- The score display adds `+N` only when the score rose versus the previously rendered score; the first render after a reload compares against 0.
- Tile classes use 1-based positions while storage uses 0-based.

## Verification
`python -m court.court --app 2048 --claims apps/2048/claims.example.json --original-dir apps/2048/original --revival-dir apps/2048/original --workers 4 --out <tmp>` gives 12/12 LOCKED, 0 mismatches, 0 flaky (run 3 times).
