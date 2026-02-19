"""Simple dev server for frontend with reverse proxy to backend API."""

import http.server
import urllib.request
import os
import mimetypes

PORT = 7800
BACKEND = "http://localhost:7700"
FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = "/tmp/image_gen"


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy()
        else:
            self.send_error(404)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy()
        elif self.path.startswith("/images/"):
            self._serve_image()
        else:
            super().do_GET()

    def _serve_image(self):
        """Serve images from /tmp/image_gen/."""
        filename = self.path[len("/images/"):]
        filepath = os.path.join(IMAGE_DIR, filename)
        if not os.path.isfile(filepath):
            self.send_error(404, "Image not found")
            return
        content_type, _ = mimetypes.guess_type(filepath)
        with open(filepath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=604800, immutable")
        self.end_headers()
        self.wfile.write(data)

    def _proxy(self):
        url = BACKEND + self.path
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else None

        req = urllib.request.Request(
            url,
            data=body,
            headers={k: v for k, v in self.headers.items() if k.lower() != "host"},
            method=self.command,
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                self.send_response(resp.status)
                for key, val in resp.getheaders():
                    if key.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(key, val)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_error(502, str(e))


if __name__ == "__main__":
    with http.server.HTTPServer(("0.0.0.0", PORT), ProxyHandler) as httpd:
        print(f"Frontend serving at http://localhost:{PORT}")
        print(f"Images served from {IMAGE_DIR}")
        httpd.serve_forever()
