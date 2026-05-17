# from __future__ import annotations

# import re
# from dataclasses import dataclass

# _THINK_RE = re.compile(r"<think>\s*(.*?)\s*</think>", re.IGNORECASE | re.DOTALL)


# @dataclass(frozen=True)
# class NormalizedText:
#     reasoning_text: str
#     answer_text: str
#     raw_text: str
#     parse_method: str
#     confidence: float


# def strip_think_tags(text: str) -> str:
#     if not text:
#         return ""
#     return _THINK_RE.sub("", text).replace("<think>", "").replace("</think>", "").strip()


# def split_think_tag(raw_text: str) -> NormalizedText | None:
#     """Split '<think>...</think>final answer' style output."""
#     raw_text = raw_text or ""
#     match = _THINK_RE.search(raw_text)
#     if not match:
#         return None

#     reasoning = match.group(1).strip()
#     answer = (raw_text[: match.start()] + raw_text[match.end() :]).strip()
#     answer = answer.replace("<think>", "").replace("</think>", "").strip()
#     return NormalizedText(
#         reasoning_text=reasoning,
#         answer_text=answer,
#         raw_text=raw_text,
#         parse_method="think_tag",
#         confidence=0.95,
#     )


# def normalize_reasoning_answer(
#     *,
#     content_text: str,
#     native_reasoning_text: str = "",
#     role: str = "tested_model",
# ) -> NormalizedText:
#     """Normalize provider-specific content/reasoning channels.

#     Rules:
#     - If a native reasoning channel exists, final answer is content_text.
#     - Else, if content has <think>...</think>, split it.
#     - Else, entire content is the answer.
#     """
#     content_text = content_text or ""
#     native_reasoning_text = native_reasoning_text or ""
#     raw_text = content_text

#     if native_reasoning_text.strip():
#         # Do not merge reasoning into answer; keep final answer clean.
#         return NormalizedText(
#             reasoning_text=native_reasoning_text.strip(),
#             answer_text=strip_think_tags(content_text),
#             raw_text=raw_text,
#             parse_method="native_reasoning",
#             confidence=0.95,
#         )

#     split = split_think_tag(content_text)
#     if split is not None:
#         return split

#     return NormalizedText(
#         reasoning_text="",
#         answer_text=content_text.strip(),
#         raw_text=raw_text,
#         parse_method="content_only",
#         confidence=0.70,
#     )
from __future__ import annotations

import re
from dataclasses import dataclass

# 匹配完整的 <think>...</think> 块（支持多行，忽略大小写）
_THINK_COMPLETE_RE = re.compile(r"<think>\s*(.*?)\s*</think>", re.IGNORECASE | re.DOTALL)
# 匹配未闭合的 <think> 块（通常出现在文本末尾，因流式截断导致）
_THINK_UNCLOSED_RE = re.compile(r"<think>\s*(.*)$", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class NormalizedText:
    reasoning_text: str
    answer_text: str
    raw_text: str
    parse_method: str
    confidence: float


def _extract_and_remove_think_blocks(text: str) -> tuple[str, str]:
    """
    内部辅助函数：提取文本中所有完整的、以及未闭合的 <think> 块。
    返回: (提取出的合并思考过程, 剔除思考过程后的纯净回答)
    """
    if not text:
        return "", ""

    reasoning_parts = []
    
    # 1. 提取并移除所有完整的 <think>...</think> 块
    def repl_complete(match: re.Match) -> str:
        reasoning_parts.append(match.group(1).strip())
        return ""  # 用空字符串替换整个完整块
        
    answer_text = _THINK_COMPLETE_RE.sub(repl_complete, text)
    
    # 2. 检查尾部是否存在未闭合的 <think> 块
    unclosed_match = _THINK_UNCLOSED_RE.search(answer_text)
    if unclosed_match:
        reasoning_parts.append(unclosed_match.group(1).strip())
        # 将未闭合标签及其后面的所有内容从回答中切除
        answer_text = answer_text[:unclosed_match.start()]
        
    # 合并所有的思考片段（忽略空字符串）
    reasoning_text = "\n".join(filter(None, reasoning_parts))
    answer_text = answer_text.strip()
    
    return reasoning_text, answer_text


def split_think_tag(raw_text: str) -> NormalizedText | None:
    """Split '<think>...</think>final answer' style output."""
    raw_text = raw_text or ""
    # 快速检查，避免不必要的正则开销
    if "<think>" not in raw_text.lower():
        return None

    reasoning, answer = _extract_and_remove_think_blocks(raw_text)
    
    # 即使存在 <think> 标签，如果里面没有任何内容，依然视作正常的提取
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
) -> NormalizedText:
    """Normalize provider-specific content/reasoning channels.

    Rules:
    - If a native reasoning channel exists, final answer is cleaned content_text.
    - Else, if content has <think>...</think>, split it (supports multiple and unclosed tags).
    - Else, entire content is the answer.
    """
    content_text = content_text or ""
    native_reasoning_text = native_reasoning_text or ""
    raw_text = content_text

    if native_reasoning_text.strip():
        # 如果存在原生思考字段，提取原生思考。但正文里可能依然混杂了冗余的 think 标签，需要清洗。
        _, cleaned_answer = _extract_and_remove_think_blocks(content_text)
        return NormalizedText(
            reasoning_text=native_reasoning_text.strip(),
            answer_text=cleaned_answer,
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