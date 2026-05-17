from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_io_normalizer.adapters.openai_compatible import OpenAICompatibleGateway


# ==========================================
# 辅助函数：构建 Mock 的 Request 和 Result
# ==========================================
def create_mock_request(stream: bool, fallback: bool, thinking: bool, retry_thinking: bool):
    req = MagicMock()
    req.model_name = "mock-model"
    req.stream = stream
    req.fallback_to_non_stream = fallback
    req.enable_thinking = thinking
    req.retry_without_thinking_when_empty = retry_thinking

    # 模拟 with_updates 方法
    def mock_with_updates(**kwargs):
        new_req = create_mock_request(
            stream=kwargs.get("stream", stream),
            fallback=fallback,
            thinking=kwargs.get("enable_thinking", thinking),
            retry_thinking=retry_thinking,
        )
        return new_req
    
    req.with_updates.side_effect = mock_with_updates
    return req

def create_mock_result(ok: bool, error_type: str = None):
    res = MagicMock()
    res.ok = ok
    res.error_type = error_type
    res.error_message = "mock error message" if not ok else None
    return res

# ==========================================
# 降级防御测试用例
# ==========================================
@pytest.mark.asyncio
async def test_stream_fallback_to_non_stream():
    """测试流式中断 (EMPTY_ANSWER) 时，自动降级为非流式重试"""
    gateway = OpenAICompatibleGateway()
    request = create_mock_request(stream=True, fallback=True, thinking=False, retry_thinking=False)
    
    bad_stream_res = create_mock_result(ok=False, error_type="EMPTY_ANSWER")
    good_non_stream_res = create_mock_result(ok=True)

    with patch.object(gateway, "_generate_stream", new_callable=AsyncMock) as mock_stream, \
         patch.object(gateway, "_generate_non_stream", new_callable=AsyncMock) as mock_non_stream:
        
        mock_stream.return_value = bad_stream_res
        mock_non_stream.return_value = good_non_stream_res
        
        result = await gateway.generate(request)
        
        mock_stream.assert_called_once()
        mock_non_stream.assert_called_once()
        retry_req = mock_non_stream.call_args[0][0]
        assert retry_req.stream is False
        assert result.ok is True


@pytest.mark.asyncio
async def test_stream_error_no_fallback():
    """测试流式遇到普通错误 (如 PROVIDER_ERROR) 时，不应触发 EMPTY_ANSWER 降级"""
    gateway = OpenAICompatibleGateway()
    request = create_mock_request(stream=True, fallback=True, thinking=False, retry_thinking=False)
    network_error_res = create_mock_result(ok=False, error_type="PROVIDER_ERROR")

    with patch.object(gateway, "_generate_stream", new_callable=AsyncMock) as mock_stream, \
         patch.object(gateway, "_generate_non_stream", new_callable=AsyncMock) as mock_non_stream:
        mock_stream.return_value = network_error_res
        result = await gateway.generate(request)
        
        mock_stream.assert_called_once()
        mock_non_stream.assert_not_called()
        assert result.ok is False
        assert result.error_type == "PROVIDER_ERROR"


@pytest.mark.asyncio
async def test_thinking_retry_fallback():
    """测试模型因为过度思考吞掉答案时，自动关闭思考重试"""
    gateway = OpenAICompatibleGateway()
    request = create_mock_request(stream=False, fallback=False, thinking=True, retry_thinking=True)
    
    bad_res = create_mock_result(ok=False, error_type="EMPTY_ANSWER")
    good_res = create_mock_result(ok=True)

    with patch.object(gateway, "_generate_non_stream", new_callable=AsyncMock) as mock_non_stream:
        mock_non_stream.side_effect = [bad_res, good_res]
        result = await gateway.generate(request)
        
        assert mock_non_stream.call_count == 2
        retry_req = mock_non_stream.call_args_list[1][0][0]
        assert retry_req.enable_thinking is False
        assert result.ok is True


@pytest.mark.asyncio
async def test_thinking_retry_disabled():
    """测试当 retry_without_thinking_when_empty 关闭时，不触发思考降级"""
    gateway = OpenAICompatibleGateway()
    # 关键修改：retry_thinking=False
    request = create_mock_request(stream=False, fallback=False, thinking=True, retry_thinking=False)
    bad_res = create_mock_result(ok=False, error_type="EMPTY_ANSWER")

    with patch.object(gateway, "_generate_non_stream", new_callable=AsyncMock) as mock_non_stream:
        mock_non_stream.return_value = bad_res
        result = await gateway.generate(request)
        
        mock_non_stream.assert_called_once()
        assert result.ok is False