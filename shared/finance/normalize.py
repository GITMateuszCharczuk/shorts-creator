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
    return " ".join(_ONES[int(d)] for d in s)  # very large: digit-by-digit fallback


def _say_number(num: str) -> str:
    if "." in num:
        whole, frac = num.split(".")
        frac_words = " ".join(_ONES[int(d)] for d in frac)
        return f"{_say_int(whole)} point {frac_words}"
    return _say_int(num)


def normalize(text: str) -> str:
    # Lexicon substitutions (longest-match via sorted keys, descending length)
    for token, expansion in sorted(_LEX.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(token, expansion)

    # $NM / $NB — millions / billions
    def _money_scale(m: re.Match) -> str:
        num = _say_number(m.group(1))
        scale = "million" if m.group(2).upper() == "M" else "billion"
        return f"{num} {scale} dollars"

    text = re.sub(r"\$(\d+(?:\.\d+)?)([MB])\b", _money_scale, text)

    # $N.NN — plain dollar amounts
    def _money_plain(m: re.Match) -> str:
        return f"{_say_number(m.group(1))} dollars"

    text = re.sub(r"\$(\d+(?:\.\d+)?)", _money_plain, text)

    # N% — percentages
    def _percent(m: re.Match) -> str:
        return f"{_say_number(m.group(1))} percent"

    text = re.sub(r"(\d+(?:\.\d+)?)%", _percent, text)

    return text.strip()
