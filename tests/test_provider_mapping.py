from llm_io_normalizer.adapters.openai_compatible import (
    OpenAICompatibleGateway,
    ProviderFieldMapping,
)


class MockMessage:
    """Mock OpenAI Object for testing attribute extraction."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_default_mapping_extraction():
    """测试默认的字段映射规则 (支持主流厂商如 DeepSeek 的 reasoning_content 等)"""
    gateway = OpenAICompatibleGateway()
    
    # 场景 1：以 Object 形式返回
    msg_obj = MockMessage(content="这是答案", reasoning_content="这是思考过程")
    assert gateway._extract_message_content(msg_obj) == "这是答案"
    assert gateway._extract_message_reasoning(msg_obj) == "这是思考过程"

    # 场景 2：以 Dict 形式返回 (部分代理网关会返回字典)
    msg_dict = {"content": "回答部分", "thoughts": "思考部分"}
    assert gateway._extract_message_content(msg_dict) == "回答部分"
    assert gateway._extract_message_reasoning(msg_dict) == "思考部分"

    # 场景 3：缺失推理字段时，不能影响回答提取
    msg_clean = MockMessage(content="直接回答")
    assert gateway._extract_message_content(msg_clean) == "直接回答"
    assert gateway._extract_message_reasoning(msg_clean) == ""


def test_custom_mapping_extraction():
    """测试注入自定义的字段映射 (解耦硬编码的核心价值)"""
    # 假设某个新厂商把字段叫 message_body 和 chain_of_thought
    custom_mapping = ProviderFieldMapping(
        content_fields=("message_body", "text"),
        reasoning_fields=("chain_of_thought", "deep_thought")
    )
    gateway = OpenAICompatibleGateway(field_mapping=custom_mapping)

    # 测试自定义字段能被正确提取
    msg_custom = MockMessage(message_body="定制回答", chain_of_thought="深度思考")
    assert gateway._extract_message_content(msg_custom) == "定制回答"
    assert gateway._extract_message_reasoning(msg_custom) == "深度思考"

    # 测试原有的默认字段 (content, reasoning_content) 应该被忽略
    msg_old = MockMessage(content="旧答案", reasoning_content="旧思考")
    assert gateway._extract_message_content(msg_old) == ""
    assert gateway._extract_message_reasoning(msg_old) == ""