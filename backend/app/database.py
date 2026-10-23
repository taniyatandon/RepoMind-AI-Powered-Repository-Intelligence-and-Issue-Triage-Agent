from collections.abc import Generator
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def _ensure_issue_analysis_content_digest(conn) -> None:
    """Add the nullable digest column to existing analysis tables once."""
    inspector = inspect(conn)
    if "issue_analyses" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("issue_analyses")}
    if "source_content_digest" not in columns:
        conn.execute(text(
            "ALTER TABLE issue_analyses ADD COLUMN source_content_digest VARCHAR(64)"
        ))


def migrate_user_ownership() -> None:
    """Migrate older databases to per-user repository ownership and uniqueness."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in ("repositories", "ingestion_jobs"):
            if table not in inspector.get_table_names():
                continue
            columns = {column["name"] for column in inspector.get_columns(table)}
            if "user_id" not in columns:
                if engine.dialect.name == "sqlite":
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"))
                else:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"))
                conn.execute(text(f"CREATE INDEX ix_{table}_user_id ON {table} (user_id)"))
        # Existing installations had shared repositories and no owner field.
        # Preserve them under the first account created; later accounts start empty.
        first_user_id = conn.execute(text("SELECT id FROM users ORDER BY id LIMIT 1")).scalar()
        if first_user_id is not None:
            conn.execute(
                text("UPDATE repositories SET user_id = :user_id WHERE user_id IS NULL"),
                {"user_id": first_user_id},
            )
            conn.execute(
                text("UPDATE ingestion_jobs SET user_id = :user_id WHERE user_id IS NULL"),
                {"user_id": first_user_id},
            )

        if "repositories" in inspector.get_table_names():
            # Older schemas made GitHub repositories globally unique, which prevented
            # another account from independently adding the same public repository.
            repo_indexes = {item["name"]: item for item in inspector.get_indexes("repositories")}
            for index in repo_indexes.values():
                if index.get("unique") and index.get("column_names") in (["github_repo_id"], ["full_name"]):
                    conn.execute(text(f'DROP INDEX "{index["name"]}"'))

            current_indexes = {item["name"] for item in inspect(conn).get_indexes("repositories")}
            scoped_indexes = (
                ("uq_repositories_user_github_repo_id", "github_repo_id"),
                ("uq_repositories_user_full_name", "full_name"),
            )
            for index_name, column in scoped_indexes:
                if index_name not in current_indexes:
                    conn.execute(text(
                        f'CREATE UNIQUE INDEX "{index_name}" ON repositories (user_id, "{column}")'
                    ))
            current_indexes = {item["name"] for item in inspect(conn).get_indexes("repositories")}
            for column in ("github_repo_id", "full_name"):
                index_name = f"ix_repositories_{column}"
                if index_name not in current_indexes:
                    conn.execute(text(
                        f'CREATE INDEX "{index_name}" ON repositories ("{column}")'
                    ))
        if "issue_analyses" in inspector.get_table_names():
            analysis_columns = {
                column["name"] for column in inspector.get_columns("issue_analyses")
            }
            json_type = "JSONB" if engine.dialect.name == "postgresql" else "JSON"
            timestamp_type = "TIMESTAMP WITH TIME ZONE" if engine.dialect.name == "postgresql" else "TIMESTAMP"
            for column_name in ("issue_facts", "repository_evidence", "assumptions"):
                if column_name not in analysis_columns:
                    conn.execute(text(
                        f"ALTER TABLE issue_analyses ADD COLUMN {column_name} {json_type} NOT NULL DEFAULT '[]'"
                    ))
            if "priority_rationale" not in analysis_columns:
                conn.execute(text(
                    "ALTER TABLE issue_analyses ADD COLUMN priority_rationale TEXT"
                ))
            if "repository_index_status" not in analysis_columns:
                conn.execute(text(
                    "ALTER TABLE issue_analyses ADD COLUMN repository_index_status VARCHAR(30)"
                ))
            if "repository_indexed_at" not in analysis_columns:
                conn.execute(text(
                    f"ALTER TABLE issue_analyses ADD COLUMN repository_indexed_at {timestamp_type}"
                ))
            _ensure_issue_analysis_content_digest(conn)
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
