"""Vercel entry point: Vercel looks for an `app` object in api/index.py."""
import os
import sys

# Make the 'app' package importable when Vercel runs this file
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402,F401
