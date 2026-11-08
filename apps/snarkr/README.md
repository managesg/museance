# Snarkr (demo original)

A 2014-style sarcastic microblog we wrote today as the court's oracle ("the dead app"). Deterministic, no network, state in localStorage (`snarkr.posts`). MIT, ours. Tell judges it is a stand-in we built.

Serve: `python -m http.server 8001 -d apps/snarkr/original`

## Behaviors the court can test (selector → expected)
| # | Behavior | Steps → observe |
|---|---|---|
| 1 | Post goes to the top of the feed | `type:#composer:hi` `click:#post` → `#feed .post .text` = `hi` |
| 2 | Enter posts, Shift+Enter does not | `type:#composer:hi` `key:Enter` → first `.text` |
| 3 | Empty or whitespace post is roasted | `type:#composer:   ` `click:#post` → `#error` = `Wow. Nothing. Bold.` |
| 4 | Counter is 140 minus length | `type:#composer:abc` → `#count` = `137` |
| 5 | Over 140: counter `.over`, Snark disabled, nothing posted | 141 chars → `#count` = `-1` |
| 6 | Claps pluralize | one `.clap` → `.claps` = `1 slow clap`; two → `2 slow claps` |
| 7 | Trailing `/s` adds a sarcasm badge and is stripped | `type:#composer:great idea /s` → `.text` = `great idea`, `.badge` = `sarcasm` |
| 8 | Hashtags become `.tag`; click filters; `#clear-filter` resets | `#filter` = `#mondays` |
| 9 | “Well, actually” adds a reply; count pluralizes | `.replies-count` = `1 reply` |
| 10 | Mute is case-insensitive and counts hidden posts | mute `CRYPTO` hides `crypto rules` → `#muted-count` = `1 post hidden` |
| 11 | Hot sorts by claps, ties newest first | `#sort-hot` → first `.text` |
| 12 | Posts survive a reload | reload → `.text` present |

Not in the app (good FABRICATED bait): editing posts, a dislike button, DMs.
Likely drift in an agent rewrite: `1 slow claps`, `/s` left in text, case-sensitive mute, posting at 141 chars, error text paraphrased.
