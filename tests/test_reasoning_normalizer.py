from llm_io_normalizer.normalizers import normalize_reasoning_answer, split_think_tag


# ==========================================
# 1. 针对底层提取函数 split_think_tag 的独立测试
# ==========================================
def test_split_think_tag():
    parsed = split_think_tag("<think>plan</think>final")
    assert parsed is not None
    assert parsed.reasoning_text == "plan"
    assert parsed.answer_text == "final"
    assert parsed.parse_method == "think_tag"


# ==========================================
# 2. 针对总入口 normalize_reasoning_answer 的全面测试
# ==========================================
def test_normalize_native_reasoning():
    # 原生通道有思考内容，正文干净 (覆盖了原有的 test_native_reasoning_wins)
    res = normalize_reasoning_answer(
        content_text="最终答案是 42",
        native_reasoning_text="这是一道简单的数学题，先乘除后加减。"
    )
    assert res.reasoning_text == "这是一道简单的数学题，先乘除后加减。"
    assert res.answer_text == "最终答案是 42"
    assert res.parse_method == "native_reasoning"
    assert res.confidence == 0.95


def test_normalize_single_think_tag():
    # 基础的标签包裹
    res = normalize_reasoning_answer(content_text="<think> 思考过程 </think> 最终答案")
    assert res.reasoning_text == "思考过程"
    assert res.answer_text == "最终答案"
    assert res.parse_method == "think_tag"


def test_normalize_multiple_think_tags():
    # 模型交替输出思考和正文
    content = "你好，<think>第一步</think>中间穿插<think>第二步</think>最终回答"
    res = normalize_reasoning_answer(content_text=content)
    assert res.reasoning_text == "第一步\n第二步"
    assert res.answer_text == "你好，中间穿插最终回答"
    assert res.parse_method == "think_tag"


def test_normalize_unclosed_think_tag():
    # 最致命的流式断流/Token截断场景
    content = "开场白 <think> 思考了一半突然断流，没有闭合标签"
    res = normalize_reasoning_answer(content_text=content)
    assert res.reasoning_text == "思考了一半突然断流，没有闭合标签"
    assert res.answer_text == "开场白"
    assert res.parse_method == "think_tag"


def test_normalize_content_only():
    # 纯回答兜底 (覆盖了原有的 test_content_only)
    res = normalize_reasoning_answer(content_text="纯回答没有任何标签")
    assert res.reasoning_text == ""
    assert res.answer_text == "纯回答没有任何标签"
    assert res.parse_method == "content_only"
    assert res.confidence == 0.70


def test_native_reasoning_with_redundant_tags():
    # 厂商返回了原生 reasoning，但 content 依然带着重复的 think 标签
    res = normalize_reasoning_answer(
        content_text="<think> 重复混入正文的思考 </think> 真正的纯净回答",
        native_reasoning_text="原生思考通道里的过程"
    )
    assert res.reasoning_text == "原生思考通道里的过程"
    assert res.answer_text == "真正的纯净回答"
    assert res.parse_method == "native_reasoning"


def test_normalize_empty_input():
    # 空输入边界
    res = normalize_reasoning_answer(content_text="", native_reasoning_text="")
    assert res.reasoning_text == ""
    assert res.answer_text == ""
    assert res.parse_method == "content_only"


def test_normalize_tag_in_text():
    # 验证没有滥用 replace，正文中单独出现的闭合词不会误伤
    content = "模型的机制是 <think> 这是思考 </think>，结尾加上 </think> 作为标识。"
    res = normalize_reasoning_answer(content_text=content)
    assert res.reasoning_text == "这是思考"
    assert res.answer_text == "模型的机制是 ，结尾加上 </think> 作为标识。"