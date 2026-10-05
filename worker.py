"""LedgerLens: an observable, bounded autonomous worker for a sandbox workflow.

No model decides whether a database write succeeded. Tool outputs and independent
read-back checks decide that. The optional model only proposes a task contract.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
TERMINAL = {"completed", "failed", "rejected", "needs_input", "awaiting_approval"}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class Clarification(ValueError):
    pass


class ConcurrentChange(ValueError):
    pass


class TableReader(HTMLParser):
    """Read only data cells, never execute scripts or instructions in reports."""
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], [], None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        if tag == "td":
            self.cell = ""

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.row.append(self.cell.strip())
            self.cell = None
        if tag == "tr" and self.row:
            self.rows.append(self.row)


def number(value):
    text = value.strip().replace(",", "")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric value: {value}") from exc
    if not result.is_finite() or abs(result) > Decimal("1e15"):
        raise ValueError("Non-finite or out-of-range number")
    return result


def rounded(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def extract_report(text, company, period):
    parser = TableReader()
    parser.feed(text)
    fields = {}
    for row in parser.rows:
        if len(row) == 2:
            key, value = row
            if key in fields:
                raise ValueError(f"Duplicate field: {key}")
            fields[key] = value
    required = {"Company", "Period", "Prior period", "Unit", "Revenue", "Net profit", "Prior revenue"}
    if not required <= fields.keys():
        raise ValueError("Missing required fields: " + ", ".join(sorted(required - fields.keys())))
    if fields["Company"] != company or fields["Period"] != period:
        raise ValueError("Company or reporting period does not match the task")
    if fields["Prior period"] != f"FY{int(period[2:]) - 1}":
        raise ValueError("Prior revenue is not from the preceding fiscal year")
    factors = {"INR million": Decimal(1), "INR crore": Decimal(10), "INR lakh": Decimal("0.1")}
    if fields["Unit"] not in factors:
        raise ValueError("Unsupported unit or currency")
    factor = factors[fields["Unit"]]
    revenue, profit, prior = [number(fields[k]) * factor for k in ("Revenue", "Net profit", "Prior revenue")]
    if revenue <= 0 or prior < 0:
        raise ValueError("Revenue must be positive and prior revenue cannot be negative")
    return {
        "company": company, "period": period, "unit": "INR million",
        "revenue": rounded(revenue), "net_profit": rounded(profit), "prior_revenue": rounded(prior),
        "net_margin_pct": rounded(profit / revenue * 100),
        "revenue_growth_pct": rounded((revenue / prior - 1) * 100) if prior else None,
        "source_unit": fields["Unit"], "raw_fields": fields,
    }


def values(report):
    return {k: report[k] for k in ("company", "period", "unit", "revenue", "net_profit", "prior_revenue", "net_margin_pct", "revenue_growth_pct")}


def parse_task(task, policy):
    """Conservative supported-language grammar. Ambiguity always stops writes."""
    text = task.lower()
    if re.search(r"\b(delete|email|send|pay|transfer|quarter|quarterly|usd|dollar|forecast)\b", text):
        raise Clarification("Supported scope: annual INR financial research, summary, or save. Remove unsupported actions or specify a supported task.")
    companies = [key for key, c in policy["companies"].items()
                 if any(re.search(r"\b" + re.escape(alias) + r"\b", text) for alias in c["aliases"])]
    if len(companies) != 1:
        raise Clarification("Specify exactly one company: Aurora Retail, Beacon Software, or Cedar Logistics.")
    if not re.search(r"\b(revenue|profit|financial|results|margin|research|report|metrics|growth)\b", text):
        raise Clarification("Specify a financial research task, for example: Research Aurora's latest revenue and profit and save it.")
    years = set(re.findall(r"\b(?:fy\s*)?(20\d{2})\b", text))
    if len(years) > 1:
        raise Clarification("Specify one fiscal year, or ask for the latest annual report.")
    readonly = bool(re.search(r"read[ -]?only|(?:don['’]?t|do not|never|must not|should not|no need to)\s+(?:save|store|write|enter|record|upsert)|without\s+(?:saving|writing|storing)", text))
    # 'Record' alone can be a noun (e.g. 'show the research record'), not write permission.
    write = bool(re.search(r"\b(save|store|enter|upsert|write)\b", text)) and not readonly
    return {"company": companies[0], "period": "FY" + next(iter(years)) if years else "latest", "write": write}


def model_contract(task, baseline, policy):
    """Optional Ollama adapter. Validated suggestions cannot broaden permission.

    A model is optional because the recorded no-key demo must be reproducible.
    This is intentionally not advertised as unrestricted LLM planning.
    """
    model = os.environ.get("OLLAMA_MODEL")
    if not model:
        return baseline, "bounded grammar (no LLM call)"
    schema = {"type": "object", "properties": {
        "company": {"type": "string", "enum": list(policy["companies"])},
        "period": {"type": "string"}, "write": {"type": "boolean"}},
        "required": ["company", "period", "write"], "additionalProperties": False}
    body = {"model": model, "stream": False, "format": schema,
            "messages": [{"role": "system", "content": "Extract the requested company, fiscal period (FY2026 or latest), and explicit permission to save. Summary alone is read-only. Return JSON only."}, {"role": "user", "content": task}],
            "options": {"temperature": 0}}
    request = Request("http://127.0.0.1:11434/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urlopen(request, timeout=45) as response:
        proposal = json.loads(json.loads(response.read())["message"]["content"])
    if (not isinstance(proposal, dict) or set(proposal) != set(baseline) or type(proposal["write"]) is not bool
            or proposal != baseline):
        raise Clarification("Model interpretation disagreed with the safe parser. Rephrase the task with company, period, and whether to save.")
    return proposal, f"Ollama {model}, grammar validated"


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript("""
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, body TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS records (
                company TEXT, period TEXT, body TEXT NOT NULL, version TEXT NOT NULL,
                PRIMARY KEY(company, period));
            """)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save_run(self, state):
        state["updated_at"] = now()
        with self.connect() as con:
            con.execute("INSERT OR REPLACE INTO runs VALUES (?,?)", (state["id"], json.dumps(state)))

    def get_run(self, run_id):
        with self.connect() as con:
            row = con.execute("SELECT body FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise KeyError("Run not found")
        return json.loads(row[0])

    def all_runs(self):
        with self.connect() as con:
            return [json.loads(r[0]) for r in con.execute("SELECT body FROM runs ORDER BY rowid DESC LIMIT 50")]

    def read_record(self, company, period):
        with self.connect() as con:
            row = con.execute("SELECT body,version FROM records WHERE company=? AND period=?", (company, period)).fetchone()
        return {"data": json.loads(row[0]), "version": row[1]} if row else None

    def all_records(self):
        with self.connect() as con:
            return [json.loads(r[0]) for r in con.execute("SELECT body FROM records ORDER BY company,period")]

    def write_record(self, record, expected_version):
        # BEGIN IMMEDIATE plus compare-and-swap prevents a stale approval overwriting new data.
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            key = (record["company"], record["period"])
            old = con.execute("SELECT body,version FROM records WHERE company=? AND period=?", key).fetchone()
            if old and values(json.loads(old[0])) == values(record):
                return "already present"
            if (old[1] if old else None) != expected_version:
                raise ConcurrentChange("Record changed since it was checked; approval must be reconsidered")
            con.execute("INSERT OR REPLACE INTO records VALUES (?,?,?,?)", (*key, json.dumps(record), digest(record)))
        return "saved"


class Worker:
    def __init__(self, db=None, root=ROOT):
        self.root = Path(root)
        self.store = Store(db or self.root / "data" / "ledgerlens.db")
        self.policy = json.loads((self.root / "config/company_policy.json").read_text())
        if self.policy["canonical_unit"] != "INR million":
            raise ValueError("This version supports INR million as its canonical unit")
        self.lock = threading.RLock()

    def create(self, task):
        if not isinstance(task, str) or not 1 <= len(task.strip()) <= 2000:
            raise ValueError("Task must contain 1–2000 characters")
        state = {"id": uuid.uuid4().hex[:12], "task": task.strip(), "status": "running",
                 "created_at": now(), "events": [], "attempted": [], "reports": [],
                 "approvals": [], "steps": 0, "policy": self.policy}
        self.store.save_run(state)
        return state

    def event(self, s, tool, reason, output, ok=True):
        s["events"].append({"sequence": len(s["events"]) + 1, "time": now(), "tool": tool,
                            "reason": reason, "ok": ok, "observation": output})

    def next_action(self, s):
        if "intent" not in s:
            return "understand", "Identify company, reporting period and permitted outcome"
        if "sources" not in s:
            return "discover_sources", "Find the latest eligible annual report in the approved catalog"
        pending = [p for p in s["sources"] if p not in s["attempted"]]
        if pending:
            return "read_report", "Read the next approved source; use another source after a failed read"
        if "candidate" not in s:
            return "validate", "Compare normalized figures and detect conflicting source values"
        if not s["intent"]["write"]:
            return "verify_summary", "Re-read the evidence and validate the requested read-only result"
        if "existing" not in s:
            return "inspect_record", "Check existing data before writing to the research system"
        if not s.get("written"):
            return "save_record", "Apply the company write policy and save idempotently"
        return "verify_record", "Re-open stored data and source files before declaring success"

    def step(self, run_id):
        with self.lock:
            s = self.store.get_run(run_id)
            if s["status"] != "running":
                return s
            if s["steps"] >= s["policy"]["max_actions"]:
                s.update(status="failed", message="Action budget exhausted; inspect the event log.")
                self.store.save_run(s)
                return s
            tool, reason = self.next_action(s)
            s["steps"] += 1
            try:
                output = getattr(self, "tool_" + tool)(s)
                self.event(s, tool, reason, output)
            except Clarification as exc:
                s.update(status="needs_input", message=str(exc))
                self.event(s, tool, reason, str(exc), False)
            except ConcurrentChange as exc:
                s.pop("existing", None)
                s.pop("overwrite_allowed", None)
                self.event(s, tool, reason, str(exc), False)
            except (ValueError, OSError, KeyError, sqlite3.Error) as exc:
                # Reads can recover via a different approved source. Other failures stop safely.
                if tool != "read_report":
                    s.update(status="failed", message=f"{tool}: {exc}")
                self.event(s, tool, reason, f"{type(exc).__name__}: {exc}", False)
            self.store.save_run(s)
            return s

    def run(self, run_id):
        while True:
            state = self.step(run_id)
            if state["status"] != "running":
                return state

    def tool_understand(self, s):
        baseline = parse_task(s["task"], s["policy"])
        intent, mode = model_contract(s["task"], baseline, s["policy"])
        s["intent"], s["parser_mode"] = intent, mode
        s["plan"] = ["Discover approved sources", "Read and normalize annual metrics", "Resolve data conflicts"]
        s["plan"] += ["Check write permissions and existing record", "Save to SQLite", "Read back and verify"] if intent["write"] else ["Verify source evidence", "Return read-only summary"]
        return {"intent": intent, "mode": mode, "plan": s["plan"]}

    def tool_discover_sources(self, s):
        catalog = json.loads((self.root / "fixtures/catalog.json").read_text())
        intent = s["intent"]
        eligible = [r for r in catalog if r["company"] == intent["company"]]
        if intent["period"] != "latest":
            eligible = [r for r in eligible if r["period"] == intent["period"]]
        if not eligible:
            raise Clarification("No approved report exists for that company and fiscal year. Choose another year or latest.")
        latest = max(eligible, key=lambda r: (r["period"], r["published"]))
        s["period"], s["sources"] = latest["period"], latest["paths"]
        return {"period": s["period"], "paths": s["sources"], "scope": "Latest within the fictional sandbox catalog; not the public internet"}

    def source_path(self, relative):
        base = (self.root / "fixtures").resolve()
        path = (base / relative).resolve()
        if not path.is_relative_to(base) or path.suffix != ".html":
            raise ValueError("Source is outside the approved HTML directory")
        return path

    def tool_read_report(self, s):
        source = next(p for p in s["sources"] if p not in s["attempted"])
        s["attempted"].append(source)
        raw = self.source_path(source).read_bytes()
        if len(raw) > 1_000_000:
            raise ValueError("Source exceeds 1 MB limit")
        report = extract_report(raw.decode("utf-8"), s["intent"]["company"], s["period"])
        report.update(source=source, sha256=hashlib.sha256(raw).hexdigest())
        s["reports"].append(report)
        return report

    def pause(self, s, kind, message):
        s.update(status="awaiting_approval", pending={"kind": kind, "message": message}, message=message)
        return s["pending"]

    def tool_validate(self, s):
        if not s["reports"]:
            raise ValueError("All approved sources failed. No figures will be invented or saved.")
        first = s["reports"][0]
        if any(values(r) != values(first) for r in s["reports"][1:]) and "chosen_source" not in s:
            return self.pause(s, "source_conflict", "Sources disagree. Select the report to use and explain why, or reject the task.")
        chosen = s.get("chosen_source", first["source"])
        report = next(r for r in s["reports"] if r["source"] == chosen)
        s["candidate"] = {**values(report), "source": report["source"], "sha256": report["sha256"]}
        return {"candidate": s["candidate"], "warnings": ["Growth is undefined when prior revenue is zero"] if report["revenue_growth_pct"] is None else []}

    def tool_inspect_record(self, s):
        c = s["candidate"]
        s["existing"] = self.store.read_record(c["company"], c["period"])
        return s["existing"] or {"record": "not present"}

    def tool_save_record(self, s):
        existing, candidate = s["existing"], s["candidate"]
        if not existing and not s["policy"]["allow_new_records"] and not s.get("new_allowed"):
            return self.pause(s, "new_record", "Company policy requires approval to create this research record.")
        if existing and values(existing["data"]) != values(candidate) and s["policy"]["require_approval_for_overwrite"] and not s.get("overwrite_allowed"):
            return self.pause(s, "overwrite", "An existing record has different values. Review old and proposed figures before approving replacement.")
        outcome = self.store.write_record(candidate, existing["version"] if existing else None)
        s["written"] = True
        return {"outcome": outcome, "key": [candidate["company"], candidate["period"]]}

    def verify_sources(self, s):
        report = next(r for r in s["reports"] if r["source"] == s["candidate"]["source"])
        raw = self.source_path(report["source"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != report["sha256"]:
            raise ValueError("Source changed during execution; verification failed")
        fresh = extract_report(raw.decode("utf-8"), s["intent"]["company"], s["period"])
        if values(fresh) != values(s["candidate"]):
            raise ValueError("Recomputed figures differ from the planned result")

    def finish(self, s, verified_record):
        c = s["candidate"]
        company = s["policy"]["companies"][c["company"]]["name"]
        outcome = "Saved and independently read back" if verified_record else "Verified read-only summary; no record written"
        growth = c["revenue_growth_pct"] + "%" if c["revenue_growth_pct"] is not None else "undefined (zero prior revenue)"
        s.update(status="completed", message=f"{outcome}. {company} {c['period']}: revenue {c['revenue']} and net profit {c['net_profit']} INR million; net margin {c['net_margin_pct']}%; revenue growth {growth}.")
        s["verification"] = {"source_hash_match": True, "recomputed_metrics_match": True,
                             "database_readback_match": True if verified_record else None,
                             "verified_at": now(), "record_key": [c["company"], c["period"]]}
        return {"summary": s["message"], "checks": s["verification"]}

    def tool_verify_summary(self, s):
        self.verify_sources(s)
        return self.finish(s, False)

    def tool_verify_record(self, s):
        self.verify_sources(s)
        c = s["candidate"]
        actual = self.store.read_record(c["company"], c["period"])
        if not actual or values(actual["data"]) != values(c):
            raise ValueError("Stored values differ from the requested record")
        # Idempotent no-op may retain an older evidence reference: validate that reference too.
        stored_source = self.source_path(actual["data"]["source"]).read_bytes()
        if hashlib.sha256(stored_source).hexdigest() != actual["data"]["sha256"]:
            raise ValueError("Stored record evidence no longer matches its source")
        return self.finish(s, True)

    def approve(self, run_id, approved, reason, source=None):
        with self.lock:
            s = self.store.get_run(run_id)
            if s["status"] != "awaiting_approval":
                raise ValueError("This run is not awaiting approval")
            if type(approved) is not bool or not isinstance(reason, str) or not reason.strip():
                raise ValueError("A boolean decision and a non-empty reason are required")
            kind = s["pending"]["kind"]
            if approved and kind == "source_conflict":
                if source not in [r["source"] for r in s["reports"]]:
                    raise ValueError("Select one of the observed reports")
                s["chosen_source"] = source
            if approved and kind == "overwrite":
                s["overwrite_allowed"] = True
            if approved and kind == "new_record":
                s["new_allowed"] = True
            decision = {"kind": kind, "approved": approved, "reason": reason.strip(), "source": source, "time": now()}
            s["approvals"].append(decision)
            self.event(s, "human_decision", "Apply an explicit human decision", decision)
            s["status"] = "running" if approved else "rejected"
            s["message"] = "Approved; continuing" if approved else "Rejected; no further actions taken"
            s.pop("pending")
            self.store.save_run(s)
            return s


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", help="Example: Research Aurora latest revenue and profit and save it")
    args = parser.parse_args()
    worker = Worker()
    result = worker.run(worker.create(args.task)["id"])
    print(json.dumps(result, indent=2))
