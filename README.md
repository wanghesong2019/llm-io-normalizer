# llm-io-normalizer

`llm-io-normalizer` is a lightweight **Model I/O normalization layer** for OpenAI-compatible LLM calls.
It is built for applications that call both **tested models** and **judge models** and need a stable result contract instead of provider-specific response parsing.

It normalizes common LLM response differences such as:

- `message.content` vs `message.reasoning`
- `delta.content` vs `delta.reasoning` / `delta.reasoning_content`
- `<think>...</think>` reasoning mixed into normal content
- stream vs non-stream completion behavior
- successful HTTP responses that contain reasoning but no final answer
- final JSON extraction from model output

The public contract is intentionally small and stable:

```python
result.answer_text
result.reasoning_text
result.ok
result.error_type
result.error_message
```

Business code should depend on these normalized fields instead of reading raw provider fields directly.

## Install

After publishing to PyPI:

```bash
pip install llm-io-normalizer
```

From a local checkout:

```bash
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick start

```python
import asyncio

from llm_io_normalizer import LLMGateway, LLMRequest, LLMRole


async def main() -> None:
    gateway = LLMGateway()

    result = await gateway.generate(
        LLMRequest(
            role=LLMRole.JUDGE_MODEL,
            model_name="your-model-name",
            base_url="https://example.com/v1",
            api_key="YOUR_API_KEY",
            messages=[
                {"role": "system", "content": "You are a strict JSON judge."},
                {"role": "user", "content": "Return {\"result\": 2}."},
            ],
            # Judge models should usually prefer stable non-stream output.
            stream=False,
            enable_thinking=False,
            temperature=0,
            max_tokens=1024,
        )
    )

    result.require_ok()
    print(result.answer_text)


asyncio.run(main())
```

## Core concepts

### Tested model calls

`LLMRole.TESTED_MODEL` is for the model being evaluated or observed.

Default behavior:

- streams by default unless `stream=False` is provided
- can collect native reasoning fields from compatible providers
- can split `<think>...</think>` blocks out of the answer
- returns clean `answer_text` and separate `reasoning_text`
- can retry without thinking when the provider returns no final answer

### Judge model calls

`LLMRole.JUDGE_MODEL` is for scoring, evaluation, moderation, ranking, or structured judgment tasks.

Default behavior:

- uses non-stream mode by default unless `stream=True` is provided
- is designed for stable final output, especially JSON scoring results
- usually pairs well with `enable_thinking=False` and `temperature=0`
- marks the call as `ok=False` with `error_type="EMPTY_ANSWER"` when the provider returns reasoning but no final answer

## JSON output helper

```python
from llm_io_normalizer.normalizers import extract_json_object

obj = extract_json_object('```json\n{"result": 2}\n```')
assert obj == {"result": 2}
```

## Examples

The `examples/` directory contains runnable examples for:

- tested-model calls
- judge-model calls
- a tested-model → judge-model evaluation pipeline

Use environment variables for provider credentials and endpoints when running examples:

```bash
export LLM_BASE_URL="https://your-provider.example/v1"
export LLM_API_KEY="your-api-key"
export LLM_MODEL="your-model-name"
python examples/judge_model.py
```

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest
python -m build
```

## Release

Recommended PyPI release mode is **Trusted Publishing** from GitHub Actions.
Configure the PyPI project to trust this repository workflow, then publish a GitHub release tag such as `v0.1.0`.

## Scope

This package is intentionally **not** a full API gateway.
It does not implement authentication, rate limiting, billing, routing dashboards, or multi-tenant governance.
Those can be handled by an outer gateway such as Kong, APISIX, Envoy, Portkey, or other infrastructure.

`llm-io-normalizer` focuses on the reusable Python SDK layer:

- Model I/O normalization
- reasoning / answer separation
- stream / non-stream fallback
- tested-model and judge-model call policies
- unified result/error contract
- simple JSON object extraction from model output
