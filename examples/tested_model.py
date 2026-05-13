"""Run a tested-model call through llm-io-normalizer.

Usage:
  export LLM_API_KEY=...
  export LLM_BASE_URL=https://your-provider.example/v1
  export LLM_MODEL=your-tested-model
  python examples/tested_model.py
"""

import asyncio
import os

from llm_io_normalizer import LLMGateway, LLMRequest, LLMRole


async def main() -> None:
    gateway = LLMGateway()
    result = await gateway.generate(
        LLMRequest(
            role=LLMRole.TESTED_MODEL,
            model_name=os.getenv("LLM_MODEL", "your-tested-model"),
            base_url=os.environ["LLM_BASE_URL"],
            api_key=os.environ["LLM_API_KEY"],
            messages=[{"role": "user", "content": "用一句话介绍杭州西湖。"}],
            stream=True,
            enable_thinking=True,
            temperature=0.1,
            max_tokens=1024,
        )
    )
    print("OK:", result.ok)
    print("Reasoning:", result.reasoning_text[:300])
    print("Answer:", result.answer_text)


if __name__ == "__main__":
    asyncio.run(main())
