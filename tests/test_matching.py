"""Tests for matching utilities."""

import pytest

from rfp_finder.matching import exclude_keyword_matches, positive_keyword_matches


class TestExcludeKeywordMatches:
    """Exclude keywords should use word boundaries to avoid false positives."""

    def test_standalone_word_matches(self) -> None:
        """Standalone word matches."""
        assert exclude_keyword_matches("printing services required", "printing") is True
        assert exclude_keyword_matches("Construction services", "construction") is True

    def test_hyphenated_compound_no_match(self) -> None:
        """'printing' in 'non-printing' should NOT match (false positive)."""
        assert exclude_keyword_matches("Documents in non-printing format", "printing") is False


    def test_substring_no_match(self) -> None:
        """'construction' in 'reconstruction' should NOT match (different word)."""
        assert exclude_keyword_matches("Database reconstruction project", "construction") is False

    def test_reseller_standalone_matches(self) -> None:
        """'reseller' as standalone word matches."""
        assert exclude_keyword_matches("Reseller agreement required", "reseller") is True

    def test_reseller_plural_no_match(self) -> None:
        """'reseller' should not match 'resellers' (word boundary)."""
        assert exclude_keyword_matches("For resellers only", "reseller") is False


class TestPositiveKeywordMatches:
    """Positive keyword matching for include/preferred keywords."""

    def test_full_phrase_matches(self) -> None:
        """Full phrase matches."""
        assert positive_keyword_matches("software development project", "software development") is True

    def test_multi_word_partial(self) -> None:
        """Multi-word: at least 2 words match."""
        assert positive_keyword_matches("software and development", "software development") is True
