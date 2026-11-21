# URL Shortener

A small URL shortener written in Python using only the standard library. Short
links are stored in SQLite and remain available after the server restarts.

## Run

Requires Python 3.9 or later:

```bash
python3 app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000), enter an `http://` or
`https://` URL, and submit it. The app creates `urls.db` in the current
directory. It listens on all interfaces by default so Codespaces can forward
port 8000; set `HOST=127.0.0.1` to restrict access to the local machine.

Configure the bind address, port, or database location with environment
variables:

```bash
HOST=0.0.0.0 PORT=8000 URL_SHORTENER_DB=/path/to/urls.db python3 app.py
```

In a Codespace, expose port 8000 and use its forwarded URL to access the app.

## Test

```bash
python3 -m unittest
```
