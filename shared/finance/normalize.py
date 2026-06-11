import json
import re
from pathlib import Path

_LEX = json.loads((Path(__file__).parent / "lexicon.json").read_text())
_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_TEENS = [
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]


def _say_int(s: str) -> str:
    n = int(s)
    # Fix #2: handle negatives properly (Python's negative indexing would give wrong result)
    if n < 0:
        return "negative " + _say_int(str(-n))
    if n < 10:
        return _ONES[n]
    if n < 20:
        return _TEENS[n - 10]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else " " + _ONES[n % 10])
    if n < 1000:
        rem = n % 100
        return _ONES[n // 100] + " hundred" + ("" if rem == 0 else " " + _say_int(str(rem)))
    if n < 1_000_000:
        rem = n % 1000
        return (
            _say_int(str(n // 1000)) + " thousand" + ("" if rem == 0 else " " + _say_int(str(rem)))
        )
    # Fix #4: add millions branch before digit-by-digit fallback
    if n < 1_000_000_000:
        rem = n % 1_000_000
        return (
            _say_int(str(n // 1_000_000)) + " million"
            + ("" if rem == 0 else " " + _say_int(str(rem)))
        )
    return " ".join(_ONES[int(d)] for d in s)  # very large: digit-by-digit fallback


def _say_number(num: str) -> str:
    if "." in num:
        whole, frac = num.split(".")
        # Fix #1: empty whole part (e.g. ".5") should be treated as "0"
        whole = whole or "0"
        frac_words = " ".join(_ONES[int(d)] for d in frac)
        return f"{_say_int(whole)} point {frac_words}"
    return _say_int(num)


def normalize(text: str) -> str:
    # Lexicon substitutions (longest-match via sorted keys, descending length)
    # Fix #3: use word-boundary regex instead of str.replace to avoid substring corruption
    # (e.g. "CPI" in "CPIAUCSL" must NOT be replaced; "Q3" in "Q32" must NOT be replaced)
    for token, spoken in sorted(_LEX.items(), key=lambda kv: -len(kv[0])):
        # Build a pattern that matches the token only when not adjacent to alphanumeric chars.
        # We cannot use \b because tokens like "401(k)" contain non-word characters.
        pattern = rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])"
        text = re.sub(pattern, spoken, text)

    # Fix #5: $NM / $NB — millions / billions (case-insensitive, optional space, MM shorthand)
    # Also fix #1: accept leading-dot decimals via \d*\.?\d+
    def _money_scale(m: re.Match) -> str:
        num = _say_number(m.group(1))
        suffix = m.group(2).upper().rstrip()  # strip any trailing whitespace
        # MM is finance shorthand for millions (mille mille)
        if suffix in ("MM", "M"):
            scale = "million"
        else:
            scale = "billion"
        return f"{num} {scale} dollars"

    text = re.sub(
        r"\$(\d*\.?\d+)\s*(MM|M|B)\b",
        _money_scale,
        text,
        flags=re.IGNORECASE,
    )

    # $N.NN — plain dollar amounts (also accept leading-dot decimals)
    def _money_plain(m: re.Match) -> str:
        return f"{_say_number(m.group(1))} dollars"

    text = re.sub(r"\$(\d*\.?\d+)", _money_plain, text)

    # N% — percentages (leading-dot decimals; a minus counts as a SIGN only when not preceded
    # by a digit, so "3-5%" stays a range instead of becoming "3negative five percent")
    def _percent(m: re.Match) -> str:
        return f"{_say_number(m.group(1))} percent"

    text = re.sub(r"((?<!\d)-?\d*\.?\d+)%", _percent, text)

    return text.strip()
