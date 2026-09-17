from collections.abc import Generator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings


settings = get_settings()
pool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=10,
    timeout=10,
    kwargs={"row_factory": dict_row},
    open=False,
)


@asynccontextmanager
async def database_lifespan(_: FastAPI):
    """Open the shared pool at application startup and close it on shutdown."""
    pool.open(wait=True)
    from .services.speech import start_worker, stop_worker
    start_worker()
    try:
        yield
    finally:
        stop_worker()
        pool.close()


def get_connection() -> Generator[Connection, None, None]:
    """Borrow a PostgreSQL connection for one API request."""
    with pool.connection() as connection:
        yield connection
