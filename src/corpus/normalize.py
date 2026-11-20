"""Preserve traditional characters and source readings; expose unknown glyphs."""
from __future__ import annotations

import re
import unicodedata as ud

HAN_PUNCT = "。，、；：？！「」『』（）《》〈〉…．·"


def is_pua(char):
    if len(char) != 1:
        return False
    n = ord(char)
    return 0xE000 <= n <= 0xF8FF or 0xF0000 <= n <= 0xFFFFD or 0x100000 <= n <= 0x10FFFD


def is_han(char):
    if len(char) != 1:
        return False
    n = ord(char)
    return (0x2E80 <= n <= 0x2FDF or 0x3400 <= n <= 0x4DBF or 0x4E00 <= n <= 0x9FFF
            or 0xF900 <= n <= 0xFAFF or 0x20000 <= n <= 0x323AF or char == "〓")


def is_han_punct(char):
    return char in HAN_PUNCT


def norm_han(text):
    out = []
    for i, char in enumerate(text):
        # Remove only a proven radical + identical full character encoding artifact.
        # Legitimate repetitions such as 關關 must survive normalization.
        if 0x2E80 <= ord(char) <= 0x2FDF:
            plain = ud.normalize("NFKC", char)
            if i+1 < len(text) and text[i+1] == plain:
                continue
            char = plain
        out.append("〓" if is_pua(char) else char)
    return "".join(out).replace(",", "，")


def norm_viet(text):
    text = "".join("〓" if is_pua(c) else c for c in ud.normalize("NFC", text))
    return " ".join(text.split())


def norm_reading(text):
    return norm_viet(text).lower().strip(" ,.;:!?()[]\"'“”‘’-–")


def han_len(text):
    return sum(is_han(c) for c in text)


def vi_len(text):
    return len(re.findall(r"[^\W\d_]+", text))


def han_body(text, preserve_unknown=False):
    out = []
    for char in norm_han(text):
        if is_han(char) or is_han_punct(char) or char in ".;:!?":
            out.append(char)
        elif preserve_unknown and (char.isalpha() or char.isdigit()):
            out.append("〓")
    return "".join(out)


def normalization_flags(text):
    return ["pua_unmapped"] if "〓" in text or any(is_pua(c) for c in text) else []
