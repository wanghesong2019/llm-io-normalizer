from llm_io_normalizer.normalizers import normalize_reasoning_answer, split_think_tag


def test_split_think_tag():
    parsed = split_think_tag("<think>plan</think>final")
    assert parsed is not None
    assert parsed.reasoning_text == "plan"
    assert parsed.answer_text == "final"
    assert parsed.parse_method == "think_tag"


def test_native_reasoning_wins():
    parsed = normalize_reasoning_answer(content_text="final", native_reasoning_text="thought")
    assert parsed.reasoning_text == "thought"
    assert parsed.answer_text == "final"
    assert parsed.parse_method == "native_reasoning"


def test_content_only():
    parsed = normalize_reasoning_answer(content_text="hello")
    assert parsed.reasoning_text == ""
    assert parsed.answer_text == "hello"
    assert parsed.parse_method == "content_only"
