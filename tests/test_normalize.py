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


# --- Regression tests for review-driven fixes ---

# Fix #1: leading-dot decimals no longer crash and produce correct narration
def test_leading_dot_percent():
    assert normalize(".5%") == "zero point five percent"


def test_leading_dot_money_scale():
    assert normalize("$.5M") == "zero point five million dollars"


# Fix #2: negative numbers are narrated correctly (not silently mangled)
def test_negative_percent():
    assert normalize("-5%") == "negative five percent"


def test_negative_int_in_context():
    assert normalize("down -5%") == "down negative five percent"


# Fix #3: word-boundary substitution — "CPI" must not corrupt "CPIAUCSL"
def test_cpi_standalone_expands():
    # CPI alone should expand (it's in the lexicon as "C P I")
    assert normalize("CPI") == "C P I"


def test_cpiaucsl_not_corrupted():
    # CPIAUCSL contains "CPI" as a prefix but must NOT be split
    result = normalize("CPIAUCSL")
    assert "AUCSL" in result, f"AUCSL was mangled: {result!r}"
    assert "C P I" not in result, f"CPI was incorrectly expanded inside CPIAUCSL: {result!r}"


# Fix #3: "Q3" in lexicon must not mangle "Q32"
def test_q3_standalone_expands():
    assert normalize("Q3") == "Q three"


def test_q3_not_mangled_in_q32():
    result = normalize("Q32")
    assert "Q32" in result or result == "Q32", f"Q32 was incorrectly mangled: {result!r}"


# Fix #3: 401(k) still expands correctly after regex substitution refactor
def test_401k_still_expands():
    assert normalize("401(k)") == "four oh one k"


# Fix #4: 1,000,000 uses "million" branch, not digit-by-digit fallback
def test_one_million_exact():
    assert normalize("$1000000") == "one million dollars"


def test_one_million_percent():
    # just _say_int path via a large percent (unusual but tests the branch)
    assert normalize("1000000%") == "one million percent"


def test_two_million_remainder():
    assert normalize("$2500000") == "two million five hundred thousand dollars"


# Fix #5: money scale regex accepts lowercase, space before suffix, MM shorthand, billions
def test_money_lowercase_m():
    assert normalize("$5m") == "five million dollars"


def test_money_space_before_suffix():
    assert normalize("$5 M") == "five million dollars"


def test_money_mm_shorthand():
    assert normalize("$1.5MM") == "one point five million dollars"


def test_money_billions_upper():
    assert normalize("$2B") == "two billion dollars"


def test_money_billions_lower():
    assert normalize("$2b") == "two billion dollars"
