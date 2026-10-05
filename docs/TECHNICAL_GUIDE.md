# LedgerLens

An autonomous financial research and data quality worker for the CentrAlign AI Engineering Intern assignment.

Give it an outcome such as **“Find Aurora Retail's latest annual revenue and profit, calculate margin and growth, and save the research record.”** It selects approved reports, extracts and normalizes financial figures, handles missing or conflicting sources, writes to SQLite, and independently checks the saved result.

**Scope disclosure:** companies and source reports are fictional sandbox fixtures. File reads, calculations, persisted state, database writes, approvals, and verification are real. The default interpreter and controller are rule-based; no LLM is called in the supplied demo. An optional Ollama task-interpretation adapter is included, but no real-model integration run is claimed. This is a bounded autonomous workflow, not a general computer-use agent.

## Run in two commands

Install Python 3.11 or newer, open a terminal in this directory, and run:

```sh
python server.py
```

Open **http://127.0.0.1:8765** in a browser. On Windows, `py -3 server.py` or `run_windows.bat` also works if Python is installed. No pip packages, API keys, paid services, or internet access are needed for the default application.

Run the checks in another terminal:

```sh
python -m unittest discover -s tests -v
```

For a command-line-only run:

```sh
python worker.py "Research Aurora latest financial results and save them"
```

The CLI prints a full audit JSON. Use the browser for approvals. To open the same state in the browser, launch `server.py` without changing the database path.

## Try these tasks

| Task | Expected behavior |
|---|---|
| Find Aurora Retail latest revenue and profit and save them | Missing primary source -> alternate report -> calculate -> save -> verify |
| Save Aurora latest financial results again | Existing identical values -> no duplicate -> verify |
| Research Beacon Software latest financial results and save | Sources disagree: 800 vs 810 million revenue -> human source selection -> continue |
| Summarize Cedar Logistics latest financial results. Do not save | Normalize lakh to million, preserve loss, produce summary without a database write |
| Save Aurora FY2025 financial results | Select explicit annual period rather than latest |
| Find latest financial results and save them | Ask for a company; no write |

In the Beacon review, inspect both reports, select the primary report, and enter a reason such as “Checked the sandbox primary annual report; use its 800 million figure.” Approving is a human exception decision, not proof of real-world correctness. Rejecting stops the run.

Supported intent is one company, one annual period or latest, and summary or save. A new task provides clarification after `needs_input`. An interrupted `running` task can be resumed from history with **Resume interrupted run**.

## Architecture

```text
Browser task / CLI
       |
Bounded task interpreter (optional validated Ollama proposal)
       |
Task contract: company + period + read/write permission
       |
Observation-driven controller <---- persistent run state in SQLite
       |
Approved tool methods: discover -> read -> validate -> inspect -> save -> verify
       |                                     |
HTML reports + company policy         Human approval when necessary
       |
Research records + audit events + source hashes + completion evidence
```

`Worker.next_action()` chooses one tool from the current state. A failed file read changes the next source. Conflicting observations pause the run. Read-only requests bypass write tools. Existing equal records use a no-op; changed records require approval. Completion is set only after source checks and, for writes, an independent database read.

## Important decisions

- **Python standard library:** keep setup small and the complete workflow easy to debug in an interview.
- **Deterministic financial math:** use `Decimal`, explicit unit factors and two-decimal rounding. Revenue growth and profit margin are calculated in code, never invented by a model.
- **SQLite:** durable records and resumable task state without a separate database service. Each database connection closes explicitly, including on errors.
- **Bounded autonomy:** one business workflow, configured source allowlist, a finite tool set and a 24-action budget. This makes decisions inspectable.
- **Evidence before completion:** SHA-256 identifies the exact file version. Verification re-reads files, recalculates results, and compares saved values. Hashes show consistency, not authenticity.
- **Idempotency and concurrency:** `(company, period)` is the record key. A transaction and version check prevent overwriting a record that changed after inspection. A retried identical write is harmless.
- **Human control:** source conflicts, policy-restricted new records and changed values require decisions with reasons. Approval survives a process restart.
- **Separation of permissions from language:** an optional model cannot silently expand a summary task into permission to write.

## What is real and what is configured

Real execution: source discovery from a catalog, disk reads, HTML extraction, metric calculations, exception-driven tool choices, state persistence, approval handling, SQL writes, read-back checks, audit download.

Configured: three fictional companies, report catalog, supported table labels, annual INR scope, parsing vocabulary, decision rules, policy defaults, and a deliberately absent source plus a deliberately conflicting report. The failure scenarios are deliberately set up; their errors and recovery are real.

The UI is an actual local company application. The worker uses its file and database tools; it does not move a mouse or automate arbitrary websites. Playwright is used to verify and record the UI, not as the worker's execution engine.

## Files

| File | Purpose |
|---|---|
| `worker.py` | Interpreter, tool methods, controller, store, optional model adapter |
| `server.py` | Loopback HTTP API and background execution |
| `web/index.html` | Task UI, review controls, audit history and research table |
| `config/company_policy.json` | Company aliases, permissions and action budget |
| `fixtures/` | Fictional annual reports and approved catalog |
| `tests/test_worker.py` | Functional, reliability, data-quality and API checks |
| `docs/ARCHITECTURE.md` | State, permissions, recovery and production design |
| `docs/DEMO_SCRIPT.md` | Narration and reproduction steps |
| `artifacts/demo.webm` | Recorded working browser demo |
| `artifacts/evidence/` | Actual run JSON and browser-check result |

## Models and dependencies

Runtime: Python 3.11+ with `sqlite3`, `http.server`, `html.parser`, `decimal`, `urllib`, and other standard modules; vanilla HTML/CSS/JavaScript. No runtime framework or external service is required.

Optional: install Ollama separately, download a model suitable for your computer, set `OLLAMA_MODEL` to its exact installed name, then start the server. The adapter calls `http://127.0.0.1:11434/api/chat` with JSON-schema output. The safe grammar must still understand the request, and the proposal must match it. This adapter is intentionally conservative; it does not make the system an unrestricted language agent. A model outage or disagreement does not silently switch execution modes. Adapter permission validation is tested with a stub; real model quality, latency and availability are unverified.

Development/demo tools: Python `unittest`; Playwright for actual browser interaction and recording; ReportLab for the handbook. These are not application runtime dependencies. AI assistance: OpenAI Codex/ChatGPT generated and revised code, tests, documentation, and demo tooling. No pre-existing agent application or agent framework was copied.

Reference documentation: [Ollama chat API](https://docs.ollama.com/api/chat), [Playwright video recording](https://playwright.dev/docs/videos), [Python SQLite](https://docs.python.org/3/library/sqlite3.html), [Python Decimal](https://docs.python.org/3/library/decimal.html).

## Assumptions and limitations

1. “Latest” means the highest fiscal year and publication date in the approved sandbox catalog. It is not a claim about current financial information on the web.
2. Sources use a small, known HTML table format and comparable consolidated annual periods. Arbitrary PDFs, scanned reports, quarterly results, FX and restatements are outside scope.
3. Natural-language support is conservative and limited. Unrecognized paraphrases may need rewriting; this is not open-ended reasoning.
4. Approvals identify a local human decision but have no login, role identity, or tamper-proof audit storage. Do not expose the server publicly as-is.
5. Single process, one local user, bounded workload. No durable distributed task queue, scheduler or multi-tenant isolation.
6. Source content is untrusted. The parser reads known fields; it does not obey source prose. The current protection is narrow and is not a general prompt-injection guarantee.
7. A failed post-write verification marks the run failed but does not automatically roll back the record. The audit supports investigation; production needs staged records and quarantine.
8. Policy is snapshotted for each run. Later policy revocation does not retroactively cancel existing approvals.
9. Verification reuses the extraction function. It detects file changes and storage errors but cannot detect every shared extraction bug or establish source authenticity.
10. Source and run state commits are separate. Idempotent writes cover the tested crash window; this is not a distributed exactly-once guarantee.

## Next two weeks

Days 1–3: build a labelled evaluation set covering paraphrases, report layouts, missing fields and conflicts. Establish task success, false completion, inappropriate write and recovery rates.

Days 4–6: add one authorized real-source connector with timeouts and bounded exponential backoff, plus structured PDF extraction with page citations. Keep the fixture suite.

Days 7–9: replace the narrow parser with evaluated schema-constrained model interpretation; retain policy enforcement and deterministic calculations. Add abstention and budget tracking.

Days 10–12: add authenticated approvals, staged writes, audit integrity, and a durable queue with leases and retry limits.

Days 13–14: test interruptions, concurrent tasks and malicious documents; document measured results and deploy a separate safe demo environment.

## Demo

Watch [the recorded working demo](../artifacts/demo.webm). Its browser requests and database changes are real. See [demo reproduction instructions](DEMO_SCRIPT.md) for the recording harness. The source report fixtures are fictional, and the default run does not use an LLM.
