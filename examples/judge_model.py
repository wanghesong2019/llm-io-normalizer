"""Run a judge-model call through llm-io-normalizer.

Usage:
  export LLM_API_KEY=...
  export LLM_BASE_URL=https://your-provider.example/v1
  export LLM_MODEL=your-judge-model
  python examples/judge_model.py
"""

import asyncio
import os

from llm_io_normalizer import LLMGateway, LLMRequest, LLMRole


async def main() -> None:
    gateway = LLMGateway()
    result = await gateway.generate(
        LLMRequest(
            role=LLMRole.JUDGE_MODEL,
            model_name=os.getenv("LLM_MODEL", "your-judge-model"),
            base_url=os.environ["LLM_BASE_URL"],
            api_key=os.environ["LLM_API_KEY"],
            messages=[
                {"role": "system", "content": "你是一个只输出 JSON 的评分裁判。"},
                {"role": "user", "content": "请判断文本是否积极：文本=\"这个工具很有帮助\"。输出 {\"score\": 0 或 1}。"},
            ],
            stream=False,
            enable_thinking=False,
            temperature=0,
            max_tokens=1024,
        )
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
