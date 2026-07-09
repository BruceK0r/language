from __future__ import annotations

from typing import Any

from paper_agent.config import get_settings
from paper_agent.memory.repository import MemoryRepository
from paper_agent.providers import build_llm_provider
from paper_agent.agents.critic_agent import CriticAgent
from paper_agent.agents.profile_agent import ProfileAgent
from paper_agent.agents.query_planner_agent import QueryPlannerAgent
from paper_agent.agents.reader_agent import ReaderAgent
from paper_agent.agents.recommender_agent import RecommenderAgent
from paper_agent.agents.report_agent import ReportAgent
from paper_agent.agents.retrieval_agent import RetrievalAgent
from paper_agent.agents.vision_agent import VisionAgent


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


def _read_image_file(image_file: Any) -> tuple[bytes, str]:
    if isinstance(image_file, bytes):
        return image_file, "image/png"
    if isinstance(image_file, bytearray):
        return bytes(image_file), "image/png"
    if hasattr(image_file, "getvalue"):
        image_bytes = image_file.getvalue()
        mime_type = getattr(image_file, "type", None) or getattr(image_file, "content_type", None) or "image/png"
        return bytes(image_bytes), str(mime_type)
    if hasattr(image_file, "read"):
        image_bytes = image_file.read()
        mime_type = getattr(image_file, "type", None) or getattr(image_file, "content_type", None) or "image/png"
        return bytes(image_bytes), str(mime_type)
    raise TypeError("image_file must be bytes or a file-like object")


class CoordinatorAgent:
    def __init__(
        self,
        memory: MemoryRepository | None = None,
        planner: QueryPlannerAgent | None = None,
        retrieval_agent: Any | None = None,
        recommender: RecommenderAgent | None = None,
        reader: ReaderAgent | None = None,
        critic: CriticAgent | None = None,
        reporter: ReportAgent | None = None,
        profile_agent: ProfileAgent | None = None,
        vision_agent: VisionAgent | None = None,
    ) -> None:
        settings = get_settings()
        self.memory = memory or MemoryRepository(settings.database_path)
        try:
            llm = build_llm_provider(settings)
        except Exception:
            llm = None
        self.profile_agent = profile_agent or ProfileAgent(memory=self.memory)
        self.planner = planner or QueryPlannerAgent(llm_provider=llm)
        self.retrieval_agent = retrieval_agent or RetrievalAgent()
        self.recommender = recommender or RecommenderAgent(memory=self.memory)
        self.reader = reader or ReaderAgent(llm_provider=llm)
        self.critic = critic or CriticAgent(llm_provider=llm)
        self.reporter = reporter or ReportAgent()
        self.vision_agent = vision_agent or VisionAgent()

    def run_text_query(self, user_id: str, query: str, top_k: int = 5) -> dict[str, Any]:
        self.profile_agent.create_user_if_not_exists(user_id)
        planned_query = self.planner.plan(query, top_k=top_k)
        papers, retrieval_errors = self.retrieval_agent.retrieve(planned_query)
        profile_update = self.profile_agent.update_profile_from_query(user_id, query, planned_query.get("keywords", []))

        if not papers:
            answer = self.reporter.build_text_query_report(
                query=query,
                planned_query=planned_query,
                recommendations=[],
                summaries=[],
                follow_up_recommendations=[],
                profile_update=profile_update,
                errors=retrieval_errors,
            )
            return {
                "answer": answer,
                "recommendations": [],
                "follow_up_recommendations": [],
                "profile_update": profile_update,
                "planned_query": planned_query,
                "errors": retrieval_errors,
            }

        recommendation_result = self.recommender.recommend(
            user_id=user_id,
            query=query,
            candidate_papers=papers,
            top_k=planned_query.get("top_k", top_k),
        )
        recommendations = recommendation_result.get("recommendations", [])
        follow_up = recommendation_result.get("follow_up_recommendations", [])
        recommendations = self.reader.enrich_recommendation_reasons(recommendations, query, purpose="top")
        follow_up = self.reader.enrich_recommendation_reasons(follow_up, query, purpose="follow_up")
        summaries = self.reader.summarize(recommendations, query)
        reviewed = self.critic.review(summaries)
        answer = self.reporter.build_text_query_report(
            query=query,
            planned_query=planned_query,
            recommendations=recommendations,
            summaries=reviewed,
            follow_up_recommendations=follow_up,
            profile_update=profile_update,
            errors=retrieval_errors,
        )
        return {
            "answer": answer,
            "recommendations": recommendations,
            "follow_up_recommendations": follow_up,
            "profile_update": profile_update,
            "planned_query": planned_query,
            "errors": retrieval_errors,
        }

    def run_vision_query(
        self,
        user_id: str,
        image_file: Any,
        question: str = "",
        top_k: int = 3,
    ) -> dict[str, Any]:
        self.profile_agent.create_user_if_not_exists(user_id)
        image_bytes, mime_type = _read_image_file(image_file)
        vision_result = self.vision_agent.analyze(image_bytes, mime_type=mime_type, question=question or "")
        vision_result = {**vision_result, "user_question": question or ""}
        profile_update = self.profile_agent.update_profile_from_image(user_id, vision_result)
        keywords = _clean_keywords(vision_result.get("recommendation_keywords") or [])
        if not keywords:
            keywords = _clean_keywords(vision_result.get("possible_related_topics") or [])
        if not keywords and question:
            keywords = self.profile_agent.extract_keywords_from_query(question)

        planned_query = {
            "keywords": keywords,
            "time_range": "last_180_days",
            "top_k": top_k,
        }
        errors: list[str] = []
        if not keywords:
            errors.append("Vision query did not produce recommendation keywords.")
            answer = self.reporter.build_vision_query_report(
                question=question,
                vision_result=vision_result,
                planned_query=planned_query,
                recommendations=[],
                follow_up_recommendations=[],
                profile_update=profile_update,
                errors=errors,
            )
            return {
                "vision_result": vision_result,
                "answer": answer,
                "related_recommendations": [],
                "recommendations": [],
                "follow_up_recommendations": [],
                "profile_update": profile_update,
                "planned_query": planned_query,
                "errors": errors,
            }

        papers, retrieval_errors = self.retrieval_agent.retrieve(planned_query)
        errors.extend(retrieval_errors)
        recommendation_result = self.recommender.recommend(
            user_id=user_id,
            query=" ".join(keywords),
            candidate_papers=papers,
            top_k=top_k,
        )
        recommendations = recommendation_result.get("recommendations", [])
        follow_up = recommendation_result.get("follow_up_recommendations", [])
        reason_query = question or vision_result.get("main_content", "")
        recommendations = self.reader.enrich_recommendation_reasons(recommendations, reason_query, purpose="top")
        follow_up = self.reader.enrich_recommendation_reasons(follow_up, reason_query, purpose="follow_up")
        summaries = self.reader.summarize(recommendations, question or vision_result.get("main_content", ""))
        reviewed = self.critic.review(summaries)
        answer = self.reporter.build_vision_query_report(
            question=question,
            vision_result=vision_result,
            planned_query=planned_query,
            recommendations=recommendations,
            follow_up_recommendations=follow_up,
            profile_update=profile_update,
            summaries=reviewed,
            errors=errors,
        )
        return {
            "vision_result": vision_result,
            "answer": answer,
            "related_recommendations": recommendations,
            "recommendations": recommendations,
            "follow_up_recommendations": follow_up,
            "profile_update": profile_update,
            "planned_query": planned_query,
            "errors": errors,
        }
