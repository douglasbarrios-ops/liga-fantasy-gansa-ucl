# Liga Fantasy — Champions League 2026/27

A self-updating scoreboard for a 9-manager, 36-club draft league. After setup it
runs itself: a scheduled job pulls results from an API, recomputes every point,
and republishes the page. Nothing to enter by hand, all season.

```
football-data.org  ──►  update_data.py  ──►  data.json  ──►  index.html
   (results API)      (GitHub Actions,        (committed        (static page
                       every 10 min)          to the repo)       your managers open)
```

Three moving parts, all free, no server:

- **`update_data.py`** — fetches fixtures and the league table, normalises them, writes `data.json`. Computes no fantasy points.
- **`index.html`** — the whole scoring engine plus the interface. One file. Reads `data.json` at page load.
- **`.github/workflows/update.yml`** — the cron that runs the fetcher and commits the result.

Keeping the scoring in the page rather than the fetcher means there is exactly
one place to edit if you ever adjust a rule mid-season, and every manager sees
the change on their next refresh.

---

## Setup — about 15 minutes, once

**1. Get an API token.** Register at <https://www.football-data.org/client/register>.
The free tier covers the Champions League and allows 10 requests a minute; this
project uses two per run.

**2. Create the repo.** Make a **public** GitHub repository and upload these four
files, keeping the folder structure:

```
index.html
update_data.py
data.json          ← optional; the page handles its absence
.github/workflows/update.yml
```

Public matters for two reasons: GitHub Pages is free on public repos, and so are
unlimited Actions minutes.

**3. Add the token.** Repo → Settings → Secrets and variables → Actions → New
repository secret. Name it exactly `FOOTBALL_DATA_TOKEN`, paste the token as the
value. It never appears in the page or the repo.

**4. Turn on Pages.** Settings → Pages → Source: *Deploy from a branch* →
`main` / `/ (root)` → Save. Your URL will be
`https://<your-user>.github.io/<repo-name>/`. Send that to the nine managers.

**5. Run it once by hand.** Actions tab → *Actualizar resultados* → Run workflow.
Watch it finish green.

That last step is the real setup. `update_data.py` refuses to write anything if
it cannot match every club the API mentions to a club in the draft — it prints
the unmatched names and exits with an error. If it passes once, the name mapping
is proven for the whole season and the pipeline is genuinely hands-off from
there. If it fails, add the offending fragment to the `ALIASES` list at the top
of the script and re-run.

---

## Two rule calls I had to make

Your rules were clear on everything except two edges. Both are one-line changes
in the `RULES` block at the top of the `<script>` in `index.html`.

**Extra time counts toward the match result.** A knockout leg that finishes 1–1
after ninety minutes and 2–1 after extra time is scored as a win. Set
`extraTimeCounts: false` to score on the ninety-minute result instead.

**A shootout still earns the playoff bonus.** No points for winning the shootout
itself — but a club that survives the 9–24 playoff on penalties has reached the
round of 16, so it gets the `+1`. If your table meant to withhold the bonus in
that case, remove the shootout branch in `playoffWinners()`.

Everything else follows your summary exactly: 3/1/0 in the league phase, +3 for
the top eight, +1 for ninth through twenty-fourth, +1 for surviving the playoff,
no points from the two playoff legs, 3/1/0 from the round of sixteen onward, and
no further bonuses for advancing.

The maximum a single club can score is 48: 24 in the league phase, 3 for a top-8
finish, and 21 across seven knockout matches.

---

## What managers see

Before matchday 1 the page shows the draft with zeros and a line explaining that
results will appear on their own — no broken layout, no error.

The standings are the page. Each manager's row carries a four-segment bar showing
how their total splits across their four clubs, so a table carried by one club
looks different at a glance from a balanced one. Tapping a row opens the
per-club breakdown: league-phase position, league points, bonus, knockout points.
Before matchday 8 the bonus column is shown dimmed, because it is provisional
until the final table is set. Below that, all 36 clubs in table order, with the
8th and 24th cut lines drawn in and the owner of each club named.

Matches in play surface in a strip at the top with both managers named.

---

## Changing something later

| Change | Where |
|---|---|
| A rule (points, bonuses, extra time) | `RULES` in `index.html` |
| A club's display name | `DRAFT` and `ALIASES` in `update_data.py`, and `EMPTY_DRAFT` in `index.html` |
| How often it refreshes | the `cron` lines in `update.yml` |
| Colours, layout, copy | the `<style>` block in `index.html` |

The draft is duplicated in two places on purpose: `update_data.py` is the source
of truth and writes it into `data.json`, while `EMPTY_DRAFT` in `index.html` is
only the fallback shown if `data.json` has not been generated yet.

---

## Things worth knowing

**Scheduled workflows go dormant after 60 days without repository activity.**
This one commits `data.json` whenever a result changes, which counts as activity,
so it stays awake through the season on its own. If a long gap ever does disable
it, GitHub emails you and one click in the Actions tab brings it back.

**GitHub cron is best-effort.** During busy periods a run can be a few minutes
late. Live scores may lag the television by a few minutes; final results are
reliable.

**If the API ever goes down,** `data.json` is a plain readable file in the repo.
You can edit a score in it directly and the page will reflect it — an escape
hatch you will probably never need.

**Testing.** `simulate.py` generates a complete fake season into `data.json` so
you can see how the page looks with a champion crowned. Run `python simulate.py`,
open the page, then delete `data.json` and let the workflow rebuild the real one.
`test_engine.js` runs the scoring engine straight out of `index.html` against that
fake season and checks the totals add up — worth running (`node test_engine.js`)
if you ever change a rule.
