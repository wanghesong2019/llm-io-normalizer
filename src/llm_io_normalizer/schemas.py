from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Literal


class LLMRole(str, Enum):
    """Role-specific call policy."""

    TESTED_MODEL = "tested_model"
    JUDGE_MODEL = "judge_model"


class LLMMode(str, Enum):
    STREAM = "stream"
    NON_STREAM = "non_stream"


@dataclass(frozen=True)
class LLMRequest:
    """Portable request contract for an LLM call.

    `role` is deliberately part of the request because tested-model calls and
    judge-model calls should use different defaults.
    """

    model_name: str
    messages: list[dict[str, Any]]
    role: LLMRole | str = LLMRole.TESTED_MODEL

    api_key: str | None = None
    base_url: str | None = None

    stream: bool | None = None
    enable_thinking: bool | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None

    response_format: Literal["text", "json"] = "text"
    timeout: float | None = None
    extra_body: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Fallback behavior
    fallback_to_non_stream: bool = True
    retry_without_thinking_when_empty: bool = True

    def normalized_role(self) -> LLMRole:
        if isinstance(self.role, LLMRole):
            return self.role
        return LLMRole(self.role)

    def with_updates(self, **updates: Any) -> LLMRequest:
        return replace(self, **updates)


@dataclass(frozen=True)
class LLMResult:
    """Portable result contract returned by gateway.generate()."""

    ok: bool
    model_name: str
    mode: LLMMode | str

    answer_text: str = ""
    reasoning_text: str = ""
    raw_text: str = ""

    # Low-level raw channels before final normalization
    content_text: str = ""
    native_reasoning_text: str = ""

    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)

    parse_method: str | None = None
    confidence: float | None = None

    error_type: str | None = None
    error_message: str | None = None

    raw_chunks_sample: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def require_ok(self) -> LLMResult:
        if not self.ok:
            raise RuntimeError(f"LLM call failed: {self.error_type}: {self.error_message}")
        return self
