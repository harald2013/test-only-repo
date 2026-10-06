from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

HOST = "0.0.0.0"
PORT = 8000
BODY = b"Hello World Version 1"
HEALTH_PATH = "/health"
HEALTH_BODY = b"ok"
CONTENT_TYPE = "text/plain; charset=utf-8"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = HEALTH_BODY if urlparse(self.path).path == HEALTH_PATH else BODY
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE)
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    HTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
