"""Generates a fake completed season into data.json so the dashboard and the
scoring engine can be tested before real results exist. Not part of the pipeline."""
import json, random, itertools
from datetime import datetime, timezone, timedelta
from update_data import DRAFT

random.seed(7)
TEAMS = [t for v in DRAFT.values() for t in v]
STRENGTH = {t: random.uniform(0.6, 2.1) for t in TEAMS}
for t in ["Bayern München","Real Madrid","Liverpool","Arsenal","Barcelona","Paris Saint-Germain"]:
    STRENGTH[t] = random.uniform(2.0, 2.6)

matches, mid = [], 1000
T0 = datetime(2026, 9, 8, 19, 0, tzinfo=timezone.utc)

def play(h, a, stage, md=None, day=0, ko=False):
    global mid
    hs = min(6, int(random.expovariate(1 / (STRENGTH[h] * 1.15))))
    as_ = min(6, int(random.expovariate(1 / STRENGTH[a])))
    mid += 1
    m = {"id": mid, "utcDate": (T0 + timedelta(days=day)).isoformat(),
         "status": "FINISHED", "stage": stage, "rawStage": stage, "matchday": md,
         "leg": None, "home": h, "away": a, "homeScore": hs, "awayScore": as_,
         "regHome": hs, "regAway": as_, "etHome": None, "etAway": None,
         "penHome": None, "penAway": None, "duration": "REGULAR",
         "winner": "HOME_TEAM" if hs > as_ else ("AWAY_TEAM" if as_ > hs else "DRAW")}
    matches.append(m)
    return m

# --- league phase: 8 matches each, 144 total ------------------------------
sched = {t: [] for t in TEAMS}
while True:
    need = sorted([t for t in TEAMS if len(sched[t]) < 8],
                  key=lambda t: (len(sched[t]), t))
    if len(need) < 2:
        break
    h = need[0]
    opp = next((t for t in need[1:] if t not in sched[h]), need[1])
    sched[h].append(opp); sched[opp].append(h)
    play(h, opp, "LEAGUE", md=len(sched[h]), day=len(sched[h]) * 20)

# --- table -----------------------------------------------------------------
st = {t: {"pts": 0, "gf": 0, "ga": 0, "w": 0, "d": 0, "l": 0, "p": 0} for t in TEAMS}
for m in matches:
    h, a, hs, as_ = m["home"], m["away"], m["homeScore"], m["awayScore"]
    for x, gf, ga in ((h, hs, as_), (a, as_, hs)):
        st[x]["p"] += 1; st[x]["gf"] += gf; st[x]["ga"] += ga
        if gf > ga: st[x]["pts"] += 3; st[x]["w"] += 1
        elif gf == ga: st[x]["pts"] += 1; st[x]["d"] += 1
        else: st[x]["l"] += 1
order = sorted(TEAMS, key=lambda t: (-st[t]["pts"], -(st[t]["gf"] - st[t]["ga"]), -st[t]["gf"]))
standings = [{"pos": i + 1, "team": t, "played": st[t]["p"], "won": st[t]["w"],
              "draw": st[t]["d"], "lost": st[t]["l"], "gf": st[t]["gf"],
              "ga": st[t]["ga"], "gd": st[t]["gf"] - st[t]["ga"], "pts": st[t]["pts"]}
             for i, t in enumerate(order)]

# --- knockout playoff (9-24), two legs ------------------------------------
po = order[8:24]
ties = [(po[i], po[15 - i]) for i in range(8)]
winners = []
for x, y in ties:
    l1 = play(y, x, "PLAYOFF", day=170); l2 = play(x, y, "PLAYOFF", day=177)
    ax = l1["awayScore"] + l2["homeScore"]; ay = l1["homeScore"] + l2["awayScore"]
    if ax == ay:
        l2["penHome"], l2["penAway"] = 4, 3
        l2["duration"] = "PENALTY_SHOOTOUT"
        winners.append(x)
    else:
        winners.append(x if ax > ay else y)

# --- R16 -> final ----------------------------------------------------------
alive = order[:8] + winners
random.shuffle(alive)
for stage, day, legs in (("R16", 190, 2), ("QF", 220, 2), ("SF", 250, 2), ("FINAL", 280, 1)):
    nxt = []
    for i in range(0, len(alive), 2):
        x, y = alive[i], alive[i + 1]
        ax = ay = 0
        for L in range(legs):
            m = play(x if L else y, y if L else x, stage, day=day + L * 7)
            ax += m["homeScore"] if m["home"] == x else m["awayScore"]
            ay += m["homeScore"] if m["home"] == y else m["awayScore"]
        nxt.append(x if ax >= ay else y)
    alive = nxt

json.dump({"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "season": "2026/27 (SIMULADO)", "source": "simulación de prueba",
           "draft": DRAFT, "standings": standings, "matches": matches},
          open("data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{len(matches)} matches, champion: {alive[0]}")
