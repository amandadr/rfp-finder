"""Enrich opportunities with extracted attachment text."""

from pathlib import Path
from typing import TYPE_CHECKING

from rfp_finder.models.opportunity import NormalizedOpportunity

from .extractor import extract_text_from_file
from .fetcher import fetch_attachment

if TYPE_CHECKING:
    from rfp_finder.store.attachment_cache import AttachmentCacheStore


def enrich_opportunity(
    opp: NormalizedOpportunity,
    cache_dir: Path,
    cache_store: "AttachmentCacheStore",
    *,
    fetch_missing: bool = True,
) -> str:
    """
    Fetch and extract text from attachments. Returns combined text:
    opp summary + extracted attachment texts (with source labels).
    """

    parts: list[str] = []
    if opp.summary:
        parts.append(f"[Main]\n{opp.summary}")

    for att in opp.attachments or []:
        if not att.url:
            continue
        cached = cache_store.get_cached(att.url)
        text = ""
        if cached and cached.extraction_status == "success" and cached.extracted_text:
            text = cached.extracted_text
        elif fetch_missing:
            local_path, err = fetch_attachment(
                att.url, cache_dir, skip_existing=True
            )
            if local_path:
                extracted, page_count, ext_err = extract_text_from_file(
                    local_path, att.mime_type
                )
                cache_store.upsert(
                    att.url,
                    str(local_path),
                    extraction_status="failed" if ext_err else "success",
                    extracted_text=extracted if not ext_err else None,
                    text_length=len(extracted) if not ext_err else None,
                    page_count=page_count if not ext_err else None,
                    error_message=ext_err,
                )
                if not ext_err:
                    text = extracted
        if text.strip():
            label = att.label or Path(att.url).name or "attachment"
            parts.append(f"[Attachment: {label}]\n{text[:50000]}")  # cap size

    return "\n\n---\n\n".join(parts)


# Type alias for late import
AttachmentCacheStore = "AttachmentCacheStore"
