"""Dig collector: pre-collect an app's evidence pile into dig/piles/<app>/pile.json.

Tier C: the GitHub repo description, README, issues and PRs (text, via `gh api`).
Tier B: our own screenshots of the running original, one per scripted scene in dig/piles/<app>/scenes.json
        ([{"name", "steps"}], CONTRACTS step grammar). Each shot also stores the page's visible text.
usage: uv run --with playwright python dig/collect.py todo --repo themaxsandelin/todo --original <dir with index.html>
"""
import argparse, json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LISTS = ["#todo", "#completed"]  # ponytail: todo-app lists; scenes.json can override per scene with "lists"
sys.path.insert(0, str(ROOT))


def gh(path):
    return json.loads(subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True, encoding="utf-8").stdout)


def github_items(repo):
    meta = gh(f"repos/{repo}")
    lic = (meta.get("license") or {}).get("spdx_id") or "unknown"
    url = f"https://github.com/{repo}"
    items = [{"tier": "C", "kind": "page", "source": url, "license": lic, "text": f"{meta['description'] or ''} (created {meta['created_at'][:10]}, archived: {meta.get('archived')})"}]
    readme = subprocess.run(["gh", "api", f"repos/{repo}/readme", "-H", "Accept: application/vnd.github.raw"],
                            capture_output=True, text=True, check=True, encoding="utf-8").stdout
    items.append({"tier": "C", "kind": "doc", "source": f"{url}#readme", "license": lic, "text": readme.strip()})
    for it in gh(f"repos/{repo}/issues?state=all&per_page=100"):
        text = f"{'PR' if 'pull_request' in it else 'Issue'} #{it['number']} ({it['state']}): {it['title']}\n{(it.get('body') or '').strip()}"
        items.append({"tier": "C", "kind": "issue", "source": it["html_url"], "license": "public GitHub issue, quoted as evidence", "text": text.strip()})
    return items


def screenshots(app, original, scenes):
    from playwright.sync_api import sync_playwright
    from court.serve import folder
    from court.steps import run_steps
    shots = ROOT / "dig" / "piles" / app / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    items = []
    with folder(original) as url, sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")  # system Chrome, no browser download
        for sc in scenes:
            page = browser.new_context(viewport={"width": 900, "height": 700}).new_page()  # fresh storage per scene
            run_steps(page, url, sc["steps"], "body")
            page.screenshot(path=shots / f"{sc['name']}.png")
            seen = "; ".join(f"{sel}: {page.locator(sel + ' li').count()} items {page.locator(sel + ' li').all_inner_texts()}"
                             for sel in sc.get("lists", LISTS))
            items.append({"tier": "B", "kind": "screenshot", "source": f"our screenshot of the original, scene '{sc['name']}'",
                          "license": "ours", "path": f"shots/{sc['name']}.png",
                          "text": f"Screenshot after steps {sc['steps']}. Seen on screen: {seen}"})
            page.context.close()
        browser.close()
    return items


def main():
    a = argparse.ArgumentParser()
    a.add_argument("app")
    a.add_argument("--repo", required=True)
    a.add_argument("--original", help="folder holding the original build; skip screenshots if omitted")
    a = a.parse_args()
    pile_dir = ROOT / "dig" / "piles" / a.app
    items = github_items(a.repo)
    if a.original:
        items += screenshots(a.app, a.original, json.loads((pile_dir / "scenes.json").read_text(encoding="utf-8")))
    (pile_dir / "pile.json").write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(items)} pile items -> {pile_dir / 'pile.json'}")


if __name__ == "__main__":
    main()
