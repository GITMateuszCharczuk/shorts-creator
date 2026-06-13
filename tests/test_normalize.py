from shared.finance.normalize import normalize


def test_money_millions():
    assert normalize("$1.5M") == "one point five million dollars"


def test_known_token_from_lexicon():
    assert normalize("401(k)") == "four oh one k"


def test_percent():
    assert normalize("3.2%") == "three point two percent"


def test_dollars_with_hundreds():
    assert normalize("$184.21") == "one hundred eighty four point two one dollars"


def test_ticker_passthrough_uppercased_words_kept():
    assert "FOMC" not in normalize("FOMC")  # expanded via lexicon
