"""Runs a slow network call in a separate thread so the window never freezes.

Tkinter is not thread-safe: only the main thread may touch widgets. So the worker thread
only does the request and drops its result into a queue; the main thread checks that queue
every 50 ms (with widget.after) and then calls on_done / on_error safely.
"""
import queue
import threading
import traceback

from api_client import ApiError


def run_async(widget, work, on_done, on_error):
    results = queue.Queue()

    def worker():
        try:
            results.put(("ok", work()))
        except ApiError as error:
            results.put(("error", error))
        except Exception:  # a bug, not a server problem: print it for the developer
            traceback.print_exc()
            results.put(("error", ApiError("Something unexpected went wrong. Please try again.")))

    def check_for_result():
        if not widget.winfo_exists():  # the screen was closed while we were waiting
            return
        try:
            kind, value = results.get_nowait()
        except queue.Empty:
            widget.after(50, check_for_result)
            return
        (on_done if kind == "ok" else on_error)(value)

    threading.Thread(target=worker, daemon=True).start()
    widget.after(50, check_for_result)
