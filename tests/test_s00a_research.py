import pytest

from stages.s00a_research.stage import Budget, BudgetExceeded, corroborated


def test_corroboration_needs_two_sources():
    news = [{"title": "Inflation cooled", "source": "Reuters"},
            {"title": "CPI inflation eases", "source": "AP"}]
    assert corroborated("inflation", news, min_sources=2) is True


def test_corroboration_single_source_fails():
    assert corroborated("inflation", [{"title": "Inflation cooled", "source": "Reuters"}],
                        min_sources=2) is False


def test_corroboration_ignores_offtopic_sources():
    news = [{"title": "Inflation cooled", "source": "Reuters"},
            {"title": "Sports recap", "source": "ESPN"}]   # second item not about the topic
    assert corroborated("inflation", news, min_sources=2) is False


def test_budget_blocks_over_limit():
    b = Budget(limit=2)
    b.spend("alpha_vantage")
    b.spend("alpha_vantage")
    with pytest.raises(BudgetExceeded):
        b.spend("alpha_vantage")


def test_corroboration_empty_topic_never_corroborates():
    # "" is a substring of everything; an upstream bug clearing the topic must not pass the gate
    news = [{"title": "A", "source": "Reuters"}, {"title": "B", "source": "AP"}]
    assert corroborated("", news, min_sources=2) is False


def test_corroboration_normalizes_source_case():
    # "Reuters" vs "reuters" is ONE source, not two
    news = [{"title": "Inflation cooled", "source": "Reuters"},
            {"title": "Inflation eases", "source": "reuters "}]
    assert corroborated("inflation", news, min_sources=2) is False


def test_corroboration_tolerates_missing_source_key():
    news = [{"title": "Inflation cooled"},  # no source -> ignored, not a KeyError
            {"title": "Inflation eases", "source": "AP"}]
    assert corroborated("inflation", news, min_sources=2) is False
