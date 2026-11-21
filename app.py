import html
import os
import re
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


DATABASE_PATH = os.environ.get("URL_SHORTENER_DB", "urls.db")
CODE_LENGTH = 7
MAX_URL_LENGTH = 2048
CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def initialize_database(database_path=None):
    database_path = DATABASE_PATH if database_path is None else database_path
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                code TEXT PRIMARY KEY,
                destination TEXT NOT NULL
            )
            """
        )


def is_valid_url(url):
    if not isinstance(url, str) or not url or len(url) > MAX_URL_LENGTH:
        return False
    try:
        parsed = urlsplit(url)
        port = parsed.port
        return (
            parsed.scheme.lower() in ("http", "https")
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and (port is None or 0 <= port <= 65535)
        )
    except ValueError:
        return False


def shorten_url(url, database_path=None):
    if not is_valid_url(url):
        raise ValueError("Enter a valid http:// or https:// URL.")

    database_path = DATABASE_PATH if database_path is None else database_path
    with sqlite3.connect(database_path) as connection:
        for _ in range(10):
            code = secrets.token_urlsafe(5)[:CODE_LENGTH]
            try:
                connection.execute(
                    "INSERT INTO urls (code, destination) VALUES (?, ?)",
                    (code, url),
                )
                return code
            except sqlite3.IntegrityError:
                continue
    raise RuntimeError("Could not create a unique short link. Please try again.")


def get_destination(code, database_path=None):
    if not CODE_PATTERN.fullmatch(code):
        return None
    database_path = DATABASE_PATH if database_path is None else database_path
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT destination FROM urls WHERE code = ?", (code,)
        ).fetchone()
    return row[0] if row else None


class URLShortenerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/":
            body = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>URL Shortener</title>
</head>
<body>
  <main>
    <h1>URL Shortener</h1>
    <form method="post" action="/">
      <label for="url">Long URL</label>
      <input id="url" name="url" type="url" placeholder="https://example.com/page"
             maxlength="2048" required>
      <button type="submit">Shorten URL</button>
    </form>
  </main>
</body>
</html>"""
            self._send_html(200, body)
            return

        code = path.removeprefix("/")
        destination = get_destination(code)
        if destination is None:
            self._send_html(404, "<h1>Short link not found</h1>")
            return

        self.send_response(302)
        self.send_header("Location", destination)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        if self.path != "/":
            self._send_html(404, "<h1>Not found</h1>")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_html(400, "<h1>Invalid request</h1>")
            return
        if content_length <= 0 or content_length > MAX_URL_LENGTH * 3 + 100:
            self._send_html(400, "<h1>Invalid request</h1>")
            return

        form = parse_qs(self.rfile.read(content_length).decode("utf-8", "replace"))
        url = form.get("url", [""])[0].strip()
        try:
            code = shorten_url(url)
        except ValueError as error:
            self._send_html(400, f"<h1>{html.escape(str(error))}</h1>")
            return

        scheme = self.headers.get("X-Forwarded-Proto", "http").split(",", 1)[0]
        if scheme not in ("http", "https"):
            scheme = "http"
        short_url = f"{scheme}://{self.headers.get('Host', 'localhost')}/{code}"
        body = (
            "<h1>Your short link is ready</h1>"
            f'<p><a href="{html.escape(short_url, quote=True)}">'
            f"{html.escape(short_url)}</a></p>"
            '<p><a href="/">Shorten another URL</a></p>'
        )
        self._send_html(201, body)

    def _send_html(self, status, body):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)


def main():
    initialize_database()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), URLShortenerHandler)
    print(f"URL shortener running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
