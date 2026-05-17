# from __future__ import annotations

# import asyncio
# import json
# import logging
# from typing import Any

# from llm_io_normalizer.normalizers import normalize_reasoning_answer
# from llm_io_normalizer.schemas import LLMMode, LLMRequest, LLMResult, LLMRole

# logger = logging.getLogger(__name__)


# class OpenAICompatibleGateway:
#     """OpenAI-compatible adapter with Model IO normalization.

#     This adapter intentionally keeps provider-specific return fields out of
#     business code. It collects content/reasoning from common stream and
#     non-stream locations, then normalizes them into answer_text/reasoning_text.
#     """

#     def __init__(self, *, default_timeout: float | None = 120) -> None:
#         self.default_timeout = default_timeout

#     async def generate(self, request: LLMRequest) -> LLMResult:
#         role = request.normalized_role()
#         stream = self._select_stream_default(request, role)

#         if stream:
#             result = await self._generate_stream(request)
#             if result.ok:
#                 return result

#             if request.fallback_to_non_stream and result.error_type == "EMPTY_ANSWER":
#                 logger.warning(
#                     "[LLMGatewayFallback] model=%s role=%s action=retry_non_stream reason=%s",
#                     request.model_name,
#                     role.value,
#                     result.error_message,
#                 )
#                 return await self._generate_non_stream(request.with_updates(stream=False))
#             return result

#         result = await self._generate_non_stream(request)
#         if result.ok:
#             return result

#         # For tested models, if thinking consumed the final answer, retry once without thinking.
#         if (
#             role == LLMRole.TESTED_MODEL
#             and request.retry_without_thinking_when_empty
#             and request.enable_thinking is True
#             and result.error_type == "EMPTY_ANSWER"
#         ):
#             logger.warning(
#                 "[LLMGatewayFallback] model=%s role=%s action=retry_without_thinking",
#                 request.model_name,
#                 role.value,
#             )
#             return await self.generate(request.with_updates(enable_thinking=False))

#         return result

#     def _select_stream_default(self, request: LLMRequest, role: LLMRole) -> bool:
#         if request.stream is not None:
#             return bool(request.stream)
#         # Judge calls should prefer non-stream because final JSON should be stable.
#         if role == LLMRole.JUDGE_MODEL:
#             return False
#         return True

#     def _client(self, request: LLMRequest):
#         from openai import OpenAI

#         kwargs: dict[str, Any] = {}
#         if request.api_key:
#             kwargs["api_key"] = request.api_key
#         if request.base_url:
#             kwargs["base_url"] = request.base_url
#         timeout = request.timeout if request.timeout is not None else self.default_timeout
#         if timeout is not None:
#             kwargs["timeout"] = timeout
#         return OpenAI(**kwargs)

#     def _extra_body(self, request: LLMRequest) -> dict[str, Any] | None:
#         body = dict(request.extra_body or {})
#         if request.enable_thinking is not None:
#             body.setdefault("enable_thinking", request.enable_thinking)
#         return body or None

#     def _common_kwargs(self, request: LLMRequest) -> dict[str, Any]:
#         kwargs: dict[str, Any] = {
#             "model": request.model_name,
#             "messages": request.messages,
#         }
#         if request.temperature is not None:
#             kwargs["temperature"] = request.temperature
#         if request.top_p is not None:
#             kwargs["top_p"] = request.top_p
#         if request.max_tokens is not None:
#             kwargs["max_tokens"] = request.max_tokens
#         extra_body = self._extra_body(request)
#         if extra_body is not None:
#             kwargs["extra_body"] = extra_body
#         return kwargs

#     async def _generate_non_stream(self, request: LLMRequest) -> LLMResult:
#         client = self._client(request)
#         kwargs = self._common_kwargs(request)
#         kwargs["stream"] = False

#         logger.info(
#             "[LLMGatewayRequest] mode=non_stream role=%s model=%s messages=%s",
#             request.normalized_role().value,
#             request.model_name,
#             len(request.messages),
#         )

#         try:
#             response = await asyncio.to_thread(lambda: client.chat.completions.create(**kwargs))
#         except Exception as exc:
#             logger.exception("[LLMGatewayError] mode=non_stream model=%s", request.model_name)
#             return LLMResult(
#                 ok=False,
#                 model_name=request.model_name,
#                 mode=LLMMode.NON_STREAM,
#                 error_type="PROVIDER_ERROR",
#                 error_message=str(exc),
#             )

#         if not response.choices:
#             return LLMResult(
#                 ok=False,
#                 model_name=request.model_name,
#                 mode=LLMMode.NON_STREAM,
#                 error_type="EMPTY_CHOICES",
#                 error_message="Provider returned no choices.",
#             )

#         choice = response.choices[0]
#         msg = choice.message
#         finish_reason = getattr(choice, "finish_reason", None)

#         content_text = getattr(msg, "content", None) or ""
#         native_reasoning = self._extract_message_reasoning(msg)
#         usage = self._safe_model_dump(getattr(response, "usage", None))

#         return self._finalize_result(
#             request=request,
#             mode=LLMMode.NON_STREAM,
#             content_text=content_text,
#             native_reasoning_text=native_reasoning,
#             finish_reason=finish_reason,
#             usage=usage,
#             raw_chunks_sample=[],
#         )

#     async def _generate_stream(self, request: LLMRequest) -> LLMResult:
#         client = self._client(request)
#         kwargs = self._common_kwargs(request)
#         kwargs["stream"] = True

#         logger.info(
#             "[LLMGatewayRequest] mode=stream role=%s model=%s messages=%s",
#             request.normalized_role().value,
#             request.model_name,
#             len(request.messages),
#         )

#         content_text = ""
#         native_reasoning = ""
#         finish_reason: str | None = None
#         raw_chunks_sample: list[dict[str, Any]] = []
#         chunk_count = 0

#         try:
#             stream = await asyncio.to_thread(lambda: client.chat.completions.create(**kwargs))
#             for chunk in stream:
#                 chunk_count += 1
#                 if len(raw_chunks_sample) < 3:
#                     raw_chunks_sample.append(self._safe_model_dump(chunk))

#                 if not getattr(chunk, "choices", None):
#                     continue
#                 choice = chunk.choices[0]
#                 if getattr(choice, "finish_reason", None):
#                     finish_reason = choice.finish_reason
#                 delta = getattr(choice, "delta", None)
#                 if delta is None:
#                     continue

#                 content_text += self._extract_delta_content(delta)
#                 native_reasoning += self._extract_delta_reasoning(delta)
#         except Exception as exc:
#             logger.exception("[LLMGatewayError] mode=stream model=%s", request.model_name)
#             return LLMResult(
#                 ok=False,
#                 model_name=request.model_name,
#                 mode=LLMMode.STREAM,
#                 error_type="PROVIDER_ERROR",
#                 error_message=str(exc),
#                 raw_chunks_sample=raw_chunks_sample,
#             )

#         result = self._finalize_result(
#             request=request,
#             mode=LLMMode.STREAM,
#             content_text=content_text,
#             native_reasoning_text=native_reasoning,
#             finish_reason=finish_reason,
#             usage={},
#             raw_chunks_sample=raw_chunks_sample,
#         )
#         result.metadata.update({"chunk_count": chunk_count})
#         return result

#     def _finalize_result(
#         self,
#         *,
#         request: LLMRequest,
#         mode: LLMMode,
#         content_text: str,
#         native_reasoning_text: str,
#         finish_reason: str | None,
#         usage: dict[str, Any],
#         raw_chunks_sample: list[dict[str, Any]],
#     ) -> LLMResult:
#         normalized = normalize_reasoning_answer(
#             content_text=content_text,
#             native_reasoning_text=native_reasoning_text,
#             role=request.normalized_role().value,
#         )

#         answer = normalized.answer_text
#         reasoning = normalized.reasoning_text

#         ok = bool(answer.strip())
#         error_type = None if ok else "EMPTY_ANSWER"
#         error_message = None
#         if not ok:
#             if native_reasoning_text.strip():
#                 error_message = "Provider returned reasoning but no final answer content."
#             else:
#                 error_message = "Provider returned no final answer content."

#         logger.info(
#             "[LLMGatewayResult] mode=%s role=%s model=%s ok=%s answer_len=%s reasoning_len=%s parse=%s",
#             mode.value,
#             request.normalized_role().value,
#             request.model_name,
#             ok,
#             len(answer or ""),
#             len(reasoning or ""),
#             normalized.parse_method,
#         )

#         return LLMResult(
#             ok=ok,
#             model_name=request.model_name,
#             mode=mode,
#             answer_text=answer,
#             reasoning_text=reasoning,
#             raw_text=normalized.raw_text,
#             content_text=content_text,
#             native_reasoning_text=native_reasoning_text,
#             finish_reason=finish_reason,
#             usage=usage,
#             parse_method=normalized.parse_method,
#             confidence=normalized.confidence,
#             error_type=error_type,
#             error_message=error_message,
#             raw_chunks_sample=raw_chunks_sample,
#             metadata={"role": request.normalized_role().value},
#         )

#     def _extract_message_reasoning(self, msg: Any) -> str:
#         parts: list[str] = []
#         for field in ("reasoning", "reasoning_content", "thoughts", "reason"):
#             value = getattr(msg, field, None)
#             if value:
#                 parts.append(str(value))
#         if isinstance(msg, dict):
#             for field in ("reasoning", "reasoning_content", "thoughts", "reason"):
#                 if msg.get(field):
#                     parts.append(str(msg[field]))
#         return "".join(parts)

#     def _extract_delta_content(self, delta: Any) -> str:
#         value = getattr(delta, "content", None)
#         if value:
#             return str(value)
#         if isinstance(delta, dict) and delta.get("content"):
#             return str(delta["content"])
#         return ""

#     def _extract_delta_reasoning(self, delta: Any) -> str:
#         parts: list[str] = []
#         for field in ("reasoning", "reasoning_content", "thoughts", "reason"):
#             value = getattr(delta, field, None)
#             if value:
#                 parts.append(str(value))
#         if isinstance(delta, dict):
#             for field in ("reasoning", "reasoning_content", "thoughts", "reason"):
#                 if delta.get(field):
#                     parts.append(str(delta[field]))
#         return "".join(parts)

#     def _safe_model_dump(self, obj: Any) -> dict[str, Any]:
#         if obj is None:
#             return {}
#         if isinstance(obj, dict):
#             return obj
#         if hasattr(obj, "model_dump"):
#             try:
#                 return obj.model_dump()
#             except Exception:
#                 pass
#         if hasattr(obj, "dict"):
#             try:
#                 return obj.dict()
#             except Exception:
#                 pass
#         try:
#             return json.loads(json.dumps(obj, default=str))
#         except Exception:
#             return {"repr": repr(obj)}
# from __future__ import annotations

# import asyncio
# import json
# import logging
# from dataclasses import dataclass
# from typing import Any

# from llm_io_normalizer.normalizers import normalize_reasoning_answer
# from llm_io_normalizer.schemas import LLMMode, LLMRequest, LLMResult, LLMRole

# logger = logging.getLogger(__name__)


# @dataclass(frozen=True)
# class ProviderFieldMapping:
#     """Configurable mapping for provider-specific response fields."""
#     content_fields: tuple[str, ...] = ("content",)
#     reasoning_fields: tuple[str, ...] = ("reasoning", "reasoning_content", "thoughts", "reason")


# class OpenAICompatibleGateway:
#     """OpenAI-compatible adapter with Model IO normalization.

#     This adapter intentionally keeps provider-specific return fields out of
#     business code. It collects content/reasoning from common stream and
#     non-stream locations, then normalizes them into answer_text/reasoning_text.
#     """

#     def __init__(
#         self,
#         *,
#         default_timeout: float | None = 120,
#         field_mapping: ProviderFieldMapping | None = None,
#     ) -> None:
#         self.default_timeout = default_timeout
#         self.field_mapping = field_mapping or ProviderFieldMapping()

#     async def generate(self, request: LLMRequest) -> LLMResult:
#         role = request.normalized_role()
#         stream = self._select_stream_default(request, role)

#         if stream:
#             result = await self._generate_stream(request)
#             if result.ok:
#                 return result

#             if request.fallback_to_non_stream and result.error_type == "EMPTY_ANSWER":
#                 logger.warning(
#                     "[LLMGatewayFallback] model=%s role=%s action=retry_non_stream reason=%s",
#                     request.model_name,
#                     role.value,
#                     result.error_message,
#                 )
#                 return await self._generate_non_stream(request.with_updates(stream=False))
#             return result

#         result = await self._generate_non_stream(request)
#         if result.ok:
#             return result

#         # For tested models, if thinking consumed the final answer, retry once without thinking.
#         if (
#             role == LLMRole.TESTED_MODEL
#             and request.retry_without_thinking_when_empty
#             and request.enable_thinking is True
#             and result.error_type == "EMPTY_ANSWER"
#         ):
#             logger.warning(
#                 "[LLMGatewayFallback] model=%s role=%s action=retry_without_thinking",
#                 request.model_name,
#                 role.value,
#             )
#             return await self.generate(request.with_updates(enable_thinking=False))

#         return result

#     def _select_stream_default(self, request: LLMRequest, role: LLMRole) -> bool:
#         if request.stream is not None:
#             return bool(request.stream)
#         # Judge calls should prefer non-stream because final JSON should be stable.
#         if role == LLMRole.JUDGE_MODEL:
#             return False
#         return True

#     def _client(self, request: LLMRequest):
#         from openai import OpenAI

#         kwargs: dict[str, Any] = {}
#         if request.api_key:
#             kwargs["api_key"] = request.api_key
#         if request.base_url:
#             kwargs["base_url"] = request.base_url
#         timeout = request.timeout if request.timeout is not None else self.default_timeout
#         if timeout is not None:
#             kwargs["timeout"] = timeout
#         return OpenAI(**kwargs)

#     def _extra_body(self, request: LLMRequest) -> dict[str, Any] | None:
#         body = dict(request.extra_body or {})
#         if request.enable_thinking is not None:
#             body.setdefault("enable_thinking", request.enable_thinking)
#         return body or None

#     def _common_kwargs(self, request: LLMRequest) -> dict[str, Any]:
#         kwargs: dict[str, Any] = {
#             "model": request.model_name,
#             "messages": request.messages,
#         }
#         if request.temperature is not None:
#             kwargs["temperature"] = request.temperature
#         if request.top_p is not None:
#             kwargs["top_p"] = request.top_p
#         if request.max_tokens is not None:
#             kwargs["max_tokens"] = request.max_tokens
#         extra_body = self._extra_body(request)
#         if extra_body is not None:
#             kwargs["extra_body"] = extra_body
#         return kwargs

#     async def _generate_non_stream(self, request: LLMRequest) -> LLMResult:
#         client = self._client(request)
#         kwargs = self._common_kwargs(request)
#         kwargs["stream"] = False

#         logger.info(
#             "[LLMGatewayRequest] mode=non_stream role=%s model=%s messages=%s",
#             request.normalized_role().value,
#             request.model_name,
#             len(request.messages),
#         )

#         try:
#             response = await asyncio.to_thread(lambda: client.chat.completions.create(**kwargs))
#         except Exception as exc:
#             logger.exception("[LLMGatewayError] mode=non_stream model=%s", request.model_name)
#             return LLMResult(
#                 ok=False,
#                 model_name=request.model_name,
#                 mode=LLMMode.NON_STREAM,
#                 error_type="PROVIDER_ERROR",
#                 error_message=str(exc),
#             )

#         if not response.choices:
#             return LLMResult(
#                 ok=False,
#                 model_name=request.model_name,
#                 mode=LLMMode.NON_STREAM,
#                 error_type="EMPTY_CHOICES",
#                 error_message="Provider returned no choices.",
#             )

#         choice = response.choices[0]
#         msg = choice.message
#         finish_reason = getattr(choice, "finish_reason", None)

#         content_text = self._extract_message_content(msg)
#         native_reasoning = self._extract_message_reasoning(msg)
#         usage = self._safe_model_dump(getattr(response, "usage", None))

#         return self._finalize_result(
#             request=request,
#             mode=LLMMode.NON_STREAM,
#             content_text=content_text,
#             native_reasoning_text=native_reasoning,
#             finish_reason=finish_reason,
#             usage=usage,
#             raw_chunks_sample=[],
#         )

#     async def _generate_stream(self, request: LLMRequest) -> LLMResult:
#         client = self._client(request)
#         kwargs = self._common_kwargs(request)
#         kwargs["stream"] = True

#         logger.info(
#             "[LLMGatewayRequest] mode=stream role=%s model=%s messages=%s",
#             request.normalized_role().value,
#             request.model_name,
#             len(request.messages),
#         )

#         content_text = ""
#         native_reasoning = ""
#         finish_reason: str | None = None
#         raw_chunks_sample: list[dict[str, Any]] = []
#         chunk_count = 0

#         try:
#             stream = await asyncio.to_thread(lambda: client.chat.completions.create(**kwargs))
#             for chunk in stream:
#                 chunk_count += 1
#                 if len(raw_chunks_sample) < 3:
#                     raw_chunks_sample.append(self._safe_model_dump(chunk))

#                 if not getattr(chunk, "choices", None):
#                     continue
#                 choice = chunk.choices[0]
#                 if getattr(choice, "finish_reason", None):
#                     finish_reason = choice.finish_reason
#                 delta = getattr(choice, "delta", None)
#                 if delta is None:
#                     continue

#                 content_text += self._extract_delta_content(delta)
#                 native_reasoning += self._extract_delta_reasoning(delta)
#         except Exception as exc:
#             logger.exception("[LLMGatewayError] mode=stream model=%s", request.model_name)
#             return LLMResult(
#                 ok=False,
#                 model_name=request.model_name,
#                 mode=LLMMode.STREAM,
#                 error_type="PROVIDER_ERROR",
#                 error_message=str(exc),
#                 raw_chunks_sample=raw_chunks_sample,
#             )

#         result = self._finalize_result(
#             request=request,
#             mode=LLMMode.STREAM,
#             content_text=content_text,
#             native_reasoning_text=native_reasoning,
#             finish_reason=finish_reason,
#             usage={},
#             raw_chunks_sample=raw_chunks_sample,
#         )
#         result.metadata.update({"chunk_count": chunk_count})
#         return result

#     def _finalize_result(
#         self,
#         *,
#         request: LLMRequest,
#         mode: LLMMode,
#         content_text: str,
#         native_reasoning_text: str,
#         finish_reason: str | None,
#         usage: dict[str, Any],
#         raw_chunks_sample: list[dict[str, Any]],
#     ) -> LLMResult:
#         normalized = normalize_reasoning_answer(
#             content_text=content_text,
#             native_reasoning_text=native_reasoning_text,
#         )

#         answer = normalized.answer_text
#         reasoning = normalized.reasoning_text

#         ok = bool(answer.strip())
#         error_type = None if ok else "EMPTY_ANSWER"
#         error_message = None
#         if not ok:
#             if native_reasoning_text.strip():
#                 error_message = "Provider returned reasoning but no final answer content."
#             else:
#                 error_message = "Provider returned no final answer content."

#         logger.info(
#             "[LLMGatewayResult] mode=%s role=%s model=%s ok=%s answer_len=%s reasoning_len=%s parse=%s",
#             mode.value,
#             request.normalized_role().value,
#             request.model_name,
#             ok,
#             len(answer or ""),
#             len(reasoning or ""),
#             normalized.parse_method,
#         )

#         return LLMResult(
#             ok=ok,
#             model_name=request.model_name,
#             mode=mode,
#             answer_text=answer,
#             reasoning_text=reasoning,
#             raw_text=normalized.raw_text,
#             content_text=content_text,
#             native_reasoning_text=native_reasoning_text,
#             finish_reason=finish_reason,
#             usage=usage,
#             parse_method=normalized.parse_method,
#             confidence=normalized.confidence,
#             error_type=error_type,
#             error_message=error_message,
#             raw_chunks_sample=raw_chunks_sample,
#             metadata={"role": request.normalized_role().value},
#         )

#     # -------------------------------------------------------------------------
#     # DRY Field Extraction Helpers
#     # -------------------------------------------------------------------------
#     def _extract_field(self, obj: Any, fields: tuple[str, ...], concat: bool = False) -> str:
#         """Helper to extract values from an object or dict based on field names."""
#         parts = []
#         is_dict = isinstance(obj, dict)

#         for field_name in fields:
#             value = None
#             if is_dict:
#                 value = obj.get(field_name)
#             else:
#                 value = getattr(obj, field_name, None)

#             if value:
#                 if not concat:
#                     return str(value)
#                 parts.append(str(value))

#         return "".join(parts) if concat else ""

#     def _extract_message_content(self, msg: Any) -> str:
#         return self._extract_field(msg, self.field_mapping.content_fields, concat=False)

#     def _extract_delta_content(self, delta: Any) -> str:
#         return self._extract_field(delta, self.field_mapping.content_fields, concat=False)

#     def _extract_message_reasoning(self, msg: Any) -> str:
#         return self._extract_field(msg, self.field_mapping.reasoning_fields, concat=True)

#     def _extract_delta_reasoning(self, delta: Any) -> str:
#         return self._extract_field(delta, self.field_mapping.reasoning_fields, concat=True)

#     def _safe_model_dump(self, obj: Any) -> dict[str, Any]:
#         if obj is None:
#             return {}
#         if isinstance(obj, dict):
#             return obj
#         if hasattr(obj, "model_dump"):
#             try:
#                 return obj.model_dump()
#             except Exception:
#                 pass
#         if hasattr(obj, "dict"):
#             try:
#                 return obj.dict()
#             except Exception:
#                 pass
#         try:
#             return json.loads(json.dumps(obj, default=str))
#         except Exception:
#             return {"repr": repr(obj)}


from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from llm_io_normalizer.normalizers import normalize_reasoning_answer
from llm_io_normalizer.schemas import LLMMode, LLMRequest, LLMResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderFieldMapping:
    """Configurable mapping for provider-specific response fields."""
    content_fields: tuple[str, ...] = ("content",)
    reasoning_fields: tuple[str, ...] = ("reasoning", "reasoning_content", "thoughts", "reason")


class OpenAICompatibleGateway:
    """OpenAI-compatible adapter with Model IO normalization."""

    def __init__(
        self,
        *,
        default_timeout: float | None = 120,
        field_mapping: ProviderFieldMapping | None = None,
    ) -> None:
        self.default_timeout = default_timeout
        self.field_mapping = field_mapping or ProviderFieldMapping()

    async def generate(self, request: LLMRequest) -> LLMResult:
        stream = self._select_stream_default(request)

        if stream:
            result = await self._generate_stream(request)
            if result.ok:
                return result

            if request.fallback_to_non_stream and result.error_type == "EMPTY_ANSWER":
                logger.warning(
                    "[LLMGatewayFallback] model=%s action=retry_non_stream reason=%s",
                    request.model_name,
                    result.error_message,
                )
                return await self._generate_non_stream(request.with_updates(stream=False))
            return result

        result = await self._generate_non_stream(request)
        if result.ok:
            return result

        if (
            request.retry_without_thinking_when_empty
            and request.enable_thinking is True
            and result.error_type == "EMPTY_ANSWER"
        ):
            logger.warning(
                "[LLMGatewayFallback] model=%s action=retry_without_thinking",
                request.model_name,
            )
            return await self.generate(request.with_updates(enable_thinking=False))

        return result

    def _select_stream_default(self, request: LLMRequest) -> bool:
        if request.stream is not None:
            return bool(request.stream)
        return True

    def _client(self, request: LLMRequest):
        from openai import OpenAI
        kwargs: dict[str, Any] = {}
        if request.api_key:
            kwargs["api_key"] = request.api_key
        if request.base_url:
            kwargs["base_url"] = request.base_url
        timeout = request.timeout if request.timeout is not None else self.default_timeout
        if timeout is not None:
            kwargs["timeout"] = timeout
        return OpenAI(**kwargs)

    def _extra_body(self, request: LLMRequest) -> dict[str, Any] | None:
        body = dict(request.extra_body or {})
        if request.enable_thinking is not None:
            body.setdefault("enable_thinking", request.enable_thinking)
        return body or None

    def _common_kwargs(self, request: LLMRequest) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": request.model_name,
            "messages": request.messages,
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.top_p is not None:
            kwargs["top_p"] = request.top_p
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        extra_body = self._extra_body(request)
        if extra_body is not None:
            kwargs["extra_body"] = extra_body
        return kwargs

    async def _generate_non_stream(self, request: LLMRequest) -> LLMResult:
        client = self._client(request)
        kwargs = self._common_kwargs(request)
        kwargs["stream"] = False

        logger.info(
            "[LLMGatewayRequest] mode=non_stream model=%s messages=%s",
            request.model_name,
            len(request.messages),
        )

        try:
            response = await asyncio.to_thread(lambda: client.chat.completions.create(**kwargs))
        except Exception as exc:
            logger.exception("[LLMGatewayError] mode=non_stream model=%s", request.model_name)
            return LLMResult(
                ok=False,
                model_name=request.model_name,
                mode=LLMMode.NON_STREAM,
                error_type="PROVIDER_ERROR",
                error_message=str(exc),
            )

        if not response.choices:
            return LLMResult(
                ok=False,
                model_name=request.model_name,
                mode=LLMMode.NON_STREAM,
                error_type="EMPTY_CHOICES",
                error_message="Provider returned no choices.",
            )

        choice = response.choices[0]
        msg = choice.message
        finish_reason = getattr(choice, "finish_reason", None)

        content_text = self._extract_message_content(msg)
        native_reasoning = self._extract_message_reasoning(msg)
        usage = self._safe_model_dump(getattr(response, "usage", None))

        return self._finalize_result(
            request=request,
            mode=LLMMode.NON_STREAM,
            content_text=content_text,
            native_reasoning_text=native_reasoning,
            finish_reason=finish_reason,
            usage=usage,
            raw_chunks_sample=[],
        )

    async def _generate_stream(self, request: LLMRequest) -> LLMResult:
        client = self._client(request)
        kwargs = self._common_kwargs(request)
        kwargs["stream"] = True

        logger.info(
            "[LLMGatewayRequest] mode=stream model=%s messages=%s",
            request.model_name,
            len(request.messages),
        )

        content_text = ""
        native_reasoning = ""
        finish_reason: str | None = None
        raw_chunks_sample: list[dict[str, Any]] = []
        chunk_count = 0

        try:
            stream = await asyncio.to_thread(lambda: client.chat.completions.create(**kwargs))
            for chunk in stream:
                chunk_count += 1
                if len(raw_chunks_sample) < 3:
                    raw_chunks_sample.append(self._safe_model_dump(chunk))

                if not getattr(chunk, "choices", None):
                    continue
                choice = chunk.choices[0]
                if getattr(choice, "finish_reason", None):
                    finish_reason = choice.finish_reason
                delta = getattr(choice, "delta", None)
                if delta is None:
                    continue

                content_text += self._extract_delta_content(delta)
                native_reasoning += self._extract_delta_reasoning(delta)
        except Exception as exc:
            logger.exception("[LLMGatewayError] mode=stream model=%s", request.model_name)
            return LLMResult(
                ok=False,
                model_name=request.model_name,
                mode=LLMMode.STREAM,
                error_type="PROVIDER_ERROR",
                error_message=str(exc),
                raw_chunks_sample=raw_chunks_sample,
            )

        result = self._finalize_result(
            request=request,
            mode=LLMMode.STREAM,
            content_text=content_text,
            native_reasoning_text=native_reasoning,
            finish_reason=finish_reason,
            usage={},
            raw_chunks_sample=raw_chunks_sample,
        )
        result.metadata.update({"chunk_count": chunk_count})
        return result

    def _finalize_result(
        self,
        *,
        request: LLMRequest,
        mode: LLMMode,
        content_text: str,
        native_reasoning_text: str,
        finish_reason: str | None,
        usage: dict[str, Any],
        raw_chunks_sample: list[dict[str, Any]],
    ) -> LLMResult:
        normalized = normalize_reasoning_answer(
            content_text=content_text,
            native_reasoning_text=native_reasoning_text,
        )

        answer = normalized.answer_text
        reasoning = normalized.reasoning_text

        ok = bool(answer.strip())
        error_type = None if ok else "EMPTY_ANSWER"
        error_message = None
        if not ok:
            if native_reasoning_text.strip():
                error_message = "Provider returned reasoning but no final answer content."
            else:
                error_message = "Provider returned no final answer content."

        logger.info(
            "[LLMGatewayResult] mode=%s model=%s ok=%s answer_len=%s reasoning_len=%s parse=%s",
            mode.value,
            request.model_name,
            ok,
            len(answer or ""),
            len(reasoning or ""),
            normalized.parse_method,
        )

        return LLMResult(
            ok=ok,
            model_name=request.model_name,
            mode=mode,
            answer_text=answer,
            reasoning_text=reasoning,
            raw_text=normalized.raw_text,
            content_text=content_text,
            native_reasoning_text=native_reasoning_text,
            finish_reason=finish_reason,
            usage=usage,
            parse_method=normalized.parse_method,
            confidence=normalized.confidence,
            error_type=error_type,
            error_message=error_message,
            raw_chunks_sample=raw_chunks_sample,
            metadata={},
        )

    # -------------------------------------------------------------------------
    # DRY Field Extraction Helpers
    # -------------------------------------------------------------------------
    def _extract_field(self, obj: Any, fields: tuple[str, ...], concat: bool = False) -> str:
        parts = []
        is_dict = isinstance(obj, dict)

        for field_name in fields:
            value = None
            if is_dict:
                value = obj.get(field_name)
            else:
                value = getattr(obj, field_name, None)

            if value:
                if not concat:
                    return str(value)
                parts.append(str(value))

        return "".join(parts) if concat else ""

    def _extract_message_content(self, msg: Any) -> str:
        return self._extract_field(msg, self.field_mapping.content_fields, concat=False)

    def _extract_delta_content(self, delta: Any) -> str:
        return self._extract_field(delta, self.field_mapping.content_fields, concat=False)

    def _extract_message_reasoning(self, msg: Any) -> str:
        return self._extract_field(msg, self.field_mapping.reasoning_fields, concat=True)

    def _extract_delta_reasoning(self, delta: Any) -> str:
        return self._extract_field(delta, self.field_mapping.reasoning_fields, concat=True)

    def _safe_model_dump(self, obj: Any) -> dict[str, Any]:
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "model_dump"):
            try:
                return obj.model_dump()
            except Exception:
                pass
        if hasattr(obj, "dict"):
            try:
                return obj.dict()
            except Exception:
                pass
        try:
            return json.loads(json.dumps(obj, default=str))
        except Exception:
            return {"repr": repr(obj)}