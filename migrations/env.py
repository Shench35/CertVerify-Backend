"""
Alembic environment configuration for CertVerify.

Reads the database URL from app.core.config.settings and uses SQLModel's
metadata so that `alembic revision --autogenerate` can diff the ORM models
against the live database.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Import application metadata & models ─────────────────────
# Import all models so they register on SQLModel.metadata before Alembic
# inspects it.
from sqlmodel import SQLModel
import app.models  # noqa: F401 — registers Transaction, ApiKey, TaskResult, UserCreditAccount

from app.core.config import settings

# ── Alembic Config object ────────────────────────────────────
config = context.config

# Override sqlalchemy.url with the value from .env / settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Logging setup from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = SQLModel.metadata


# ── Offline mode (SQL script generation) ─────────────────────

def run_migrations_offline() -> None:
    """Generate SQL scripts without a live database connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (live database connection) ───────────────────

def run_migrations_online() -> None:
    """Run migrations against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
