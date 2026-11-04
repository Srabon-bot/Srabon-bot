"""Generate coding-stats.svg with live numbers from the GitHub GraphQL API.

Commits  = GitHub's own commit contribution count (same source as the profile graph).
Lines    = lines ADDED in your commits on each repo's default branch.
Periods  = today / this week (Mon-Sun) / this month / this year, in TZ below.
"""
import json
import os
import pathlib
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("STATS_TZ", "Asia/Dhaka"))
# Ignore single commits that add more than this many lines (lockfiles, vendored code, data dumps).
MAX_LINES_PER_COMMIT = int(os.environ.get("MAX_LINES_PER_COMMIT", "5000"))

TOKEN = os.environ.get("STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")
LOGIN = os.environ.get("STATS_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER")
if not TOKEN or not LOGIN:
    sys.exit("Missing token or username (STATS_TOKEN / GITHUB_REPOSITORY_OWNER).")

ROOT = pathlib.Path(__file__).resolve().parent.parent


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def period_starts(now):
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "today": day,
        "week": day - timedelta(days=day.weekday()),
        "month": day.replace(day=1),
        "year": day.replace(month=1, day=1),
    }


def fetch_commits_and_repos(starts, now):
    q = """
    query($login:String!,$from:DateTime!,$to:DateTime!){
      user(login:$login){
        id
        contributionsCollection(from:$from,to:$to){
          totalCommitContributions
          commitContributionsByRepository(maxRepositories:100){ repository{ nameWithOwner } }
        }
      }
    }"""
    commits, repos, user_id = {}, set(), None
    for key, start in starts.items():
        u = gql(q, {"login": LOGIN, "from": iso(start), "to": iso(now)})["user"]
        user_id = u["id"]
        cc = u["contributionsCollection"]
        commits[key] = cc["totalCommitContributions"]
        if key == "year":
            repos = {r["repository"]["nameWithOwner"] for r in cc["commitContributionsByRepository"]}
    return commits, repos, user_id


def fetch_lines(repos, user_id, starts):
    q = """
    query($owner:String!,$name:String!,$since:GitTimestamp!,$author:ID!,$cursor:String){
      repository(owner:$owner,name:$name){
        defaultBranchRef{ target{ ... on Commit{
          history(first:100,since:$since,author:{id:$author},after:$cursor){
            pageInfo{ hasNextPage endCursor }
            nodes{ committedDate additions }
          }
        } } }
      }
    }"""
    lines = {k: 0 for k in starts}
    since = iso(starts["year"])
    for full in sorted(repos):
        owner, name = full.split("/")
        cursor = None
        while True:
            repo = gql(q, {"owner": owner, "name": name, "since": since, "author": user_id, "cursor": cursor})["repository"]
            ref = repo and repo["defaultBranchRef"]
            if not ref:
                break
            hist = ref["target"]["history"]
            for c in hist["nodes"]:
                add = c["additions"]
                if add > MAX_LINES_PER_COMMIT:
                    continue
                when = datetime.fromisoformat(c["committedDate"].replace("Z", "+00:00")).astimezone(TZ)
                for key, start in starts.items():
                    if when >= start:
                        lines[key] += add
            if not hist["pageInfo"]["hasNextPage"]:
                break
            cursor = hist["pageInfo"]["endCursor"]
    return lines


TEMPLATE = """<svg width="100%" viewBox="20 38 640 164" role="img" xmlns="http://www.w3.org/2000/svg">
  <title>Coding stats</title>
  <desc>Commits and lines coded for today, this week, this month and this year</desc>
  <style>
    text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif; }
    .line  { stroke: #d0d7de; }
    .muted { fill: #59636e; }
    .num   { fill: #0969da; }
    .lines { fill: #1a7f37; }
    @media (prefers-color-scheme: dark) {
      .line  { stroke: #30363d; }
      .muted { fill: #8b949e; }
      .num   { fill: #58a6ff; }
      .lines { fill: #3fb950; }
    }
  </style>

  <text class="muted" x="636" y="52" font-size="11" text-anchor="end">updated __UPDATED__</text>

  <line class="line" x1="190" y1="68" x2="190" y2="178"/>
  <line class="line" x1="350" y1="68" x2="350" y2="178"/>
  <line class="line" x1="510" y1="68" x2="510" y2="178"/>

__COLUMNS__
</svg>
"""

COLUMN = """  <text class="muted" x="{x}" y="88" font-size="12">{label}</text>
  <text class="num" x="{x}" y="124" font-size="30" font-weight="500">{commits}</text>
  <text class="muted" x="{x}" y="142" font-size="12">commits</text>
  <text class="lines" x="{x}" y="168" font-size="16" font-weight="500">{lines}</text>
  <text class="muted" x="{x}" y="186" font-size="12">lines coded</text>"""


def render(commits, lines, now):
    cols = []
    for x, key, label in [(44, "today", "Today"), (204, "week", "This week"),
                          (364, "month", "This month"), (524, "year", "This year")]:
        cols.append(COLUMN.format(x=x, label=label, commits=f"{commits[key]:,}", lines=f"{lines[key]:,}"))
    svg = TEMPLATE.replace("__COLUMNS__", "\n\n".join(cols))
    return svg.replace("__UPDATED__", now.strftime("%d %b %H:%M"))


def main():
    now = datetime.now(TZ)
    starts = period_starts(now)
    commits, repos, user_id = fetch_commits_and_repos(starts, now)
    lines = fetch_lines(repos, user_id, starts)
    (ROOT / "coding-stats.svg").write_text(render(commits, lines, now), encoding="utf-8")
    print("commits:", commits, "lines:", lines)


if __name__ == "__main__":
    main()
