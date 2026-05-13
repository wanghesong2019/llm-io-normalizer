"""Example: tested-model response followed by judge-model evaluation.

Usage:
  export TESTED_LLM_API_KEY=...
  export TESTED_LLM_BASE_URL=https://tested-provider.example/v1
  export TESTED_LLM_MODEL=your-tested-model

  export JUDGE_LLM_API_KEY=...
  export JUDGE_LLM_BASE_URL=https://judge-provider.example/v1
  export JUDGE_LLM_MODEL=your-judge-model

  python examples/evaluation_pipeline.py
"""

import asyncio
import os

from llm_io_normalizer import LLMGateway, LLMRequest, LLMRole


async def request_tested_model(gateway: LLMGateway, question: str) -> tuple[str, str]:
    """Call the tested model and return reasoning plus final answer."""
    result = await gateway.generate(
        LLMRequest(
            role=LLMRole.TESTED_MODEL,
            model_name=os.getenv("TESTED_LLM_MODEL", "your-tested-model"),
            base_url=os.environ["TESTED_LLM_BASE_URL"],
            api_key=os.environ["TESTED_LLM_API_KEY"],
            messages=[{"role": "user", "content": question}],
            stream=True,
            enable_thinking=True,
            temperature=0.1,
            max_tokens=4096,
        )
    )
    result.require_ok()
    return result.reasoning_text, result.answer_text


async def request_judge_model(gateway: LLMGateway, system_prompt: str, user_prompt: str):
    """Call the judge model and return the normalized result object."""
    result = await gateway.generate(
        LLMRequest(
            role=LLMRole.JUDGE_MODEL,
            model_name=os.getenv("JUDGE_LLM_MODEL", "your-judge-model"),
            base_url=os.environ["JUDGE_LLM_BASE_URL"],
            api_key=os.environ["JUDGE_LLM_API_KEY"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
            enable_thinking=False,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            temperature=0,
            max_tokens=4096,
        )
    )
    result.require_ok()
    return result


async def main() -> None:
    gateway = LLMGateway()
    question = "用一句话介绍杭州西湖。"

    print(">>> Requesting tested model...")
    reasoning, answer = await request_tested_model(gateway, question)
    print("Tested-model reasoning:\n", reasoning)
    print("Tested-model answer:\n", answer)

    system_prompt = "你是一个客观评分裁判。请只输出 JSON，不输出思考过程。"
    user_prompt = f"""
[Evaluation Task]
Question: {question}
Model answer: {answer}

Score whether the answer is relevant. Output JSON: {{"relevant": true/false, "comment": "..."}}
""".strip()

    print(">>> Requesting judge model...")
    judge_result = await request_judge_model(gateway, system_prompt, user_prompt)
    print("Judge answer:\n", judge_result.answer_text)


if __name__ == "__main__":
    asyncio.run(main())
