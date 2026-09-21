"""SQLite 轻量补列：create_all 不会改已有表结构。"""

from sqlalchemy import inspect, text

from app.database import engine


def _add_missing(table: str, columns: dict[str, str]) -> None:
    inspector = inspect(engine)
    if table not in set(inspector.get_table_names()):
        return
    existing = {col["name"] for col in inspector.get_columns(table)}
    alters = [
        f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"
        for name, ddl in columns.items()
        if name not in existing
    ]
    if not alters:
        return
    with engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))


def ensure_schema() -> None:
    _add_missing(
        "users",
        {
            "nickname": "VARCHAR(50) NOT NULL DEFAULT ''",
            "avatar_url": "VARCHAR(500) NOT NULL DEFAULT ''",
            "gender": "VARCHAR(20) NOT NULL DEFAULT 'unknown'",
            "bio": "VARCHAR(200) NOT NULL DEFAULT ''",
        },
    )
    _add_missing(
        "user_videos",
        {
            "tags": "VARCHAR(200) NOT NULL DEFAULT ''",
            "duration": "FLOAT NOT NULL DEFAULT 0",
            "width": "INTEGER NOT NULL DEFAULT 0",
            "height": "INTEGER NOT NULL DEFAULT 0",
            "file_size": "INTEGER NOT NULL DEFAULT 0",
            "mime_type": "VARCHAR(80) NOT NULL DEFAULT ''",
            "original_filename": "VARCHAR(255) NOT NULL DEFAULT ''",
            "city": "VARCHAR(50) NOT NULL DEFAULT ''",
        },
    )


# 兼容旧调用名
def ensure_user_profile_columns() -> None:
    ensure_schema()
