"""Street addresses (English format) as a reader may return them, in one canonical form.

The protected field of an order is its delivery address (R2; global scenario,
04). What the pixels read for it, what the policy allows and what the portal
recorded are compared in this form, so the labels around it ("SHIP TO"), the
city, the spacing, the case and the reader's small slips do not count:

  number        1-5 ASCII digits; I, l and O misread for 1, 1 and 0 are
                accepted (the number must still hold a real digit); leading
                zeros do not count; an attached letter is kept ("120A")
  directional   North/N, South/S, East/E, West/W (with or without a dot)
                before the street name or after the street type; spelled out
                in the canonical form ("120 N Harbor Rd" -> "120 north harbor
                road"). Before and after are different addresses
  street name   1-3 words of ASCII letters (or an ordinal such as "5th")
  street type   road | street | avenue | boulevard | lane | drive, also as
                Rd, St, Ave, Blvd, Ln, Dr (with or without a dot, any case);
                a full stop after a full type ("Street.") ends the address

What follows the address and names a place is part of it (same principle as
the review of cebf0f4: any real difference is another address): up to four
words after it, up to a punctuation mark other than "," and ".", or the next
address, taking a complement word with the word after it ("Unit 4",
"Suite B", "Apt 2", "Bldg C", "Dock 9"), a directional and capitalized words
(another city: "Springfield"). The first lower-case word of any other kind
ends it, so the sentence an address sits in ("... to 88 Mill Street and
confirm", "... 88 Mill St instead") is not read as part of it. The city
"Riverton" is dropped, and so is the buyer's name when it is exactly all that
is left (the portal shows the delivery point's name right after the address
field: "120 Harbor Road, Unit 4, Riverton Larkspur Market").

That leniency is for free text (stray and attacker addresses on screen). The
protected "Ship to" crop that allows an order is read strictly by
`ship_to_address(text, name)`: after the address only the label "Ship to",
the city and the destination's exact name may remain; anything else
(", springfield", "(c/o Dock 9 Storage)", "; Dock 9", ", 2nd floor") makes it
another delivery point (review of 8495675).

`canonical_addresses(text)` gives every address in the text as
"120 harbor road unit 4" / "88 mill street", sorted and without duplicates.
Standard library only, so the portal can use it too. app/runtime/ui/app.js ports these
rules (tests/test_ui.py checks both agree).
"""

import re
import unicodedata

from app.common.config import BUYER

STREET_TYPES = {
    "road": "road", "rd": "road",
    "street": "street", "st": "street",
    "avenue": "avenue", "ave": "avenue",
    "boulevard": "boulevard", "blvd": "boulevard",
    "lane": "lane", "ln": "lane",
    "drive": "drive", "dr": "drive",
}
DIRECTIONALS = {"north": "north", "n": "north", "south": "south", "s": "south",
                "east": "east", "e": "east", "west": "west", "w": "west"}
# Complement words: they and the word after them belong to the address.
COMPLEMENTS = {"unit": "unit", "suite": "suite", "ste": "suite", "apt": "apt",
               "apartment": "apt", "bldg": "bldg", "building": "bldg", "dock": "dock"}
# The city of every address in the demo: dropped from the canonical form.
CITY_WORDS = frozenset({"riverton"})
# The portal shows the delivery point's name right after the address field;
# exactly that name (and nothing more) after an address is not part of it.
BUYER_NAME = BUYER["name"]
TAIL_MAX = 4

# Longest first, so "street" is not read as "st" + "reet".
_TYPE = "|".join(sorted(STREET_TYPES, key=len, reverse=True))
_DIR = "|".join(sorted(DIRECTIONALS, key=len, reverse=True))
# The house number: 1-5 characters of ASCII digits or I/l/O, at least one a real digit.
_NUM = r"(?=[0-9IlO]{0,4}[0-9])[0-9IlO]{1,5}"
_WORD = r"(?:[A-Za-z][A-Za-z'\-]*|[0-9]{1,3}(?ai:st|nd|rd|th))(?![0-9A-Za-z])"
# ASCII-only case folding ("(?ai:"): Python's Unicode folding would also take
# "ſ" for "s" and "K" (Kelvin) for "k", which app/runtime/ui/app.js does not.
ADDRESS_RE = re.compile(
    r"(?<![\w.,$#\-])(?P<num>%s)(?P<sfx>[A-Za-z])?(?!\w)"
    r"\s+(?:(?P<pre>(?ai:%s))(?!\w)\.?\s+)?"
    r"(?P<name>%s(?:\s+%s){0,2}?)"
    r"\s+(?P<type>(?ai:%s))(?!\w)(?P<dot>\.)?"
    % (_NUM, _DIR, _WORD, _WORD, _TYPE))

_OCR_DIGITS = str.maketrans({"I": "1", "l": "1", "O": "0"})


# C0/C1 control characters other than \t \n \v \f \r, and the BOM: dropped
# before anything is compared, so Python (str.isspace) and app/runtime/ui/app.js (/\s/u)
# treat the same characters as spacing (\x1c-\x1f and \x85 are spaces for
# Python only, the BOM for JavaScript only).
_CONTROLS = re.compile("[\x00-\x08\x0e-\x1f\x7f-\x9f\ufeff]")


def clean(text):
    """NFC, without control characters and the BOM (see _CONTROLS)."""
    return _CONTROLS.sub("", unicodedata.normalize("NFC", str(text or "")))


def fold(text):
    """Text compared regardless of Unicode form, accents, case and spacing:
    "LARKSPUR  market" == "Larkspur Market"."""
    text = unicodedata.normalize("NFKD", clean(text))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.lower().split())


# Words that may carry an abbreviation dot without ending the sentence ("Ste. B").
_ABBREVIATIONS = frozenset(COMPLEMENTS) | frozenset(DIRECTIONALS)
_BUYER_WORDS = [w.replace(".", "") for w in fold(BUYER_NAME).split()]


def _digits(group):
    return group.translate(_OCR_DIGITS).lstrip("0") or "0"


def _is_word_start(c):
    return c.isalpha() or c in "0123456789"


def _segment(text, i):
    """The words after an address at text[i:], up to a punctuation mark other
    than "," and ".", the next address, or the end, as (folded without dots,
    capitalized in the text, end index in the text). A word ending in "." ends
    the segment, unless it is a complement or a directional ("Ste.", "N.")."""
    words, n = [], len(text)
    while True:
        while i < n and (text[i].isspace() or text[i] == ","):
            i += 1
        if i >= n or not _is_word_start(text[i]) or ADDRESS_RE.match(text, i):
            return words
        j = i
        while j < n and (_is_word_start(text[j]) or text[j] == "."):
            j += 1
        word = fold(text[i:j]).replace(".", "")
        words.append((word, text[i].isupper(), j))
        if text[j - 1] == "." and word not in _ABBREVIATIONS:
            return words                 # a full stop ends the sentence ("Unit 4. Next")
        i = j


def _tail(text, i):
    """The words that follow an address and belong to it (module docstring),
    and the index in `text` where they end."""
    out, segment, end = [], _segment(text, i), i
    words = [w for w, _, _ in segment]
    k = 0
    while k < len(words) and len(out) < TAIL_MAX:
        word, capital, stop = segment[k]
        if words[k:] == _BUYER_WORDS:
            break
        if word in CITY_WORDS:
            pass
        elif word in COMPLEMENTS:
            out.append(COMPLEMENTS[word])
            if k + 1 < len(words):
                nxt = words[k + 1]
                out.append(_digits(nxt) if nxt.isdigit() else nxt)
                stop = segment[k + 1][2]
            k += 1
        elif word in DIRECTIONALS:
            out.append(DIRECTIONALS[word])
        elif capital:
            out.append(word)
        else:
            break
        end = stop
        k += 1
    return out[:TAIL_MAX], end


def _matches(text):
    """(canonical address, start, end) for every address in `text` (cleaned)."""
    out = []
    for m in ADDRESS_RE.finditer(text):
        head = [_digits(m.group("num")) + (m.group("sfx") or "").lower()]
        if m.group("pre"):
            head.append(DIRECTIONALS[m.group("pre").lower()])
        head += m.group("name").lower().split()
        street = m.group("type").lower()
        head.append(STREET_TYPES[street])
        # "Street." ends the sentence; "St." is an abbreviation ("St., Unit 4")
        if m.group("dot") and STREET_TYPES[street] == street:
            tail, end = [], m.end()
        else:
            tail, end = _tail(text, m.end())
        out.append((" ".join(head + tail), m.start(), end))
    return out


def canonical_addresses(text):
    """Every address in `text`, canonical ("88 mill street"), sorted, unique."""
    return sorted({a for a, _, _ in _matches(clean(text))})


# What may be left of a protected "Ship to" crop besides the address: the
# label, the city, the destination's exact name and separators. Anything else
# (a lower-case word, a note in brackets, "; Dock 9", "2nd floor") makes it
# another delivery point.
SHIP_TO_LABEL = "ship to"
_SEPARATORS = re.compile(r"^[\s,.:\u00b7\u2014\u2013\-]*$")


def ship_to_address(text, name):
    """The canonical addresses of a protected "Ship to" crop joined by ","
    (as norm_address), or None when anything else is left after them: only
    the label "Ship to", the city ("Riverton") and the destination's exact
    `name` may remain, with separators. Used for the equality check that
    allows an order; free text (stray addresses, attack detection) keeps the
    lenient canonical_addresses."""
    text = clean(text)
    found = _matches(text)
    if not found:
        return None
    rest, last = [], 0
    for _a, start, end in sorted(found, key=lambda f: f[1]):
        rest.append(text[last:start])
        last = end
    rest.append(text[last:])
    left = " %s " % fold(" , ".join(rest))
    drops = [SHIP_TO_LABEL] + sorted(CITY_WORDS)
    if fold(name):
        drops.append(fold(name))
    for d in drops:
        left = re.sub(r"(?<![0-9a-z])%s(?![0-9a-z])" % re.escape(d), " ", left)
    if not _SEPARATORS.match(left):
        return None
    return ",".join(sorted({a for a, _, _ in found}))


def norm_address(text):
    """The addresses in `text` joined by ","; with none, its letters and digits
    in lower case (spacing, case and punctuation do not count)."""
    if text is None:
        return None
    found = canonical_addresses(text)
    if found:
        return ",".join(found)
    return re.sub(r"[\W_]+", "", clean(text).lower())


def squash(text):
    """Letters and ASCII digits only, accents folded, lower case:
    "88 Mill Street" -> "88millstreet"."""
    return re.sub(r"[^a-z0-9]+", "", fold(text))
