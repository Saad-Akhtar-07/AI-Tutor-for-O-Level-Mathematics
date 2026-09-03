"""Create the local project role/database, migrate it, and seed Probability.

Run this script in a real terminal so password prompts stay hidden:
    python scripts/setup_database.py
"""

import argparse
import getpass
import os
import sys
from pathlib import Path
from urllib.parse import quote

import psycopg
from psycopg import sql
from psycopg.errors import OperationalError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.scripts.migrate import migrate  # noqa: E402
from backend.scripts.seed import seed  # noqa: E402


def set_env_value(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replacement = f"{key}={value}"
    updated: list[str] = []
    found = False
    for line in lines:
        if line.startswith(f"{key}="):
            updated.append(replacement)
            found = True
        else:
            updated.append(line)
    if not found:
        if updated and updated[-1].strip():
            updated.append("")
        updated.append(replacement)
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up the AI tutor PostgreSQL database")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5433)
    parser.add_argument("--admin-user", default="postgres")
    parser.add_argument("--app-user", default="ai_tutor_app")
    parser.add_argument("--database", default="ai_tutor")
    args = parser.parse_args()

    admin_password = getpass.getpass(
        f"Password for PostgreSQL administrator {args.admin_user}: "
    )
    try:
        connection = psycopg.connect(
            host=args.host,
            port=args.port,
            user=args.admin_user,
            password=admin_password,
            dbname="postgres",
            autocommit=True,
        )
    except OperationalError as error:
        raise SystemExit(
            f"Could not sign in as {args.admin_user!r} on "
            f"{args.host}:{args.port}. Check the administrator password and try again."
        ) from error

    with connection:
        app_password = getpass.getpass(f"Choose a password for role {args.app_user}: ")
        if not app_password:
            raise SystemExit("The project role password cannot be empty.")
        if app_password != getpass.getpass("Repeat the project role password: "):
            raise SystemExit("The project role passwords did not match.")

        role_exists = connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (args.app_user,)
        ).fetchone()
        if role_exists:
            connection.execute(
                sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(args.app_user), sql.Literal(app_password)
                )
            )
        else:
            connection.execute(
                sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(args.app_user), sql.Literal(app_password)
                )
            )

        database_exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (args.database,)
        ).fetchone()
        if not database_exists:
            connection.execute(
                sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0").format(
                    sql.Identifier(args.database), sql.Identifier(args.app_user)
                )
            )
        else:
            connection.execute(
                sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                    sql.Identifier(args.database), sql.Identifier(args.app_user)
                )
            )

    encoded_user = quote(args.app_user, safe="")
    encoded_password = quote(app_password, safe="")
    database_url = (
        f"postgresql://{encoded_user}:{encoded_password}@"
        f"{args.host}:{args.port}/{args.database}"
    )
    backend_env = PROJECT_ROOT / "backend" / ".env"
    set_env_value(backend_env, "DATABASE_URL", database_url)
    set_env_value(
        backend_env,
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )

    migrations = migrate(database_url)
    counts = seed(database_url)
    print(f"Database {args.database!r} and role {args.app_user!r} are ready.")
    print(
        "Migrations: "
        + (", ".join(migrations) if migrations else "already current")
    )
    print("Seeded: " + ", ".join(f"{value} {key}" for key, value in counts.items()))
    print("DATABASE_URL was written to backend/.env (which is ignored by Git).")


if __name__ == "__main__":
    main()
