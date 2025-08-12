#!/usr/bin/env python3
"""
提供 /api/config  GET/POST
"""
import os, json, yaml
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

CONFIG = Path("/app/config/settings.yml")

class Handler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/config":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            with open(CONFIG, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            self.wfile.write(json.dumps(cfg, ensure_ascii=False).encode())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/config":
            length = int(self.headers["Content-Length"])
            data = json.loads(self.rfile.read(length))
            with open(CONFIG, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_error(404)

if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()