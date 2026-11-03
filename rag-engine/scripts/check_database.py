#!/usr/bin/env python3
"""Comprueba conexión, versión de PostgreSQL, pgvector y tablas requeridas."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import DatabaseUnavailableError, connect


REQUIRED_TABLES = (
    "documento",
    "version_documento",
    "fragmento",
    "configuracion_modelo",
    "embedding_fragmento_alia",
    "ingesta",
    "schema_migracion",
)
FRAGMENT_COLUMNS = ("pagina_inicio", "pagina_fin", "token_count", "tipo_contenido")


def main() -> int:
    try:
        conn = connect(register=False, autocommit=True)
    except (DatabaseUnavailableError, ValueError) as exc:
        print(f"PostgreSQL: ERROR\n{exc}")
        return 1

    ok = True
    with conn:
        print("PostgreSQL: OK")
        print(f"Versión: {conn.execute('SHOW server_version').fetchone()[0]}")
        row = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
        if row:
            print(f"pgvector: OK ({row[0]})")
        else:
            print("pgvector: NO INSTALADO")
            ok = False
        database, user = conn.execute("SELECT current_database(), current_user").fetchone()
        print(f"Base: {database} (usuario {user})")

        print("\nTablas:")
        existing = {
            name
            for (name,) in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
        }
        for table in REQUIRED_TABLES:
            present = table in existing
            ok &= present
            print(f"{table:<26}{'OK' if present else 'FALTA'}")

        if "embedding_fragmento_alia" in existing:
            column_type = conn.execute(
                """
                SELECT format_type(atttypid, atttypmod) FROM pg_attribute
                WHERE attrelid = 'embedding_fragmento_alia'::regclass AND attname = 'embedding'
                """
            ).fetchone()[0]
            print(f"\nembedding_fragmento_alia.embedding: {column_type}")
            ok &= column_type == "vector(768)"

        if "fragmento" in existing:
            columns = {
                name for (name,) in conn.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'fragmento'"
                )
            }
            missing = [c for c in FRAGMENT_COLUMNS if c not in columns]
            print(f"fragmento (página/tokens/tipo): {'OK' if not missing else 'FALTA ' + ', '.join(missing)}")
            ok &= not missing

        if "schema_migracion" in existing:
            applied = [name for (name,) in conn.execute("SELECT archivo FROM schema_migracion ORDER BY archivo")]
            print(f"Migraciones registradas: {', '.join(applied) or 'ninguna'}")

        if "configuracion_modelo" in existing:
            print("\nConfiguraciones de modelo:")
            for nombre, model_id, dimension, normalizado, activo in conn.execute(
                "SELECT nombre, model_id, dimension, normalizado, activo FROM configuracion_modelo ORDER BY nombre"
            ):
                print(f"  {nombre}: {model_id} | {dimension}d | normalizado={normalizado} | activo={activo}")

        if ok:
            print("\nRegistros:")
            for table in REQUIRED_TABLES:
                count = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                print(f"  {table:<26}{count}")

    print("\nEstado general:", "OK" if ok else "INCOMPLETO")
    if not ok:
        print("Sugerencia: python scripts/migrate_database.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
