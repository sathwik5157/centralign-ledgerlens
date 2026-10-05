"""Loopback-only review UI and API. Not an authenticated production server."""
import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from worker import ROOT, Worker


def make_server(port=8765, db=None):
    worker = Worker(db)

    def launch(run_id):
        threading.Thread(target=worker.run, args=(run_id,), daemon=True).start()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, value, status=200, content_type="application/json"):
            raw = json.dumps(value).encode() if content_type == "application/json" else value
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = urlparse(self.path).path
            try:
                if path == "/":
                    return self.send((ROOT / "web/index.html").read_bytes(), content_type="text/html; charset=utf-8")
                if path == "/api/state":
                    return self.send({"runs": worker.store.all_runs(), "records": worker.store.all_records(), "policy": worker.policy})
                if path.startswith("/api/runs/"):
                    return self.send(worker.store.get_run(path.split("/")[-1]))
                if path.startswith("/sources/"):
                    relative = path[len("/sources/"):]
                    # Show source as text so embedded HTML cannot act on the local app.
                    return self.send(worker.source_path(relative).read_bytes(), content_type="text/plain; charset=utf-8")
                self.send({"error": "Not found"}, 404)
            except (KeyError, OSError, ValueError) as exc:
                self.send({"error": str(exc)}, 404)

        def do_POST(self):
            try:
                origin = self.headers.get("Origin")
                if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
                    return self.send({"error": "Cross-origin writes are not allowed"}, 403)
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    return self.send({"error": "JSON required"}, 415)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    return self.send({"error": "Body must be 1–8192 bytes"}, 400)
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("JSON object required")
                path = urlparse(self.path).path
                if path == "/api/runs":
                    state = worker.create(body.get("task"))
                    launch(state["id"])
                    return self.send(state, 201)
                if path.endswith("/approve") and path.startswith("/api/runs/"):
                    state = worker.approve(path.split("/")[3], body.get("approved"), body.get("reason"), body.get("source"))
                    if state["status"] == "running":
                        launch(state["id"])
                    return self.send(state)
                if path.endswith("/resume") and path.startswith("/api/runs/"):
                    state = worker.store.get_run(path.split("/")[3])
                    if state["status"] != "running":
                        raise ValueError("Only an interrupted running task can resume")
                    launch(state["id"])
                    return self.send(state)
                self.send({"error": "Not found"}, 404)
            except (ValueError, KeyError, TypeError) as exc:
                self.send({"error": str(exc)}, 400)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.worker = worker
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default=None)
    args = parser.parse_args()
    app = make_server(args.port, args.db)
    print(f"LedgerLens: http://127.0.0.1:{app.server_port}", flush=True)
    try:
        app.serve_forever()
    except KeyboardInterrupt:
        app.server_close()
