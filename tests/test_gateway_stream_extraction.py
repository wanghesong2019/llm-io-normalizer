from types import SimpleNamespace

from llm_io_normalizer.adapters.openai_compatible import OpenAICompatibleGateway


def test_extract_delta_content_and_reasoning_attributes():
    gateway = OpenAICompatibleGateway()
    delta = SimpleNamespace(content="answer", reasoning="think", reasoning_content="think2")
    assert gateway._extract_delta_content(delta) == "answer"
    assert gateway._extract_delta_reasoning(delta) == "thinkthink2"


def test_extract_delta_dict():
    gateway = OpenAICompatibleGateway()
    delta = {"content": "answer", "reasoning": "think"}
    assert gateway._extract_delta_content(delta) == "answer"
    assert gateway._extract_delta_reasoning(delta) == "think"
