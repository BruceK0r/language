from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS papers (
            paper_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            authors TEXT NOT NULL,
            abstract TEXT NOT NULL,
            published_date TEXT NOT NULL,
            url TEXT NOT NULL,
            pdf_url TEXT,
            source TEXT NOT NULL,
            citation_count INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS search_tasks (
            task_id TEXT PRIMARY KEY,
            user_query TEXT NOT NULL,
            parsed_request_json TEXT NOT NULL,
            expanded_keywords_json TEXT NOT NULL,
            selected_papers_json TEXT NOT NULL,
            final_report TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_memory (
            user_id TEXT PRIMARY KEY,
            preferred_domains_json TEXT NOT NULL,
            preferred_language TEXT NOT NULL,
            summary_style TEXT NOT NULL,
            seen_papers_json TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()

