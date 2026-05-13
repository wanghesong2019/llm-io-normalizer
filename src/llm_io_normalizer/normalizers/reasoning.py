from __future__ import annotations

import re
from dataclasses import dataclass

_THINK_RE = re.compile(r"<think>\s*(.*?)\s*</think>", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class NormalizedText:
    reasoning_text: str
    answer_text: str
    raw_text: str
    parse_method: str
    confidence: float


def strip_think_tags(text: str) -> str:
    if not text:
        return ""
    return _THINK_RE.sub("", text).replace("<think>", "").replace("</think>", "").strip()


def split_think_tag(raw_text: str) -> NormalizedText | None:
    """Split '<think>...</think>final answer' style output."""
    raw_text = raw_text or ""
    match = _THINK_RE.search(raw_text)
    if not match:
        return None

    reasoning = match.group(1).strip()
    answer = (raw_text[: match.start()] + raw_text[match.end() :]).strip()
    answer = answer.replace("<think>", "").replace("</think>", "").strip()
    return NormalizedText(
        reasoning_text=reasoning,
        answer_text=answer,
        raw_text=raw_text,
        parse_method="think_tag",
        confidence=0.95,
    )


def normalize_reasoning_answer(
    *,
    content_text: str,
    native_reasoning_text: str = "",
    role: str = "tested_model",
) -> NormalizedText:
    """Normalize provider-specific content/reasoning channels.

    Rules:
    - If a native reasoning channel exists, final answer is content_text.
    - Else, if content has <think>...</think>, split it.
    - Else, entire content is the answer.
    """
    content_text = content_text or ""
    native_reasoning_text = native_reasoning_text or ""
    raw_text = content_text

    if native_reasoning_text.strip():
        # Do not merge reasoning into answer; keep final answer clean.
        return NormalizedText(
            reasoning_text=native_reasoning_text.strip(),
            answer_text=strip_think_tags(content_text),
            raw_text=raw_text,
            parse_method="native_reasoning",
            confidence=0.95,
        )

    split = split_think_tag(content_text)
    if split is not None:
        return split

    return NormalizedText(
        reasoning_text="",
        answer_text=content_text.strip(),
        raw_text=raw_text,
        parse_method="content_only",
        confidence=0.70,
    )
