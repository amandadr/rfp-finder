"""Unit tests for UserProfile."""

import tempfile
from pathlib import Path

import pytest

from rfp_finder.models.profile import UserProfile


class TestUserProfile:
    """Tests for UserProfile model."""

    def test_from_yaml_loads_filters(self) -> None:
        """from_yaml loads filters from nested structure."""
        yaml_content = """
profile_id: example
filters:
  regions: ["ON", "National"]
  keywords: [AI, software]
  exclude_keywords: [construction]
  max_days_to_close: 60
  max_budget: 500000
eligibility:
  citizenship_required: canadian
  security_clearance: null
"""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            Path(f.name).write_text(yaml_content)
            profile = UserProfile.from_yaml(f.name)
            Path(f.name).unlink()
        assert profile.profile_id == "example"
        assert profile.eligible_regions == ["ON", "National"]
        assert profile.keywords == ["AI", "software"]
        assert profile.exclude_keywords == ["construction"]
        assert profile.max_days_to_close == 60
        assert profile.citizenship_required == "canadian"
