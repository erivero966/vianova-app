#!/usr/bin/env python3
"""Aplica las migraciones pendientes de sql/ y las registra con su SHA-256."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import DatabaseUnavailableError, SchemaDriftError, apply_schema, connect


def main() -> int:
    try:
        with connect(register=False) as conn:
            applied = apply_schema(conn)
    except (DatabaseUnavailableError, SchemaDriftError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print("Migraciones aplicadas/registradas: " + (", ".join(applied) if applied else "ninguna (al día)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
