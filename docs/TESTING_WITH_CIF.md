# Testing the Context Intelligence Framework with MedStock

MedStock is a working project in its own right, but its history was also
written so that every capability of the
[Context Intelligence Framework (CIF)](https://github.com/nagarwal00/context-engine-prototype-)
has real material to work on. This page maps each CIF feature to what in this
repository exercises it, how to run it, and what CIF produced when it was run
on this repository. The figures below come from a full live ingestion
from GitHub on 21 November 2026 (20 commits on `main`).

Nothing here is synthetic: the commits, ADRs, code and diffs are the ones in
this repository.

## What is in the history

| Material | Where | Used by CIF for |
|---|---|---|
| 18 regular commits (Conventional Commits with scopes matching module names: `scaffold`, `models`, `storage`, `dispensing`, `inventory`, `alerts`, `api`, `cli`, `adr`, `guard`, `readme`) | `git log` | Commit ingestion, decision extraction, timeline, bus factor per scope |
| 2 merge commits (`Merge branch 'feature/...'`) | `git log --merges` | Trivial-commit filtering |
| 2 real bug fixes with regression tests | `fix(storage)`, `fix(dispensing)` commits | Explanations grounded in fixes |
| 5 ADRs, one per lifecycle state | `docs/adr/` | ADR parsing, lifecycle states, alternatives, supersession, guard-rule synthesis |
| A rejected idea (FIFO) and its replacement (FEFO) | ADR-0002, ADR-0003 | Rejected-idea guard, drift detection |
| An open design conflict (polling vs WebSocket) | `medstock/api.py`, README, ADR-0005 | Conflict detection (`polling` / `websocket` pair) |
| 8 Python modules, 62 functions/methods incl. tests | `medstock/`, `tests/` | AST entity resolution (`file::function`) |
| Human-reviewed active guard rules | `cif_rules.json` | CI guard, Live CI Drift Check |
| A branch that reintroduces FIFO | `demo/fifo-regression` | Drift detection, CI guard failing on a PR |

### ADR lifecycle coverage

| ADR | Title | Status in file | State CIF parsed |
|---|---|---|---|
| 0001 | Store inventory in a single JSON file | Superseded by ADR-0004 | `superseded` |
| 0002 | Dispense batches in FIFO order | Rejected | `rejected` |
| 0003 | Dispense batches in FEFO order | Accepted | `accepted` |
| 0004 | Move inventory storage to SQLite | Accepted (supersedes ADR-0001) | `accepted` |
| 0005 | Push alerts to the dashboard over a WebSocket | Proposed | `proposed` |

Alternatives CIF extracted from the "We considered X, but Y" sentences:
`FIFO by received date` (ADR-0003) and `PostgreSQL` (ADR-0004).

## Set up with your CIF project

These steps need a CIF version that includes the ingest fixes of
21 November 2026 (repository registration, admin access for the signed-in
local user, a clear rate-limit error instead of invented commits). Paths
below assume CIF is checked out at `C:\Users\HP\Desktop\SE_project` and this
repository at `C:\Users\HP\Desktop\context-engine-repo`.

**1. Create a GitHub token.** GitHub allows only 60 unauthenticated requests
per hour *per public IP address*, shared with every other device on your
network, and one ingestion of this repository needs about 35. On a shared
campus or office network the quota is often already used up. Create a token
at https://github.com/settings/tokens (classic, no scopes needed for a public
repository) and add this line to CIF's `.env` file:

```
GITHUB_TOKEN=<your token>
```

`server.py` reads `.env` on start. Alternatively paste the token into the
token field of the ingest dialog each time.

**2. Start CIF.** Keep `CIF_DEV_MODE=1` in `.env` for local ingestion.

```powershell
cd C:\Users\HP\Desktop\SE_project
```

```powershell
python server.py
```

Open http://127.0.0.1:8080/ and sign in (Sign in as Demo Developer is fine).

**3. Ingest this repository.** Workspace (top bar) → paste
`https://github.com/nagarwal00/context-engine-repo` → Connect → Ingest &
Extract Context. Leave "Start with Empty Dashboard" ticked to see only this
repository, or untick it to keep the pilot demo data.

**4. Load the guard rules and run reconciliation.** Ingestion creates no
guard rules and does not run conflict or supersession detection. In a second
terminal:

```powershell
cd C:\Users\HP\Desktop\context-engine-repo
```

```powershell
python tools/cif_setup.py --engine C:\Users\HP\Desktop\SE_project
```

It adds the three rules from `cif_rules.json` as *proposed* and records the
conflict and supersession candidates. Add `--activate` to skip the approval
step.

**5. Use the dashboard.** Refresh the page and pick
`nagarwal00/context-engine-repo` in the Repository selector. In Review Queue
press **Approve (Enforce in CI)** on the three MedStock rules. Then open Live
CI Drift Check, paste the diff from section 6 below and run it.

**Live GitHub Pages site:** https://nagarwal00.github.io/context-engine-prototype-/
ingests commits and the file tree only, in the browser, and needs the same
token once the shared quota is used up. ADRs, guard rules, conflicts and the
review queue need the local server.

## Feature-by-feature

### 1. Multi-source ingestion and evidence grounding
- **Input:** commits, tree, Python files and `docs/adr/*.md`.
- **Observed:** all 20 commits and all 5 ADRs ingested (25 events), 34 file
  and 43 function entities, 24 decisions, 122 graph edges. Every decision
  links to a real commit or ADR URL.
- **Where to look:** Evidence Panel, Project Timeline.

### 2. AST entity resolution
- **Observed:** entities such as `medstock/dispensing.py::fefo_order`,
  `medstock/storage.py::apply_dispense`, `medstock/cli.py::import_csv`.
- **Where to look:** Code-Context View.

### 3. Decision lifecycle
- **Observed:** all five ADR states in the table above.
- **Where to look:** Decision Explorer, filtered by state.

### Reconciliation (needed for sections 4 and 5)
Ingestion does not run conflict or supersession detection, and no server
route or UI button calls it (only `run_demo.py` does). Setup step 4
(`tools/cif_setup.py`) runs it.

### 4. Conflict detection
- **Observed (after reconciliation):** `polling vs websocket` between ADR-0005 (proposes WebSocket
  push) and the README commit (documents 30-second polling of `GET /alerts`).
  This is a real open design question.
- **Where to look:** Context Graph (`conflicts_with` edge), Review Queue
  (`conflict` item).

### 5. Supersession
- **Observed (after reconciliation):** 4 supersession candidates, for
  example "Persist inventory in a single JSON file (ADR-0001)" and the SQLite
  migration being followed by later storage changes. See behaviour 2 below
  for one false positive.
- **Where to look:** Context Graph (`supersedes` edges), Review Queue
  (`supersession_candidate` items).

### 6. Guard rules and drift detection
`cif_rules.json` holds three rules, each citing the decision ID CIF
generated for the ADR it enforces:

| Rule | Enforces | Blocks |
|---|---|---|
| `rule_forbid_fifo_sort_dispensing` | ADR-0003 | Sorting batches by `received_on` in `medstock/dispensing.py` |
| `rule_forbid_fifo_name_dispensing` | ADR-0002 | A `fifo*` ordering helper in `medstock/` |
| `rule_forbid_postgres_driver` | ADR-0004 | `import psycopg2` in `medstock/` |

CIF also synthesises rules automatically, but only as *proposed*. On this
repository the synthesised set was too broad (for example it proposed
forbidding `received_on` everywhere), which is why the active rules were
written by hand. That is CIF's intended review step.

**Live CI Drift Check:** paste this diff (the change on the
`demo/fifo-regression` branch):

```diff
--- a/medstock/dispensing.py
+++ b/medstock/dispensing.py
@@ -24,7 +24,8 @@ def fefo_order(batches: Iterable[Batch], today: date) -> List[Batch]:
     batch number so the order is deterministic.
     """
     usable = [b for b in batches if b.quantity > 0 and not b.is_expired(today)]
-    return sorted(usable, key=lambda b: (b.expiry_date, b.batch_no))
+    # Simpler for counter staff: FIFO, oldest delivery first.
+    return sorted(usable, key=lambda b: (b.received_on, b.batch_no))
```

- **Observed with the rules approved:** `drift_detected: true`, a finding
  for `rule_forbid_fifo_sort_dispensing` at `medstock/dispensing.py` line 28
  with signal strength `high`, and two advisory rejected-idea findings (both
  tier `strong`).
- **Clean change:** a diff that only changes `DEFAULT_EXPIRY_WINDOW_DAYS` in
  `medstock/alerts.py` gives `drift_detected: false`.

### 7. CI guard on pull requests
`.github/workflows/cif-guard.yml` checks out CIF and runs
`tools/cif_guard.py` on every pull request into `main`. To see it fail for
the right reason, open a pull request from `demo/fifo-regression`:

https://github.com/nagarwal00/context-engine-repo/compare/main...demo/fifo-regression

**Do not merge it.** Both the **Tests** workflow
(`test_earliest_expiry_first_even_if_received_later` fails) and the
**CIF Decision Guard** workflow (violation of
`rule_forbid_fifo_sort_dispensing`) fail on it.

Run the same check locally:

```powershell
python tools/cif_guard.py --engine <path to CIF checkout> --base main --head demo/fifo-regression
```

### 8. Evidence-grounded explanation and refusal
- `medstock/dispensing.py` → `status: grounded`, citing the
  `fix(dispensing)` commit that made dispensing atomic.
- `medstock/unknown.py` → `status: not_found` (CIF refuses rather than
  inventing an answer).
- **Where to look:** Code-Context View → "Why does this exist?".

### 9. Time travel (as-of)
- **Observed:** asking about `medstock/dispensing.py` as of 2026-01-01 returns
  no decisions (the file did not exist yet) and lists the later decisions under
  `changed_afterwards`.
- **Where to look:** Project Timeline → as-of control.

### 10. Review queue
- **Observed:** 24 `decision` items straight after ingestion; 39 items after
  reconciliation and a drift check, adding `conflict`,
  `supersession_candidate` and `drift` items.
- **Where to look:** Review Queue; confirm or reject items.

### 11. Bus factor and onboarding
- **Observed:** overall bus factor `1` across 7 modules. This is accurate:
  every commit so far has one author. Commits from a second contributor
  would change it.
- **Onboarding:** 26 checklist items generated for the repository.
- **Where to look:** Metrics, Onboarding Tour.

### 12. Browser and VS Code extensions
Not run as part of the verification. With the CIF server running
and this repository ingested:
- **Browser extension:** open the `demo/fifo-regression` pull request page on
  GitHub with the CIF extension loaded.
- **VS Code extension:** open `medstock/dispensing.py`; `fefo_order` and
  `pick_batches` are function entities CIF resolved.

## CIF behaviours this repository surfaced

These are properties of the CIF engine observed while testing, recorded so
results are read correctly:

1. **Live ingestion links each ADR decision to the first 10 paths in the
   repository tree** (here `LICENSE`, `README.md`, `cif_rules.json`, `data/`,
   ...), not to the files the ADR discusses. This is why the polling/WebSocket
   conflict is reported on a documentation entity rather than on
   `medstock/api.py`.
2. **The supersession heuristic can mark an ADR as superseded by the commit
   that implements it.** "Implement FEFO batch picking ... (ADR-0003)" was
   treated as superseding ADR-0003, so ADR-0003 appeared as `superseded` after
   reconciliation even though its file says Accepted.
3. **Fixed in CIF on 21 November 2026, found while testing with this
   repository:**
   - A 403 from GitHub crashed ingestion with `NameError: name 'datetime' is
     not defined`, and the code behind it would have invented four placeholder
     commits. It now stops with a message asking for a GitHub token.
   - Repositories ingested from the Workspace were never registered, so they
     could not be selected in the dashboard and returned 404. They are now
     registered, and the user who ingested one can review it.
   - A signed-in local user got 403 "Admin permission required" on Connect &
     Ingest. In dev mode on localhost this is now allowed.
   - Live CI Drift Check always checked the pilot demo repositories. It now
     checks the repository selected in the top bar and the files in the diff.
4. **The static GitHub Pages build ingests commits and the file tree only**
   (no ADRs, issues or pull requests). Use the local server for ADR-driven
   features.
5. **Conflict and supersession detection are not wired into the server.**
   They only appear after running `tools/cif_setup.py` (setup step 4).
6. **Issues and pull requests:** this repository has none yet apart from
   the demo PR you open. CIF's issue/PR ingestion and `Closes #N` linkage
   need issues and PRs to exist on GitHub.
