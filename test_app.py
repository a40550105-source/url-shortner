import http.client
from http.server import ThreadingHTTPServer
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from app import (
    URLShortenerHandler,
    get_destination,
    initialize_database,
    is_valid_url,
    shorten_url,
)


class URLShortenerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = str(Path(self.temp_dir.name) / "urls.db")
        initialize_database(self.database_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_shortens_and_resolves_url(self):
        original = "https://example.com/a?b=c"
        code = shorten_url(original, self.database_path)

        self.assertEqual(len(code), 7)
        self.assertEqual(get_destination(code, self.database_path), original)

    def test_rejects_non_http_urls(self):
        for url in ("", "javascript:alert(1)", "ftp://example.com", "//example.com"):
            with self.subTest(url=url):
                self.assertFalse(is_valid_url(url))
                with self.assertRaises(ValueError):
                    shorten_url(url, self.database_path)

    def test_rejects_credentials_and_invalid_authorities(self):
        for url in (
            "https://user:pass@example.com/",
            "http://[invalid/",
            "http://example.com:invalid/",
        ):
            with self.subTest(url=url):
                self.assertFalse(is_valid_url(url))

    def test_unknown_codes_resolve_to_none(self):
        self.assertIsNone(get_destination("unknown", self.database_path))

    def test_http_create_and_redirect(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), URLShortenerHandler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            with patch("app.DATABASE_PATH", self.database_path):
                connection = http.client.HTTPConnection(*server.server_address)
                connection.request(
                    "POST",
                    "/",
                    body=urlencode({"url": "https://example.com/path"}),
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Forwarded-Proto": "https",
                    },
                )
                response = connection.getresponse()
                body = response.read().decode()
                self.assertEqual(response.status, 201)
                self.assertIn("https://127.0.0.1:", body)
                code = re.search(r"/([A-Za-z0-9_-]{7})</a>", body).group(1)

                connection.request("GET", f"/{code}?source=test")
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 302)
                self.assertEqual(
                    response.getheader("Location"), "https://example.com/path"
                )
                connection.close()
        finally:
            server.shutdown()
            thread.join()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
