import argparse
from pathlib import Path

import psycopg

from backend.app.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "database" / "migrations"


def migrate(database_url: str) -> list[str]:
    applied_now: list[str] = []
    with psycopg.connect(database_url) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        }

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem
            if version in applied:
                continue
            connection.execute(path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )
            applied_now.append(version)

    return applied_now


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply pending PostgreSQL migrations")
    parser.add_argument("--database-url", help="Override DATABASE_URL")
    args = parser.parse_args()
    database_url = args.database_url or get_settings().database_url
    applied = migrate(database_url)
    if applied:
        print(f"Applied migrations: {', '.join(applied)}")
    else:
        print("Database schema is already up to date.")


if __name__ == "__main__":
    main()
