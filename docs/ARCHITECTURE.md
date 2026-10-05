# Architecture and design decisions

## Business outcome

An analyst wants a trustworthy financial research record, not a paragraph containing unverified numbers. LedgerLens performs the small data pipeline required to produce that record: discover, extract, standardize, validate, load, then verify. Each action leaves evidence.

## Components

The browser sends a task to the loopback server. The server creates a run and starts a background Python thread. `Worker.step()` loads the saved state, asks `next_action()` for the next tool, executes that tool, logs the observation, and saves a checkpoint. This repeats until completion, failure or a human boundary. A process-local lock serializes steps and approvals. SQLite transactions protect individual writes.

`parse_task()` creates a task contract with company, period and permission to save. It recognizes aliases and supported intent words. Ambiguous company/year requests stop with a clarification. A summary is read-only unless a supported explicit write verb is present and no supported negative instruction cancels it.

`model_contract()` is an optional, conservative Ollama adapter. It does not currently expand the parser's language coverage: it validates a model proposal against the safe baseline. No production model capability is implied.

`discover_sources` filters the approved catalog and chooses the requested fiscal period, or the latest catalog period. `read_report` reads HTML, checks identity/period/unit, normalizes values and retains raw fields and a hash. Missing or invalid reports are logged; the next approved source is attempted. `validate` compares the canonical figures from successful reports and pauses on disagreement.

`inspect_record` checks the existing destination. `save_record` enforces the policy and compares the observed version inside an immediate SQLite transaction. An identical record is an idempotent no-op. A changed record needs approval by default. A stale version raises `ConcurrentChange`, clearing the previous authorization before inspecting again.

`verify_record` opens a fresh database connection, re-reads the source file, compares its hash and recalculates the metrics. Only then can the run become completed. A read-only task instead uses `verify_summary` and never calls the write tool.

## State and memory

`runs(id, body)` stores task intent, policy snapshot, plan, attempted paths, extracted reports, candidate, existing record version, approval decisions, action count, and audit events. `records(company, period, body, version)` stores the research values and their source reference. The primary key provides idempotency; the version hash supports optimistic concurrency.

Company memory is explicit configuration: aliases, permitted source catalog, canonical units, write policy and action budget. Task memory is the persistent run JSON. This version does not learn new policies from feedback, use embeddings, or maintain a semantic vector memory.

## State transitions

```text
running -> needs_input          ambiguous/unsupported request
running -> awaiting_approval    source conflict or restricted write
awaiting_approval -> running    accepted decision with reason
awaiting_approval -> rejected   rejected decision
running -> failed              exhausted tools, budget or failed verification
running -> completed           all required verification passed
```

The next action is conditional rather than an unconditional sequence. For example, the source-recovery branch executes another read; a read-only task skips storage; a data conflict waits; a concurrent change returns to inspection. Tool implementations are fixed, so generalization is within the workflow rather than arbitrary task invention.

## Calculations

- INR crore × 10 = INR million; INR lakh × 0.1 = INR million.
- Net profit margin = net profit / revenue × 100.
- Revenue growth = (current revenue / prior revenue − 1) × 100.
- A loss is valid. Non-finite values, non-positive current revenue, negative prior revenue, missing/duplicate fields, unsupported units and incorrect periods are rejected.
- Zero prior revenue produces an undefined growth value, not a division error or invented percentage.
- Decimal arithmetic and explicit half-up rounding avoid binary-float surprises. Canonical values are stored as decimal strings.

## Failure and permission examples

Aurora's first configured file does not exist. Reading it produces a real `FileNotFoundError`. The controller observes that failure and attempts the next allowed report. It does not search arbitrary directories.

Beacon's reports disagree on revenue. The worker pauses before saving. The reviewer sees each source's values, selects an observed report and writes a reason. That decision is recorded and execution resumes.

If an existing destination changes while approval is pending, the version comparison fails. The worker re-reads the destination and asks again if the conflict still exists. It does not reuse an outdated overwrite authorization.

If the process stops after committing a record but before the checkpoint, the resumed write recognizes the same values and performs a no-op. This specific crash window has an automated regression test.

## Verification boundaries

A source hash proves that the same bytes were used across a run; it does not establish that a fictional or real report is true. Recomputing with the same parser is a consistency check, not independent auditing of the parser. Two disagreeing sources are not automatically resolved by majority or authority scoring. The human's decision is explicit evidence of an exception, not a truth oracle.

## Security and deployment boundary

The prototype binds to loopback, uses parameterized SQL, confines source reads to HTML files under fixtures, escapes UI text and rejects cross-origin JSON writes. No model output can request arbitrary tool calls. The app does not execute document prose. These controls fit a local demonstration; there is no user authentication, production secret management, rate limiting, tamper-resistant storage or tenant isolation. It must not be publicly hosted unchanged.

## How to extend it

A fourth company in the same annual-results schema mainly needs company aliases, an approved catalog entry and reports; the controller does not change. Supporting invoices requires a new schema, extraction and validation tools, and intent routing. A fully generic employee needs a tool registry with schemas, typed outcomes, planning contracts, resource permissions, durable jobs, connectors and independent evaluators. The current compact tool methods are a starting point, not a claim that those abstractions are already implemented.
