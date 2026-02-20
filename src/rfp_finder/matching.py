"""Shared keyword matching utilities for filtering and scoring."""

import re


def exclude_keyword_matches(text: str, keyword: str) -> bool:
    """
    Check if exclude keyword appears as a standalone word.
    Avoids false positives from:
    - Partial tokens: "printing" in "non-printing" (hyphenated compound)
    - Substrings: "construction" in "reconstruction" (word boundary)
    """
    if not keyword or not text:
        return False
    text_lower = text.lower()
    kw = re.escape(keyword.lower().strip())
    pattern = rf"\b{kw}\b"
    for m in re.finditer(pattern, text_lower):
        start = m.start()
        # Reject hyphenated compound: "non-printing" when searching "printing"
        if start > 0 and text_lower[start - 1] == "-":
            continue
        return True
    return False


def _word_in_text(text: str, word: str) -> bool:
    """Word-boundary match for single word (avoids substring false positives)."""
    if not word or not text:
        return False
    pattern = rf"\b{re.escape(word.lower())}\b"
    return bool(re.search(pattern, text.lower()))


def positive_keyword_matches(text: str, keyword: str) -> bool:
    """
    Full phrase match, or word-level match for multi-word keywords.
    Single-word: use word boundary. Multi-word: at least 2 words match.
    """
    kw_lower = keyword.lower().strip()
    if not kw_lower:
        return False
    words = kw_lower.split()
    if len(words) == 1:
        return _word_in_text(text, words[0])
    if kw_lower in text:
        return True
    return sum(1 for w in words if len(w) > 2 and _word_in_text(text, w)) >= min(2, len(words))
