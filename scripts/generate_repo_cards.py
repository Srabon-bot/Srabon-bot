#!/usr/bin/env python3
"""Draw self-hosted cards for the README's Featured Repositories table.

Replaces github-readme-stats.vercel.app pin cards: that's a single free
shared instance, and it 503s under load (it did, the day this was written).
Same story as generate_stats.py -- no third-party services, own the render.
These share its visual language (JBMono, the portrait's ink, a clipPath-free
fade-in) by importing its drawing primitives directly.

Env:
  GITHUB_TOKEN  optional -- unauthenticated REST is capped at 60 req/hr,
                which is plenty for a handful of cards run once a day, but
                set it (Actions provides it for free) to be safe
  GH_LOGIN      owner of the featured repos (default: Srabon-bot)
  OUT_DIR       where to write (default: repository root)
"""
import json
import os
import textwrap
import urllib.request

import generate_stats as gs

# repo name -> output slug (card-<slug>.svg), matching the local project
# folder names. Owner is assumed to be GH_LOGIN; make this (owner, name, slug)
# instead if a featured repo is ever not owned by GH_LOGIN.
FEATURED = [
    ("Bangladesh-flood-data-set", "flood-dataset"),
    ("Discharge-forecaster-model-for-Bangladesh", "discharge-forecaster"),
    ("Bangladesh-flood-risk-classifier-model", "flood-risk-classifier"),
    ("Bangladesh-flood-susceptibility", "flood-susceptibility"),
]

GAP = 20
CARD_W = (gs.WIDTH - GAP) / 2      # two columns inside the shared column width
CARD_H = 112


def esc(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fetch_repo(login, name, token):
    headers = {"User-Agent": f"{login}-profile-stats", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"bearer {token}"
    req = urllib.request.Request(f"https://api.github.com/repos/{login}/{name}", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def wrap_desc(text, width=38):
    if not text:
        return []
    words = textwrap.wrap(text, width)
    if len(words) <= 2:
        return words
    second = words[1][: width - 1].rstrip() + "…"
    return [words[0], second]


# JBMono's ramp advance is 0.6em (see make_portrait.py); the data-graphics
# weights are close enough to budget off the same ratio.
def fit(text, font_size, max_w=CARD_W - 32):
    max_chars = int(max_w / (font_size * 0.6))
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1]
    if "-" in cut:
        cut = cut.rsplit("-", 1)[0]
    return cut + "…"


def draw_card(repo, delay):
    name = esc(fit(repo["name"], 13))
    desc_lines = [esc(l) for l in wrap_desc(repo.get("description") or "")]
    lang = esc(repo.get("language") or "")
    stars, forks = repo.get("stargazers_count", 0), repo.get("forks_count", 0)

    p = [gs.head(CARD_W, CARD_H)]
    p.append(f'<rect x="0.5" y="0.5" width="{CARD_W - 1:.1f}" height="{CARD_H - 1}" '
             f'rx="6" class="u-s" fill="none" stroke-width="1" opacity="0">'
             f'{gs.fade(delay)}</rect>')
    p.append(f'<g opacity="0">{gs.fade(delay + 0.06)}'
             + gs.label(16, 27, name, 13, "e-f", extra=' font-weight="600"') + '</g>')
    for i, line in enumerate(desc_lines):
        p.append(f'<g opacity="0">{gs.fade(delay + 0.12 + i * 0.05)}'
                 + gs.label(16, 47 + i * 15, line, 11) + '</g>')
    foot = [w for w in (lang, f"{stars} stars", f"{forks} forks") if w]
    p.append(f'<g opacity="0">{gs.fade(delay + 0.24)}'
             + gs.label(16, CARD_H - 16, "   ".join(foot), 10.5) + '</g>')
    p.append("</svg>")
    return "".join(p)


def main():
    token = os.environ.get("GITHUB_TOKEN")
    login = os.environ.get("GH_LOGIN", "Srabon-bot")
    out_dir = os.environ.get("OUT_DIR", ".")

    changed = []
    for i, (name, slug) in enumerate(FEATURED):
        repo = fetch_repo(login, name, token)
        path = os.path.join(out_dir, f"card-{slug}.svg")
        if gs.write(path, draw_card(repo, delay=0.08 * i)):
            changed.append(os.path.basename(path))
        print(f"{name}: {repo.get('language')}, "
              f"{repo.get('stargazers_count', 0)} stars, "
              f"{repo.get('forks_count', 0)} forks")
    print("updated: " + (", ".join(sorted(changed)) if changed else "nothing"))


if __name__ == "__main__":
    main()
