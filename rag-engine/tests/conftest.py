"""Fixtures de integración con PostgreSQL.

Las pruebas usan una base aislada (`<POSTGRES_DB>_test`, configurable con
POSTGRES_TEST_DB) creada en el mismo servidor Docker; nunca tocan los datos
de `vianova_rag`. Cada prueba corre en una transacción que se revierte.
"""

from dataclasses import replace
import os

import numpy as np
import pytest
from psycopg import sql

from src.config import DatabaseSettings
from src.database import DatabaseUnavailableError, ModelConfigRepository, apply_schema, connect


@pytest.fixture(scope="session")
def test_db_settings() -> DatabaseSettings:
    try:
        settings = DatabaseSettings.from_env()
    except ValueError as exc:
        pytest.skip(str(exc))
    test_db = os.getenv("POSTGRES_TEST_DB", f"{settings.dbname}_test")
    try:
        admin = connect(settings, register=False, autocommit=True)
    except DatabaseUnavailableError as exc:
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    with admin:
        exists = admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (test_db,)).fetchone()
        if not exists:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(test_db)))
    test_settings = replace(settings, dbname=test_db)
    with connect(test_settings, register=False) as conn:
        apply_schema(conn)
    return test_settings


@pytest.fixture
def db(test_db_settings):
    conn = connect(test_db_settings)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def alia_config(db):
    return ModelConfigRepository(db).get_active("alia")


def unit_vector(seed: int, dimension: int = 768) -> np.ndarray:
    vector = np.random.default_rng(seed).standard_normal(dimension).astype(np.float32)
    return vector / np.linalg.norm(vector)
