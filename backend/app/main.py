"""Creates the FastAPI app. It only wires things together; logic lives in routers/."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DataError

from app import config
from app.database import engine
from app.routers import auth, businesses, categories, dashboard, products, reports, stock, suppliers

config.check_settings()

app = FastAPI(title="StockPilot API", version="1.0.0")
app.include_router(auth.router)
app.include_router(businesses.router)
app.include_router(dashboard.router)
app.include_router(categories.router)
app.include_router(products.router)
app.include_router(suppliers.router)
app.include_router(stock.router)
app.include_router(reports.router)


@app.exception_handler(DataError)
def value_the_database_cannot_store(request: Request, error: DataError):
    """A number too big for the column (e.g. an id of 99999999999) or text with a NUL character reaches the database
    and is refused there. That is the caller's mistake, so answer 422 instead of an unexplained 500.
    The session is closed by get_db, which rolls the failed request back; nothing is saved."""
    return JSONResponse(status_code=422, content={"detail": "One of the values is out of range or contains characters that are not allowed."})


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "StockPilot API"}


@app.get("/health", tags=["Health"])
def health_with_database():
    """Used after deployment: proves the app can reach the database (503 if it cannot)."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        # never put the real error in the response: it could contain the host or user name of the database
        raise HTTPException(status_code=503, detail="The database is not reachable")
    return {"status": "ok", "database": "ok"}
