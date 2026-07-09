from __future__ import annotations

from typing import Any


class ReportAgent:
    def build_text_query_report(
        self,
        query: str,
        planned_query: dict[str, Any],
        recommendations: list[dict[str, Any]],
        summaries: list[dict[str, Any]],
        follow_up_recommendations: list[dict[str, Any]],
        profile_update: dict[str, Any],
        errors: list[str] | None = None,
    ) -> str:
        lines = [
            "# 科研雷达文本查询报告",
            "",
            "## 查询理解",
            "",
            f"- 用户问题：{query}",
            f"- 关键词：{', '.join(planned_query.get('keywords', [])) or '无'}",
            f"- 时间范围：{planned_query.get('time_range', 'last_180_days')}",
            f"- Top K：{planned_query.get('top_k', len(recommendations))}",
            "",
            "## Top-K 推荐",
            "",
        ]
        if recommendations:
            for index, paper in enumerate(recommendations, start=1):
                lines.extend(
                    [
                        f"{index}. **[{paper.get('title', 'Untitled')}]({paper.get('url', '')})**",
                        f"   - 推荐分数：{float(paper.get('score', 0.0)):.3f}",
                        f"   - 推荐理由：{paper.get('reason', '')}",
                    ]
                )
        else:
            lines.append("未检索到候选论文，暂时无法生成个性化推荐。")
        lines.extend(["", "## 简要摘要", ""])
        summary_by_id = {summary.get("paper_id"): summary for summary in summaries}
        for paper in recommendations:
            summary = summary_by_id.get(paper.get("paper_id"))
            if not summary:
                continue
            lines.extend(
                [
                    f"### {summary.get('title', 'Untitled')}",
                    "",
                    f"- 研究问题：{summary.get('problem', '')}",
                    f"- 方法：{summary.get('method', '')}",
                    f"- 贡献：{summary.get('contribution', '')}",
                    f"- 局限：{summary.get('limitation', '')}",
                    f"- 推荐价值：{summary.get('why_recommended', '')}",
                    "",
                ]
            )
        lines.extend(["## 额外 3 篇未出现论文", ""])
        if follow_up_recommendations:
            for index, paper in enumerate(follow_up_recommendations, start=1):
                lines.append(f"{index}. **[{paper.get('title', 'Untitled')}]({paper.get('url', '')})**")
        else:
            lines.append("暂无额外未出现论文。")
        lines.extend(["", "## 画像更新摘要", "", profile_update.get("summary", "本次查询未产生画像更新摘要。")])
        if errors:
            lines.extend(["", "## 运行降级与错误", ""])
            lines.extend(f"- {error}" for error in errors)
        return "\n".join(lines)

    def build_vision_query_report(
        self,
        question: str,
        vision_result: dict[str, Any],
        planned_query: dict[str, Any],
        recommendations: list[dict[str, Any]],
        follow_up_recommendations: list[dict[str, Any]],
        profile_update: dict[str, Any],
        summaries: list[dict[str, Any]] | None = None,
        errors: list[str] | None = None,
    ) -> str:
        lines = [
            "# 多模态查询报告",
            "",
            "## 图片理解",
            "",
            f"- 图片类型：{vision_result.get('image_type', 'other')}",
            f"- 用户问题：{question or '未提供'}",
            f"- 视觉模型可用：{bool(vision_result.get('provider_available'))}",
            "",
            str(vision_result.get("main_content") or "暂无图片解释。"),
            "",
            "## 关键信息",
            "",
        ]
        findings = vision_result.get("key_findings") or []
        if findings:
            lines.extend(f"- {finding}" for finding in findings)
        else:
            lines.append("- 暂无可展示的图片关键信息。")

        lines.extend(
            [
                "",
                "## 推荐关键词",
                "",
                ", ".join(planned_query.get("keywords", [])) or "暂无可用关键词",
                "",
                "## 相关论文推荐",
                "",
            ]
        )
        if recommendations:
            for index, paper in enumerate(recommendations, start=1):
                lines.extend(
                    [
                        f"{index}. **[{paper.get('title', 'Untitled')}]({paper.get('url', '')})**",
                        f"   - 推荐分数：{float(paper.get('score', 0.0)):.3f}",
                        f"   - 推荐理由：{paper.get('reason', '')}",
                    ]
                )
        else:
            lines.append("暂未检索到可推荐论文。")

        if summaries:
            lines.extend(["", "## 简要摘要", ""])
            for summary in summaries:
                lines.extend(
                    [
                        f"### {summary.get('title', 'Untitled')}",
                        "",
                        f"- 研究问题：{summary.get('problem', '')}",
                        f"- 方法：{summary.get('method', '')}",
                        f"- 贡献：{summary.get('contribution', '')}",
                        "",
                    ]
                )

        lines.extend(["", "## 额外 3 篇未出现论文", ""])
        if follow_up_recommendations:
            for index, paper in enumerate(follow_up_recommendations, start=1):
                lines.append(f"{index}. **[{paper.get('title', 'Untitled')}]({paper.get('url', '')})**")
        else:
            lines.append("暂无额外未出现论文。")

        lines.extend(["", "## 画像更新摘要", "", profile_update.get("summary", "本次图片未产生画像更新摘要。")])
        if errors:
            lines.extend(["", "## 运行降级与错误", ""])
            lines.extend(f"- {error}" for error in errors)
        return "\n".join(lines)
