"""Unit tests for data models."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from rfp_finder.models.opportunity import AttachmentRef, NormalizedOpportunity
from rfp_finder.models.raw import RawOpportunity


class TestAttachmentRef:
    """Tests for AttachmentRef model."""

    def test_minimal_creation(self) -> None:
        """AttachmentRef requires only url."""
        ref = AttachmentRef(url="https://example.com/doc.pdf")
        assert ref.url == "https://example.com/doc.pdf"
        assert ref.label is None
        assert ref.mime_type is None
        assert ref.size_bytes is None

    def test_full_creation(self) -> None:
        """AttachmentRef accepts optional fields."""
        ref = AttachmentRef(
            url="https://example.com/doc.pdf",
            label="Specification",
            mime_type="application/pdf",
            size_bytes=1024,
        )
        assert ref.label == "Specification"
        assert ref.mime_type == "application/pdf"
        assert ref.size_bytes == 1024

    def test_serialization_roundtrip(self) -> None:
        """Model serializes and deserializes correctly."""
        ref = AttachmentRef(url="https://x.com/f.pdf", label="Foo")
        data = ref.model_dump()
        restored = AttachmentRef.model_validate(data)
        assert restored.url == ref.url
        assert restored.label == ref.label


class TestNormalizedOpportunity:
    """Tests for NormalizedOpportunity model."""

    def test_minimal_required_fields(self) -> None:
        """NormalizedOpportunity requires id, source, source_id."""
        opp = NormalizedOpportunity(
            id="canadabuys:cb-123",
            source="canadabuys",
            source_id="cb-123",
        )
        assert opp.title == ""
        assert opp.attachments == []
        assert opp.categories == []
        assert opp.commodity_codes == []

    def test_full_creation(self) -> None:
        """NormalizedOpportunity accepts all fields."""
        now = datetime.now(timezone.utc)
        opp = NormalizedOpportunity(
            id="canadabuys:cb-233",
            source="canadabuys",
            source_id="cb-233",
            title="Test Tender",
            summary="A test tender description",
            url="https://canadabuys.canada.ca/...",
            buyer="Test Agency",
            published_at=now,
            closing_at=now,
            categories=["SRV"],
            commodity_codes=["80101500"],
            attachments=[AttachmentRef(url="https://example.com/doc.pdf")],
            status="open",
            first_seen_at=now,
            last_seen_at=now,
        )
        assert opp.title == "Test Tender"
        assert len(opp.attachments) == 1
        assert opp.attachments[0].url == "https://example.com/doc.pdf"

    def test_json_serialization(self) -> None:
        """Model serializes to JSON-compatible dict."""
        opp = NormalizedOpportunity(
            id="canadabuys:cb-1",
            source="canadabuys",
            source_id="cb-1",
            title="Foo",
        )
        data = opp.model_dump(mode="json")
        assert isinstance(data["id"], str)
        assert "first_seen_at" in data
        assert "last_seen_at" in data


class TestRawOpportunity:
    """Tests for RawOpportunity model."""

    def test_empty_data(self) -> None:
        """RawOpportunity defaults to empty dict."""
        raw = RawOpportunity()
        assert raw.data == {}

    def test_data_storage(self) -> None:
        """RawOpportunity stores arbitrary dict data."""
        raw = RawOpportunity(data={"title": "Foo", "ref": "123"})
        assert raw.data["title"] == "Foo"
        assert raw.data["ref"] == "123"
