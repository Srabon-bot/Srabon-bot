#!/usr/bin/env python3
"""Draw the profile README's stat graphics from the GitHub GraphQL API.

No third-party services and no dependencies — standard library only.

Outputs, all sharing one visual language with ascii.svg (the portrait):
  stats.svg   hero total + weekly sparkline
  streak.svg  current and longest streak
  langs.svg   top languages, by bytes and by repo count

Every file uses the portrait's grey ink, a monospace face, a transparent
background, and the same left-to-right clipPath reveal with a cursor riding
the edge. Motion is SMIL because GitHub strips <script> from READMEs.

Env:
  GITHUB_TOKEN  required
  GH_LOGIN      user to summarise (default: Srabon-bot)
  OUT_DIR       where to write (default: repository root)
"""
import base64
import functools
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

API = "https://api.github.com/graphql"

# Two things are pinned for determinism, both learned the hard way:
#  * the contribution window, to whole UTC days — otherwise "the past year" is
#    measured from request time and days drift between week buckets, moving the
#    sparkline a fraction of a pixel and committing noise every night;
#  * privacy: PUBLIC on repositories — otherwise a personal token sees private
#    repos and a workflow token doesn't, so language totals disagree.
QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date weekday } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 privacy: PUBLIC) {
      nodes {
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

# The portrait's ink is the data ink, so every graphic reads as one material.
LIGHT = dict(data="#6e7681", emph="#424a53", dim="#8c959f",
             rule="#d8dee4", surface="#ffffff")
DARK = dict(data="#c9d1d9", emph="#f0f6fc", dim="#8b949e",
            rule="#30363d", surface="#0d1117")
# JBMono is the inlined subset below; the rest is a fallback for the unlikely
# case a renderer ignores the embedded face.
MONO = ("JBMono,ui-monospace,SFMono-Regular,Menlo,Consolas,"
        "&apos;Liberation Mono&apos;,monospace")
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


@functools.lru_cache(maxsize=None)
def face(filename, weight):
    """One @font-face rule with the subset inlined as a data URI.

    An external font URL cannot work here: these SVGs are loaded through <img>,
    and browsers refuse to fetch subresources for an image document. Inlining is
    also what pins the advance width — the portrait's grid assumes 0.600 em, and
    a viewer whose default monospace is narrower would otherwise see it squeezed.
    """
    with open(os.path.join(FONT_DIR, filename), "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return (f"@font-face{{font-family:JBMono;font-style:normal;"
            f"font-weight:{weight};font-display:block;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")


def font_text():
    """Basic latin, both weights — for the data graphics."""
    return face("jbmono-400.woff2", 400) + face("jbmono-600.woff2", 600)


def font_head():
    """Only the letters the section headings use."""
    return face("jbmono-head.woff2", 600)

WIDTH = 620            # every graphic shares one column width
LEFT = 34              # shared left inset, so stacked blocks line up
REVEAL = 1.30          # seconds; matches the portrait's cadence
MON = ["jan", "feb", "mar", "apr", "may", "jun",
       "jul", "aug", "sep", "oct", "nov", "dec"]


# ---------------------------------------------------------------- data

def window():
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    return (f"{start.isoformat()}T00:00:00Z", f"{today.isoformat()}T23:59:59Z")


def fetch(login, token):
    since, until = window()
    body = json.dumps({"query": QUERY,
                       "variables": {"login": login,
                                     "from": since, "to": until}}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": f"{login}-profile-stats"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL errors: {payload['errors']}")
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise SystemExit(f"no such user: {login}")
    return user


def pretty(iso):
    d = date.fromisoformat(iso)
    return f"{MON[d.month - 1]} {d.day}"


def streaks(days):
    """Current and longest runs of days with at least one contribution.

    A zero on the final day doesn't break the current streak — the day isn't
    over yet. Any earlier zero does.
    """
    best = dict(length=0, start=None, end=None)
    run, run_start = 0, None
    for d in days:
        if d["contributionCount"] > 0:
            run += 1
            run_start = run_start or d["date"]
            if run > best["length"]:
                best = dict(length=run, start=run_start, end=d["date"])
        else:
            run, run_start = 0, None

    cur = dict(length=0, start=None, end=None)
    tail = days[:-1] if days and days[-1]["contributionCount"] == 0 else days
    for d in reversed(tail):
        if d["contributionCount"] == 0:
            break
        cur["length"] += 1
        cur["start"] = d["date"]
        cur["end"] = cur["end"] or d["date"]
    return cur, best


def languages(repos):
    by_size, by_repo = {}, {}
    for node in repos:
        edges = (node.get("languages") or {}).get("edges") or []
        for e in edges:
            name = e["node"]["name"]
            by_size[name] = by_size.get(name, 0) + e["size"]
        if edges:                       # primary language of the repo
            top = edges[0]["node"]["name"]
            by_repo[top] = by_repo.get(top, 0) + 1

    def rank(d):
        # sort by value, then name, so equal values never reorder between runs
        return sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:5]

    return rank(by_size), rank(by_repo)


def fetch_traffic(login, token):
    """Views over the trailing 14 days — the only window GitHub retains.

    Needs push access to the repo, which the default Actions GITHUB_TOKEN
    doesn't have (traffic sits behind the same permission as Insights).
    Pass a PAT — classic with `repo` scope, or fine-grained with
    `Administration: Read-only` — as TRAFFIC_TOKEN.
    """
    headers = {"Authorization": f"bearer {token}",
               "Accept": "application/vnd.github+json",
               "User-Agent": f"{login}-profile-stats"}
    req = urllib.request.Request(
        f"https://api.github.com/repos/{login}/{login}/traffic/views",
        headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def summarise(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [w["contributionDays"] for w in cal["weeks"]]
    days = [d for w in weeks for d in w]
    weekly = [sum(d["contributionCount"] for d in w) for w in weeks]
    cur, best = streaks(days)
    by_size, by_repo = languages(user["repositories"]["nodes"])
    return dict(
        total=cal["totalContributions"],
        active=sum(1 for d in days if d["contributionCount"] > 0),
        best_week=max(weekly) if weekly else 0,
        weekly=weekly, weeks=weeks,
        current=cur, longest=best,
        by_size=by_size, by_repo=by_repo)


# ---------------------------------------------------------------- drawing

def style(extra="", font=None):
    def block(t):
        return (f".d-f{{fill:{t['data']}}}.d-s{{stroke:{t['data']}}}"
                f".e-f{{fill:{t['emph']}}}.m-f{{fill:{t['dim']}}}"
                f".u-s{{stroke:{t['rule']}}}.r{{stroke:{t['surface']}}}")
    return (f"<style>{font or font_text()}"
            f"{block(LIGHT)}.w{{fill:{LIGHT['data']};opacity:.13}}{extra}"
            f"@media(prefers-color-scheme:dark){{{block(DARK)}"
            f".w{{fill:{DARK['data']};opacity:.16}}}}</style>")


def head(w, h, font=None):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" fill="none" font-family="{MONO}">'
            + style(font=font))


def fade(delay, dur=0.45):
    return (f'<animate attributeName="opacity" from="0" to="1" '
            f'begin="{delay:.2f}s" dur="{dur}s" fill="freeze"/>')


def wipe(cid, x, y, w, h, delay, dur=REVEAL):
    """clipPath reveal plus the cursor block that rides its edge."""
    clip = (f'<clipPath id="{cid}"><rect x="{x}" y="{y}" height="{h}" width="0">'
            f'<animate attributeName="width" from="0" to="{w}" '
            f'begin="{delay:.2f}s" dur="{dur}s" fill="freeze"/></rect></clipPath>')
    cursor = (f'<rect y="{y}" width="2" height="{h}" class="d-f" opacity="0">'
              f'<animate attributeName="x" from="{x}" to="{x + w}" '
              f'begin="{delay:.2f}s" dur="{dur}s" fill="freeze"/>'
              f'<set attributeName="opacity" to="0.55" begin="{delay:.2f}s"/>'
              f'<set attributeName="opacity" to="0" '
              f'begin="{delay + dur:.2f}s"/></rect>')
    return clip, cursor


def label(x, y, text, size=11, cls="m-f", anchor="start", extra=""):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return (f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}"{a}'
            f'{extra}>{text}</text>')


def hbar(x, y, w, h, cls="d-f", r=3.0):
    """Horizontal bar: rounded data-end on the right, square at the baseline."""
    if w <= 0.6:
        return ""
    r = min(r, h / 2.0, w)
    return (f'<path d="M{x:.1f} {y:.1f}H{x + w - r:.1f}'
            f'Q{x + w:.1f} {y:.1f} {x + w:.1f} {y + r:.1f}'
            f'V{y + h - r:.1f}Q{x + w:.1f} {y + h:.1f} {x + w - r:.1f} {y + h:.1f}'
            f'H{x:.1f}Z" class="{cls}"/>')


def draw_stats(s):
    """Hero number, the two secondary counts, and the weekly sparkline."""
    H = 148
    weekly = s["weekly"] or [0]
    peak = max(weekly) or 1
    p = [head(WIDTH, H)]
    p.append(f'<g opacity="0">{fade(0.10)}'
             + label(0, 50, s["total"], 52, "e-f", extra=' font-weight="600"')
             + label(0, 72, "contributions in the last year", 12) + '</g>')
    for i, (val, lab) in enumerate([(s["active"], "active days"),
                                    (s["best_week"], "best week")]):
        p.append(f'<g opacity="0">{fade(0.30 + i * 0.12)}'
                 + label(WIDTH, 30 + i * 40, val, 19, "e-f", "end",
                         ' font-weight="600"')
                 + label(WIDTH, 47 + i * 40, lab, 11, "m-f", "end") + '</g>')

    base, top = H - 10, H - 58
    span = base - top
    step = WIDTH / max(len(weekly) - 1, 1)
    pts = [(i * step, base - (v / peak) * span) for i, v in enumerate(weekly)]
    clip, cursor = wipe("rs", 0, top - 6, WIDTH, span + 8, 0.50)
    p.append(clip)
    p.append('<g clip-path="url(#rs)">')
    p.append(f'<path d="M{pts[0][0]:.1f} {base:.1f}'
             + "".join(f'L{x:.1f} {y:.1f}' for x, y in pts)
             + f'L{pts[-1][0]:.1f} {base:.1f}Z" class="w"/>')
    p.append(f'<path d="M{pts[0][0]:.1f} {pts[0][1]:.1f}'
             + "".join(f'L{x:.1f} {y:.1f}' for x, y in pts[1:])
             + f'" class="d-s" stroke-width="2" stroke-linejoin="round" '
             f'stroke-linecap="round"/>')
    p.append("</g>")
    p.append(cursor)
    ex, ey = pts[-1]
    p.append(f'<circle cx="{ex - 2:.1f}" cy="{ey:.1f}" r="4.5" class="e-f r" '
             f'stroke-width="2" opacity="0">{fade(0.50 + REVEAL, 0.35)}</circle>')
    p.append("</svg>")
    return "".join(p)


def draw_streak(s):
    """Current and longest streak, split by a hairline."""
    H = 96
    cells = []
    for k, lab in (("current", "current streak"), ("longest", "longest streak")):
        r = s[k]
        span = (f"{pretty(r['start'])} &#8211; {pretty(r['end'])}"
                if r["length"] else "&#8212;")
        cells.append((r["length"], lab, span))

    p = [head(WIDTH, H)]
    mid = WIDTH / 2
    p.append(f'<line x1="{mid:.0f}" y1="16" x2="{mid:.0f}" y2="80" '
             f'class="u-s" stroke-width="1" opacity="0">{fade(0.20)}</line>')
    for i, (val, lab, span) in enumerate(cells):
        x = LEFT if i == 0 else mid + LEFT
        p.append(f'<g opacity="0">{fade(0.12 + i * 0.14)}'
                 + label(x, 44, f"{val}", 34, "e-f", extra=' font-weight="600"')
                 + label(x, 64, lab, 11)
                 + label(x, 80, span, 10) + '</g>')
    p.append("</svg>")
    return "".join(p)


def draw_visits(v):
    """Total and unique profile views, from the repo's own traffic window."""
    H = 96
    total, uniques = v.get("count", 0), v.get("uniques", 0)
    p = [head(WIDTH, H)]
    mid = WIDTH / 2
    p.append(f'<line x1="{mid:.0f}" y1="16" x2="{mid:.0f}" y2="80" '
             f'class="u-s" stroke-width="1" opacity="0">{fade(0.20)}</line>')
    cells = [(total, "profile views", "last 14 days"),
             (uniques, "unique visitors", "last 14 days")]
    for i, (val, lab, span) in enumerate(cells):
        x = LEFT if i == 0 else mid + LEFT
        p.append(f'<g opacity="0">{fade(0.12 + i * 0.14)}'
                 + label(x, 44, f"{val}", 34, "e-f", extra=' font-weight="600"')
                 + label(x, 64, lab, 11)
                 + label(x, 80, span, 10) + '</g>')
    p.append("</svg>")
    return "".join(p)


def draw_langs(s):
    """Two small charts: share of bytes, and count of repos by main language."""
    rows = max(len(s["by_size"]), len(s["by_repo"]), 1)
    H = 26 + rows * 22 + 6
    colw = (WIDTH - LEFT - 30) / 2
    name_w, bar_max = 82, colw - 82 - 44

    p = [head(WIDTH, H)]
    groups = [(LEFT, "by bytes", s["by_size"], True),
              (LEFT + colw + 30, "by repos", s["by_repo"], False)]
    for gi, (gx, title, data, as_pct) in enumerate(groups):
        p.append(f'<g opacity="0">{fade(0.10 + gi * 0.10)}'
                 + label(gx, 12, title.upper(), 9, "m-f",
                         extra=' letter-spacing="1.3"') + '</g>')
        if not data:
            continue
        top = max(v for _, v in data) or 1
        total = sum(v for _, v in data) or 1
        cid = f"rl{gi}"
        clip, cursor = wipe(cid, gx + name_w, 20, bar_max, rows * 22,
                            0.34 + gi * 0.12, 0.95)
        p.append(clip)
        for ri, (name, val) in enumerate(data):
            y = 26 + ri * 22
            shown = (f"{val / total * 100:.0f}%" if as_pct else f"{val}")
            p.append(f'<g opacity="0">{fade(0.24 + gi * 0.10 + ri * 0.05)}'
                     + label(gx, y + 8, name.lower()[:11], 11, "e-f")
                     + label(gx + colw - 6, y + 8, shown, 11, "m-f", "end")
                     + '</g>')
            p.append(f'<g clip-path="url(#{cid})">'
                     + hbar(gx + name_w, y, bar_max * val / top, 7)
                     + '</g>')
        p.append(cursor)
    p.append("</svg>")
    return "".join(p)


def draw_heading(word):
    """A section heading in the mono face, with a hairline running right.

    GitHub strips <style> and style= from markdown, so a real markdown heading
    can only ever be GitHub's own sans. Rendering the label as an SVG is the
    only way to put the page's own typeface on it. The rule starts past the
    longest plausible advance (0.6em is the widest common monospace ratio), so
    a narrower font on the viewer's machine widens the gap slightly rather than
    colliding with the text.
    """
    FS = 16
    H = 26
    text_end = len(word) * FS * 0.6 + 18
    p = [head(WIDTH, H, font=font_head())]
    p.append(label(0, 18, word, FS, "e-f", extra=' font-weight="600"'))
    p.append(f'<line x1="{text_end:.0f}" y1="12.5" x2="{WIDTH}" y2="12.5" '
             f'class="u-s" stroke-width="1"/>')
    p.append("</svg>")
    return "".join(p)


# ---------------------------------------------------------------- main

def write(path, svg):
    old = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = f.read()
    if old == svg:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    return True


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    login = os.environ.get("GH_LOGIN", "Srabon-bot")
    out_dir = os.environ.get("OUT_DIR", ".")

    s = summarise(fetch(login, token))
    files = {"stats.svg": draw_stats(s), "streak.svg": draw_streak(s),
             "langs.svg": draw_langs(s)}

    traffic_token = os.environ.get("TRAFFIC_TOKEN")
    if traffic_token:
        try:
            files["visits.svg"] = draw_visits(fetch_traffic(login, traffic_token))
        except Exception as e:
            print(f"traffic fetch failed, skipping visits.svg: {e}")

    for word in ("stats",):
        files[f"hd-{word.replace(' ', '-')}.svg"] = draw_heading(word)

    changed = [n for n, svg in files.items()
               if write(os.path.join(out_dir, n), svg)]
    print(f"{s['total']} contributions, {s['active']} active days, "
          f"best week {s['best_week']}, current streak "
          f"{s['current']['length']}, longest {s['longest']['length']}")
    print("languages by bytes: "
          + ", ".join(f"{n} {v}" for n, v in s["by_size"]))
    print("updated: " + (", ".join(sorted(changed)) if changed else "nothing"))


if __name__ == "__main__":
    main()
