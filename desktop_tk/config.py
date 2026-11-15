"""Where the backend lives. The first of these that is set wins:

1. the environment variable STOCKPILOT_API_URL
     Windows:  set STOCKPILOT_API_URL=https://your-project.vercel.app
2. a one-line text file named  server.txt  next to this file (handy when double-clicking the app)
3. the local test server http://127.0.0.1:8000
"""
import os
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT_SECONDS = 30  # generous: a sleeping serverless backend can take a few seconds to wake up


def normalise_url(text):
    """'  my-app.vercel.app/ ' -> 'https://my-app.vercel.app'  (adds https:// when no scheme was typed)."""
    text = (text or "").strip().rstrip("/")
    if not text:
        return DEFAULT_URL
    if "://" not in text:
        text = "https://" + text
    return text


def read_server_file(folder=None):
    path = Path(folder or Path(__file__).parent) / "server.txt"
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    except OSError:
        return ""
    return lines[0] if lines else ""


def find_url(environment=None, folder=None):
    environment = os.environ if environment is None else environment
    return normalise_url(environment.get("STOCKPILOT_API_URL") or read_server_file(folder))


def is_insecure(url):
    """True when the address uses plain http to a machine that is not this computer (passwords would travel unencrypted)."""
    parsed = urlparse(url)
    return parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1")


API_URL = find_url()
INSECURE = is_insecure(API_URL)
