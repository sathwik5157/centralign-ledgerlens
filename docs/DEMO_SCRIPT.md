# Demo narration and reproduction

The supplied recording uses the running application and actual browser actions. On-screen captions explain each segment. There is no synthetic voiceover. The recording harness supplies clicks, typing and the example human approval, while the backend performs the task. All data is fictional.

## Suggested narration

**Introduction:** “This is LedgerLens, a financial research worker. I chose a data analytics workflow: extract numbers, normalize units, calculate metrics and save a verified research record. This demo uses fictional reports and a rule-based controller, so it runs without an API key.”

**Aurora:** “I am giving the worker the end goal rather than individual steps. It chooses FY2026 as the latest catalog report. The primary file is missing, so it logs the failed read and chooses the next approved report. Revenue becomes 1,250 million and net profit becomes 150 million. Margin is 12 percent and growth is 25 percent. It writes the record and checks it by reading it back.”

**Rerun:** “I can run the same task again. There is still one record because the company and period form a unique key. The second write is a no-op.”

**Beacon:** “These two reports disagree. The worker stops before saving, shows 800 versus 810 million in revenue, and asks for a source choice. I inspect the primary report and give an explicit approval reason. It records the decision, resumes and verifies the final record.”

**Cedar:** “This request asks for analysis without saving. The worker converts lakh to million and correctly keeps a negative profit. Sales growth is positive even though the company has a loss. The database record count stays unchanged.”

**Clarification:** “If I leave out the company, the worker asks for it instead of guessing. The full audit contains tools, observations, failed attempts, source hashes and verification results.”

**Close:** “The implementation is intentionally narrow. Its default language grammar, report schema and decision rules are fixed. My next steps are evaluated model interpretation, one authorized real-source connector, and authenticated approvals with staged writes.”

## Reproduce the browser checks and recording

Optional developer dependencies: Node.js plus Playwright. Install Playwright locally using `npm install --no-save playwright`, then run `npx playwright install chromium ffmpeg`. In one terminal start `python server.py --port 8766 --db data/demo-new.db` with a fresh database filename. In another terminal run `node scripts/record_demo.cjs`.

On a machine using installed Edge instead of Playwright Chromium, set `BROWSER_CHANNEL=msedge`. `DEMO_URL` can override the default `http://127.0.0.1:8766`. `PLAYWRIGHT_MODULE` may identify an installed Playwright package if it is not resolvable normally. The harness requires a fresh database to make record-count assertions meaningful.

The browser assertions are real UI checks. Delays in the harness give the viewer time to read captions; they do not simulate backend execution. Raw recording files go into the ignored raw-video directory. The final recording and evidence snapshots go into `artifacts`.
