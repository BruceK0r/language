from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from paper_agent.memory.db import connect, init_db
from paper_agent.schemas import Paper, RankedPaper


class MemoryRepository:
    def __init__(self, db_path: str | Path = "paper_agent.db") -> None:
        self.db_path = Path(db_path)
        if self.db_path.parent != Path("."):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with connect(self.db_path) as conn:
            init_db(conn)

    def upsert_paper(self, paper: Paper) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO papers (
                    paper_id, title, authors, abstract, published_date, url, pdf_url,
                    source, citation_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(paper_id) DO UPDATE SET
                    title=excluded.title,
                    authors=excluded.authors,
                    abstract=excluded.abstract,
                    published_date=excluded.published_date,
                    url=excluded.url,
                    pdf_url=excluded.pdf_url,
                    source=excluded.source,
                    citation_count=excluded.citation_count
                """,
                (
                    paper.paper_id,
                    paper.title,
                    json.dumps(paper.authors, ensure_ascii=False),
                    paper.abstract,
                    paper.published_date,
                    paper.url,
                    paper.pdf_url,
                    paper.source,
                    paper.citation_count,
                ),
            )
            conn.commit()

    def create_search_task(
        self,
        user_query: str,
        parsed_request: dict[str, Any],
        expanded_keywords: list[str],
        selected_papers: list[RankedPaper],
        final_report: str,
    ) -> str:
        task_id = str(uuid.uuid4())
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO search_tasks (
                    task_id, user_query, parsed_request_json, expanded_keywords_json,
                    selected_papers_json, final_report
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    user_query,
                    json.dumps(parsed_request, ensure_ascii=False),
                    json.dumps(expanded_keywords, ensure_ascii=False),
                    json.dumps([paper.model_dump() for paper in selected_papers], ensure_ascii=False),
                    final_report,
                ),
            )
            conn.commit()
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM search_tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return {
            "task_id": row["task_id"],
            "user_query": row["user_query"],
            "parsed_request": json.loads(row["parsed_request_json"]),
            "expanded_keywords": json.loads(row["expanded_keywords_json"]),
            "selected_papers": json.loads(row["selected_papers_json"]),
            "final_report": row["final_report"],
            "created_at": row["created_at"],
        }

    def get_user_memory(self, user_id: str) -> dict[str, Any]:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM user_memory WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return {
                "preferred_domains": [],
                "preferred_language": "zh",
                "summary_style": "standard",
                "seen_papers": [],
            }
        return {
            "preferred_domains": json.loads(row["preferred_domains_json"]),
            "preferred_language": row["preferred_language"],
            "summary_style": row["summary_style"],
            "seen_papers": json.loads(row["seen_papers_json"]),
        }

    def update_user_memory(
        self,
        user_id: str,
        domain: str,
        preferred_language: str,
        summary_style: str,
        selected_papers: list[RankedPaper],
    ) -> dict[str, Any]:
        memory = self.get_user_memory(user_id)
        domains = list(dict.fromkeys([domain, *memory.get("preferred_domains", [])]))[:20]
        seen = list(
            dict.fromkeys(
                [
                    *(paper.paper.paper_id for paper in selected_papers),
                    *(paper.paper.url for paper in selected_papers),
                    *memory.get("seen_papers", []),
                ]
            )
        )[:500]
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO user_memory (
                    user_id, preferred_domains_json, preferred_language, summary_style,
                    seen_papers_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    preferred_domains_json=excluded.preferred_domains_json,
                    preferred_language=excluded.preferred_language,
                    summary_style=excluded.summary_style,
                    seen_papers_json=excluded.seen_papers_json,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    json.dumps(domains, ensure_ascii=False),
                    preferred_language,
                    summary_style,
                    json.dumps(seen, ensure_ascii=False),
                ),
            )
            conn.commit()
        return {
            "preferred_domains": domains,
            "preferred_language": preferred_language,
            "summary_style": summary_style,
            "seen_papers_count": len(seen),
        }
