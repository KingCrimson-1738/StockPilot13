"""'Save as...' for CSV exports: ask where to save, download in the background, write the file."""
from tkinter import filedialog

from api_client import ApiError
from background import run_async


def export_csv(widget, app, banner, api_call):
    """api_call() -> (suggested_name, bytes). Runs after the user picks a file; reports success/failure on `banner`."""
    def start(suggested):
        path = filedialog.asksaveasfilename(parent=app, title="Save CSV file", defaultextension=".csv",
                                            initialfile=suggested, filetypes=[("CSV file (opens in Excel)", "*.csv")])
        if not path:
            return  # the user cancelled

        def work():
            _, content = api_call()
            try:
                with open(path, "wb") as file:
                    file.write(content)
            except OSError as problem:
                raise ApiError(f"Could not save the file: {problem.strerror or 'unknown problem'}.")
            return path

        run_async(widget, work, lambda saved: banner.show(f"Saved {saved}", "success"),
                  lambda error: app.report_error(error, banner))
    return start
