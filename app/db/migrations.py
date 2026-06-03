from __future__ import annotations

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings, normalize_database_url
from app.db.session import get_engine, is_database_initialized


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url or get_settings().database_url)
    return config


def upgrade_database(revision: str = "head", database_url: str | None = None) -> None:
    command.upgrade(get_alembic_config(database_url), revision)


def downgrade_database(revision: str, database_url: str | None = None) -> None:
    command.downgrade(get_alembic_config(database_url), revision)


def create_revision(message: str, autogenerate: bool = False, database_url: str | None = None) -> None:
    command.revision(get_alembic_config(database_url), message=message, autogenerate=autogenerate)


def stamp_database(revision: str = "head", database_url: str | None = None) -> None:
    command.stamp(get_alembic_config(database_url), revision)


def get_head_revision() -> str | None:
    return ScriptDirectory.from_config(get_alembic_config()).get_current_head()


def get_current_database_revision(database_url: str | None = None) -> str | None:
    engine = get_engine() if database_url is None else create_engine(database_url, future=True, pool_pre_ping=True)
    inspector = inspect(engine)

    try:
        if not inspector.has_table("alembic_version"):
            return None
        with engine.connect() as connection:
            return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    finally:
        if database_url is not None:
            engine.dispose()


def show_database_status(database_url: str | None = None) -> None:
    engine = get_engine() if database_url is None else create_engine(database_url, future=True, pool_pre_ping=True)
    inspector = inspect(engine)

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        has_alembic_table = inspector.has_table("alembic_version")
        current_revision = (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            if has_alembic_table
            else None
        )

    schema_initialized = is_database_initialized() if database_url is None else True
    print(f"database_url={database_url or get_settings().database_url}")
    print(f"schema_initialized={schema_initialized}")
    print(f"table_count={len(inspector.get_table_names())}")
    print(f"alembic_version_table={'present' if has_alembic_table else 'missing'}")
    print(f"current_revision={current_revision or 'none'}")

    if database_url is not None:
        engine.dispose()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Meeting server database migration helper")
    parser.add_argument("--database-url", dest="database_url", default=None, help="Optional database URL override")
    parser.add_argument("--database-username", dest="database_username", default="", help="Username for JDBC-style URLs")
    parser.add_argument("--database-password", dest="database_password", default="", help="Password for JDBC-style URLs")

    subparsers = parser.add_subparsers(dest="command", required=True)
    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade database schema")
    upgrade_parser.add_argument("revision", nargs="?", default="head")

    downgrade_parser = subparsers.add_parser("downgrade", help="Downgrade database schema")
    downgrade_parser.add_argument("revision")

    revision_parser = subparsers.add_parser("revision", help="Create a new migration revision")
    revision_parser.add_argument("message")
    revision_parser.add_argument("--autogenerate", action="store_true")

    stamp_parser = subparsers.add_parser("stamp", help="Stamp database with a revision")
    stamp_parser.add_argument("revision", nargs="?", default="head")

    subparsers.add_parser("current", help="Show current database revision")
    subparsers.add_parser("status", help="Show database connectivity and migration status")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    database_url = (
        normalize_database_url(args.database_url, args.database_username, args.database_password)
        if args.database_url
        else None
    )

    if args.command == "upgrade":
        upgrade_database(args.revision, database_url=database_url)
    elif args.command == "downgrade":
        downgrade_database(args.revision, database_url=database_url)
    elif args.command == "revision":
        create_revision(args.message, autogenerate=args.autogenerate, database_url=database_url)
    elif args.command == "stamp":
        stamp_database(args.revision, database_url=database_url)
    elif args.command == "current":
        print(get_current_database_revision(database_url=database_url) or "none")
    elif args.command == "status":
        show_database_status(database_url=database_url)
    else:
        parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
