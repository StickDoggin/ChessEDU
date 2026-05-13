"""Shared FastAPI dependencies and Pydantic base models."""
import sys
import os
from typing import Generator

import psycopg
from pydantic import BaseModel

# Resolve project root so db_setup is importable from any working dir
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db_setup import get_connection


def get_db() -> Generator[psycopg.Connection, None, None]:
    """Yield a psycopg connection; close on exit."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


class OKResponse(BaseModel):
    status: str
    version: str
