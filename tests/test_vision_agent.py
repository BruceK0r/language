from paper_agent.agents.vision_agent import VisionAgent


class StaticVisionProvider:
    model = "static-vision"

    def analyze_image(self, image_bytes, mime_type, prompt=None):
        assert image_bytes == b"image-bytes"
        assert mime_type == "image/png"
        assert "What related papers" in prompt
        return (
            "The image is a model architecture diagram for a multi-agent RAG system. "
            "It contains retrieval, agent memory, an LLM agent planner, and an evaluation table."
        )


class FailingVisionProvider:
    model = "broken-vision"

    def analyze_image(self, image_bytes, mime_type, prompt=None):
        raise RuntimeError("missing vision api key")


class ApiKeyArchitectureVisionProvider:
    model = "glm-4.6v"

    def analyze_image(self, image_bytes, mime_type, prompt=None):
        return (
            "This is a model architecture diagram. The agent controller redirects "
            "base_url and api_key to an inference service, then sends trajectories "
            "to an online reinforcement learning training service."
        )


def test_vision_agent_structures_provider_output():
    agent = VisionAgent(provider=StaticVisionProvider())

    result = agent.analyze(
        b"image-bytes",
        mime_type="image/png",
        question="What related papers should I read?",
    )

    assert result["image_type"] == "model_architecture"
    assert result["provider_available"] is True
    assert "multi-agent RAG system" in result["main_content"]
    assert result["key_findings"]
    assert "multi-agent" in result["recommendation_keywords"]
    assert "rag" in result["recommendation_keywords"]
    assert "agent memory" in result["recommendation_keywords"]
    assert result["raw_explanation"].startswith("The image is")


def test_vision_agent_returns_friendly_result_when_provider_fails():
    agent = VisionAgent(provider=FailingVisionProvider())

    result = agent.analyze(b"image-bytes", mime_type="image/png")

    assert result["image_type"] == "other"
    assert result["provider_available"] is False
    assert "当前未配置视觉模型" in result["main_content"]
    assert result["key_findings"] == []
    assert result["recommendation_keywords"] == []
    assert "missing vision api key" in result["error"]


def test_vision_agent_keeps_successful_output_that_mentions_api_key():
    agent = VisionAgent(provider=ApiKeyArchitectureVisionProvider())

    result = agent.analyze(
        b"image-bytes",
        mime_type="image/png",
        question="Which paper is this architecture from?",
    )

    assert result["provider_available"] is True
    assert result["error"] == ""
    assert "api_key" in result["main_content"]
    assert result["provider_model"] == "glm-4.6v"
