from __future__ import annotations

from llm_io_normalizer.adapters import OpenAICompatibleGateway
from llm_io_normalizer.schemas import LLMRequest, LLMResult


class LLMGateway:
    """Facade for Model IO normalization.

    The first release delegates to an OpenAI-compatible adapter. Additional
    adapters can be added without changing business code.
    """

    def __init__(self, adapter: OpenAICompatibleGateway | None = None) -> None:
        self.adapter = adapter or OpenAICompatibleGateway()

    async def generate(self, request: LLMRequest) -> LLMResult:
        return await self.adapter.generate(request)
