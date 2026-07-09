from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from paper_agent.memory.db import connect, init_db
from paper_agent.schemas import Paper, RankedPaper


KEYWORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]*(?:\s+[A-Za-z][A-Za-z0-9+\-]*){0,2}")


def _clean_keywords(keywords: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        value = " ".join(str(keyword or "").strip().split())
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        cleaned.append(value)
        seen.add(key)
    return cleaned


def _extract_keywords_from_text(text: str, limit: int = 8) -> list[str]:
    academic_phrases = [
        "large language models",
        "llm agent",
        "multi-agent",
        "multi-agent systems",
        "retrieval augmented generation",
        "retrieval-augmented generation",
        "rag",
        "agent memory",
        "natural language processing",
        "computer vision",
        "information retrieval",
        "recommendation systems",
        "knowledge graphs",
        "ai safety",
        "trustworthy ai",
    ]
    lowered = (text or "").lower()
    matches = [phrase for phrase in academic_phrases if phrase in lowered]
    for match in KEYWORD_RE.findall(text or ""):
        if len(match) > 2 and match.lower() not in {"the", "and", "for", "with", "about"}:
            matches.append(match)
    return _clean_keywords(matches)[:limit]


def _paper_id_from_item(item: Any) -> str:
    if hasattr(item, "paper"):
        return _paper_id_from_item(item.paper)
    if hasattr(item, "paper_id"):
        return str(item.paper_id)
    if isinstance(item, dict):
        if item.get("paper_id"):
            return str(item["paper_id"])
        paper = item.get("paper")
        if paper is not None:
            return _paper_id_from_item(paper)
        if item.get("id"):
            return str(item["id"])
        if item.get("url"):
            return str(item["url"])
    return ""


def _score_from_item(item: Any) -> float:
    if hasattr(item, "scores") and hasattr(item.scores, "final_score"):
        return float(item.scores.final_score)
    if isinstance(item, dict):
        if item.get("score") is not None:
            return float(item["score"])
        if item.get("final_score") is not None:
            return float(item["final_score"])
        scores = item.get("scores")
        if isinstance(scores, dict) and scores.get("final_score") is not None:
            return float(scores["final_score"])
    return 0.0


def _reason_from_item(item: Any) -> str:
    if hasattr(item, "ranking_reason"):
        return str(item.ranking_reason)
    if isinstance(item, dict):
        return str(item.get("reason") or item.get("ranking_reason") or "")
    return ""


class MemoryRepository:
    def __init__(self, db_path: str | Path = "paper_agent.db") -> None:
        self.db_path = Path(db_path)
        if self.db_path.parent != Path("."):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with connect(self.db_path) as conn:
            init_db(conn)

    def create_user_if_not_exists(self, user_id: str) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO users (user_id) VALUES (?)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_active_at=CURRENT_TIMESTAMP
                """,
                (user_id,),
            )
            conn.commit()

    def create_initial_profile(self, user_id: str, interests: list[str]) -> None:
        cleaned = _clean_keywords(interests)
        if not cleaned:
            raise ValueError("interests must contain at least one item")
        self.create_user_if_not_exists(user_id)
        with connect(self.db_path) as conn:
            conn.execute("DELETE FROM user_interests WHERE user_id = ?", (user_id,))
            conn.executemany(
                """
                INSERT INTO user_interests (
                    user_id, interest_name, weight, source
                ) VALUES (?, ?, 1.0, 'onboarding')
                """,
                [(user_id, interest) for interest in cleaned],
            )
            conn.execute(
                """
                UPDATE users
                SET onboarding_done = 1, last_active_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (user_id,),
            )
            conn.commit()

    def reset_user_profile_memory(self, user_id: str) -> dict[str, int]:
        self.create_user_if_not_exists(user_id)
        summary: dict[str, int] = {}
        delete_targets = [
            ("user_interests", "deleted_interests"),
            ("user_actions", "deleted_actions"),
            ("recommendation_logs", "deleted_recommendation_logs"),
            ("image_interactions", "deleted_image_interactions"),
            ("user_memory", "deleted_user_memory"),
        ]
        with connect(self.db_path) as conn:
            for table_name, summary_key in delete_targets:
                cursor = conn.execute(f"DELETE FROM {table_name} WHERE user_id = ?", (user_id,))
                summary[summary_key] = max(0, int(cursor.rowcount))
            conn.execute(
                """
                UPDATE users
                SET onboarding_done = 0, last_active_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (user_id,),
            )
            conn.commit()
        return summary

    def get_user_profile(self, user_id: str) -> dict[str, Any]:
        self.create_user_if_not_exists(user_id)
        with connect(self.db_path) as conn:
            user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            interests = conn.execute(
                """
                SELECT * FROM user_interests
                WHERE user_id = ?
                ORDER BY weight DESC, interest_name ASC
                """,
                (user_id,),
            ).fetchall()
            action_counts = conn.execute(
                """
                SELECT action_type, COUNT(*) AS count
                FROM user_actions
                WHERE user_id = ?
                GROUP BY action_type
                """,
                (user_id,),
            ).fetchall()
            recommended_count = conn.execute(
                """
                SELECT COUNT(DISTINCT paper_id) AS count
                FROM recommendation_logs
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            image_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM image_interactions
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        total_weight = sum(float(row["weight"]) for row in interests)
        interest_items = []
        for row in interests:
            weight = float(row["weight"])
            percentage = round((weight / total_weight * 100.0) if total_weight else 0.0, 2)
            interest_items.append(
                {
                    "id": row["id"],
                    "interest_name": row["interest_name"],
                    "weight": weight,
                    "percentage": percentage,
                    "source": row["source"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return {
            "user": {
                "user_id": user["user_id"],
                "created_at": user["created_at"],
                "last_active_at": user["last_active_at"],
                "onboarding_done": bool(user["onboarding_done"]),
            },
            "interests": interest_items,
            "stats": {
                row["action_type"]: row["count"] for row in action_counts
            }
            | {
                "recommended": recommended_count["count"] if recommended_count else 0,
                "image_interactions": image_count["count"] if image_count else 0,
            },
        }

    def update_interest_weights(self, user_id: str, keywords: list[str], delta: float, source: str) -> None:
        cleaned = _clean_keywords(keywords)
        if not cleaned:
            return
        self.create_user_if_not_exists(user_id)
        with connect(self.db_path) as conn:
            for keyword in cleaned:
                row = conn.execute(
                    """
                    SELECT interest_name, weight
                    FROM user_interests
                    WHERE user_id = ? AND LOWER(interest_name) = LOWER(?)
                    """,
                    (user_id, keyword),
                ).fetchone()
                if row is None:
                    if delta < 0:
                        continue
                    conn.execute(
                        """
                        INSERT INTO user_interests (
                            user_id, interest_name, weight, source
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (user_id, keyword, max(0.0, float(delta)), source),
                    )
                    continue
                new_weight = max(0.0, float(row["weight"]) + float(delta))
                conn.execute(
                    """
                    UPDATE user_interests
                    SET weight = ?, source = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND interest_name = ?
                    """,
                    (new_weight, source, user_id, row["interest_name"]),
                )
            conn.execute("UPDATE users SET last_active_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
            conn.commit()

    def update_profile_from_query(
        self,
        user_id: str,
        query: str,
        extracted_keywords: list[str] | None = None,
    ) -> None:
        keywords = _clean_keywords(extracted_keywords or _extract_keywords_from_text(query))
        self.update_interest_weights(user_id, keywords, delta=0.2, source="query")

    def update_profile_from_image(self, user_id: str, vision_result: dict) -> None:
        keywords = _clean_keywords(
            [
                *(vision_result.get("recommendation_keywords") or []),
                *(vision_result.get("possible_related_topics") or []),
            ]
        )
        self.create_user_if_not_exists(user_id)
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO image_interactions (
                    user_id, image_type, user_question, vision_summary, extracted_keywords
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    str(vision_result.get("image_type") or "other"),
                    str(vision_result.get("user_question") or ""),
                    str(vision_result.get("main_content") or vision_result.get("vision_summary") or ""),
                    json.dumps(keywords, ensure_ascii=False),
                ),
            )
            conn.commit()
        self.update_interest_weights(user_id, keywords, delta=0.15, source="image")

    def log_user_action(self, user_id: str, paper_id: str, action_type: str) -> None:
        self.create_user_if_not_exists(user_id)
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO user_actions (user_id, paper_id, action_type)
                VALUES (?, ?, ?)
                """,
                (user_id, paper_id, action_type),
            )
            paper = conn.execute(
                """
                SELECT title, abstract
                FROM papers
                WHERE paper_id = ? OR url = ?
                """,
                (paper_id, paper_id),
            ).fetchone()
            conn.execute("UPDATE users SET last_active_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
            conn.commit()
        if paper and action_type in {"favorited", "disliked"}:
            delta = 0.3 if action_type == "favorited" else -0.2
            keywords = _extract_keywords_from_text(f"{paper['title']} {paper['abstract']}")
            self.update_interest_weights(user_id, keywords, delta=delta, source=action_type)

    def get_seen_paper_ids(self, user_id: str) -> set[str]:
        with connect(self.db_path) as conn:
            action_rows = conn.execute(
                "SELECT paper_id FROM user_actions WHERE user_id = ?",
                (user_id,),
            ).fetchall()
            recommendation_rows = conn.execute(
                "SELECT paper_id FROM recommendation_logs WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return {
            row["paper_id"]
            for row in [*action_rows, *recommendation_rows]
            if row["paper_id"]
        }

    def log_recommendations(self, user_id: str, task_id: str, papers: list[dict]) -> None:
        self.create_user_if_not_exists(user_id)
        with connect(self.db_path) as conn:
            for rank, paper in enumerate(papers, start=1):
                paper_id = _paper_id_from_item(paper)
                if not paper_id:
                    continue
                conn.execute(
                    """
                    INSERT INTO recommendation_logs (
                        user_id, task_id, paper_id, rank, score, reason
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, task_id, paper_id, rank, _score_from_item(paper), _reason_from_item(paper)),
                )
                conn.execute(
                    """
                    INSERT INTO user_actions (user_id, paper_id, action_type)
                    VALUES (?, ?, 'shown')
                    """,
                    (user_id, paper_id),
                )
            conn.execute("UPDATE users SET last_active_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
            conn.commit()

    def filter_unseen_papers(self, user_id: str, papers: list[dict]) -> list[dict]:
        seen = self.get_seen_paper_ids(user_id)
        return [paper for paper in papers if _paper_id_from_item(paper) not in seen]

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
