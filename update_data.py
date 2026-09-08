#!/usr/bin/env python3
"""
Fetches 2026/27 UEFA Champions League matches + standings from football-data.org
and writes a flat data.json that the dashboard reads.

Runs unattended in GitHub Actions. The only secret it needs is FOOTBALL_DATA_TOKEN.

Design notes:
  - This script does NOT compute fantasy points. It only normalises raw results.
    All scoring logic lives in index.html so there is one place to fix rules.
  - It resolves the 36 official API team names against the draft roster using an
    alias table, and FAILS LOUDLY if any team is unmatched. That check is the
    whole reason setup is a one-time job: if it passes once, it passes forever.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

API = "https://api.football-data.org/v4"
COMPETITION = "CL"
SEASON = "2026"  # football-data labels a season by its starting year
TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN", "").strip()

# ---------------------------------------------------------------------------
# The draft. Keys are the manager names; values are the four drafted clubs.
# The strings here are the *display* names shown in the dashboard.
# ---------------------------------------------------------------------------
DRAFT = {
    "Chino":  ["Bayern München", "Stuttgart", "Fenerbahçe", "Sabah"],
    "Eduars": ["Barcelona", "Sporting CP", "Galatasaray", "Slovan Bratislava"],
    "OMG":    ["Real Madrid", "RB Leipzig", "Como", "Viking"],
    "Nestor": ["Paris Saint-Germain", "Napoli", "PSV", "Slavia Praha"],
    "Doug":   ["Arsenal", "Roma", "Real Betis", "AEK Athens"],
    "Marron": ["Atlético Madrid", "Aston Villa", "Villarreal", "LASK"],
    "Lucho":  ["Manchester City", "Porto", "Lille", "Shakhtar Donetsk"],
    "Pohio":  ["Liverpool", "Borussia Dortmund", "Club Brugge", "Feyenoord"],
    "Chacho": ["Manchester United", "Inter", "Bodø/Glimt", "Lens"],
}

# ---------------------------------------------------------------------------
# Alias table: maps lowercased fragments of the API's official club name to our
# display name. Matching is "does the API name contain this fragment".
# Order matters — first match wins, so keep specific fragments above generic.
# ---------------------------------------------------------------------------
ALIASES = [
    ("bayern",              "Bayern München"),
    ("stuttgart",           "Stuttgart"),
    ("fenerbah",            "Fenerbahçe"),
    ("sabah",               "Sabah"),
    ("barcelona",           "Barcelona"),
    ("sporting clube",      "Sporting CP"),
    ("sporting cp",         "Sporting CP"),
    ("galatasaray",         "Galatasaray"),
    ("bratislava",          "Slovan Bratislava"),
    ("real madrid",         "Real Madrid"),
    ("leipzig",             "RB Leipzig"),
    ("como",                "Como"),
    ("viking",              "Viking"),
    ("paris saint",         "Paris Saint-Germain"),
    ("napoli",              "Napoli"),
    ("psv",                 "PSV"),
    ("slavia",              "Slavia Praha"),
    ("arsenal",             "Arsenal"),
    ("betis",               "Real Betis"),   # must precede a bare "roma"/"real"
    ("roma",                "Roma"),
    ("aek",                 "AEK Athens"),
    ("atl",                 "Atlético Madrid"),  # Atlético / Atleti / Atletico
    ("aston villa",         "Aston Villa"),
    ("villarreal",          "Villarreal"),
    ("lask",                "LASK"),
    ("manchester city",     "Manchester City"),
    ("porto",               "Porto"),
    ("lille",               "Lille"),
    ("shakhtar",            "Shakhtar Donetsk"),
    ("liverpool",           "Liverpool"),
    ("dortmund",            "Borussia Dortmund"),
    ("brugge",              "Club Brugge"),
    ("feyenoord",           "Feyenoord"),
    ("manchester united",   "Manchester United"),
    ("internazionale",      "Inter"),
    ("bod",                 "Bodø/Glimt"),
    ("lens",                "Lens"),
]


def get(path):
    """GET with retry. Free tier is 10 req/min, so we are deliberately slow."""
    req = urllib.request.Request(
        f"{API}{path}", headers={"X-Auth-Token": TOKEN, "Accept": "application/json"}
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 20 * (attempt + 1)
                print(f"  rate limited, waiting {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            if attempt == 3:
                raise
            print(f"  retrying after {e}", file=sys.stderr)
            time.sleep(5)
    raise RuntimeError("exhausted retries")


def resolve(api_name):
    """Map an official API club name to our display name, or None."""
    low = api_name.lower()
    for fragment, display in ALIASES:
        if fragment in low:
            return display
    return None


def normalise_stage(stage):
    """Collapse API stage labels into the five buckets our scoring cares about."""
    s = (stage or "").upper()
    if "LEAGUE" in s or "GROUP" in s:
        return "LEAGUE"
    if "PLAYOFF" in s or "PLAY_OFF" in s:
        return "PLAYOFF"
    if "16" in s:
        return "R16"
    if "QUARTER" in s:
        return "QF"
    if "SEMI" in s:
        return "SF"
    if "FINAL" in s or "3RD" in s:
        return "FINAL"
    return "OTHER"


def main():
    if not TOKEN:
        sys.exit("FOOTBALL_DATA_TOKEN is not set. Add it as a repository secret.")

    print("Fetching matches...")
    raw_matches = get(f"/competitions/{COMPETITION}/matches?season={SEASON}")
    time.sleep(7)
    print("Fetching standings...")
    raw_standings = get(f"/competitions/{COMPETITION}/standings?season={SEASON}")

    # --- resolve every club the API mentions -------------------------------
    seen, unmatched = {}, set()
    for m in raw_matches.get("matches", []):
        for side in ("homeTeam", "awayTeam"):
            t = m.get(side) or {}
            name = t.get("name") or t.get("shortName")
            if not name:
                continue
            display = resolve(name)
            if display:
                seen[name] = display
            else:
                unmatched.add(name)

    if unmatched:
        print("\nUNMATCHED CLUBS — add a fragment to ALIASES and re-run:",
              file=sys.stderr)
        for n in sorted(unmatched):
            print(f"   {n}", file=sys.stderr)
        sys.exit(1)

    drafted = {t for teams in DRAFT.values() for t in teams}
    missing = drafted - set(seen.values())
    if missing:
        print(f"\nWARNING: drafted clubs never seen in fixtures: {sorted(missing)}",
              file=sys.stderr)

    # --- matches -----------------------------------------------------------
    matches = []
    for m in raw_matches.get("matches", []):
        home = resolve((m.get("homeTeam") or {}).get("name") or "")
        away = resolve((m.get("awayTeam") or {}).get("name") or "")
        if not home or not away:
            continue
        score = m.get("score") or {}
        ft = score.get("fullTime") or {}
        reg = score.get("regularTime") or {}
        et = score.get("extraTime") or {}
        pen = score.get("penalties") or {}
        matches.append({
            "id": m.get("id"),
            "utcDate": m.get("utcDate"),
            "status": m.get("status"),          # SCHEDULED / IN_PLAY / PAUSED / FINISHED
            "stage": normalise_stage(m.get("stage")),
            "rawStage": m.get("stage"),
            "matchday": m.get("matchday"),
            "leg": (m.get("group") or None),
            "home": home,
            "away": away,
            # fullTime in football-data v4 already includes extra time when played.
            "homeScore": ft.get("home"),
            "awayScore": ft.get("away"),
            "regHome": reg.get("home"),
            "regAway": reg.get("away"),
            "etHome": et.get("home"),
            "etAway": et.get("away"),
            "penHome": pen.get("home"),
            "penAway": pen.get("away"),
            "duration": score.get("duration"),
            "winner": score.get("winner"),
        })
    matches.sort(key=lambda x: (x["utcDate"] or ""))

    # --- standings ---------------------------------------------------------
    standings = []
    for table in raw_standings.get("standings", []):
        if table.get("type") not in (None, "TOTAL"):
            continue
        for row in table.get("table", []):
            name = resolve((row.get("team") or {}).get("name") or "")
            if not name:
                continue
            standings.append({
                "pos": row.get("position"),
                "team": name,
                "played": row.get("playedGames"),
                "won": row.get("won"),
                "draw": row.get("draw"),
                "lost": row.get("lost"),
                "gf": row.get("goalsFor"),
                "ga": row.get("goalsAgainst"),
                "gd": row.get("goalDifference"),
                "pts": row.get("points"),
            })
        break  # single league-phase table
    standings.sort(key=lambda r: r["pos"] or 99)

    out = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": "2026/27",
        "source": "football-data.org",
        "draft": DRAFT,
        "standings": standings,
        "matches": matches,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    finished = sum(1 for m in matches if m["status"] == "FINISHED")
    print(f"Wrote data.json — {len(matches)} matches ({finished} finished), "
          f"{len(standings)} in table.")


if __name__ == "__main__":
    main()
