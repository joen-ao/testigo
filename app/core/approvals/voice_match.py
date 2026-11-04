"""F7: does the spoken confirmation match what the pixels show?

The person reads the order total and the delivery destination aloud («Twelve
hundred forty dollars, ship to Larkspur Market»). Voice Transcribe gives the
text (F7 live path); this module compares it — normalized — against the amount
and the "Ship to" text **read from the pixels** (F4), never the DOM. The
amount is spoken in English words (or digits) in whole dollars and compared in
integer cents.

Strict on purpose (a doubt is a "no"):
- the amount is exactly ONE continuous, well-formed number phrase ("twelve
  hundred forty", "one thousand two hundred (and) forty", or digits like
  "1,240", "1240.00", "$1,240"). A second separate number phrase ("five,
  twelve hundred forty") or a malformed one ("forty twelve hundred") is not a
  match; cents other than ".00" make the phrase malformed (whole dollars only);
- only the phrase before the destination's name counts (after it, if nothing
  was said before), and street addresses are ignored, in digits ("120 Harbor
  Road, Unit 4") or in words ("one twenty Harbor Road unit four"), so reading
  the address aloud never changes the amount;
- a negation or cancel cue ("no", "not", "don't", "isn't", "can't",
  "won't", "wrong", "never", "cancel", "stop", "wait") rejects the
  confirmation; apostrophes (' and ’) are dropped first, so "isn't" is one
  word ("isnt"), never "isn" + "t";
- nothing else may be said: besides the amount, the destination's name, an
  address read aloud and a few filler words ("ship to", "dollars", "please",
  "yes", "confirm", "approve"...), any other word rejects it ("... that is
  right" and "... that is wrong" alike: a doubt is a "no").

The voice confirms the destination's NAME, not the address digits: the address
is checked by the pixels (F4/F5) and the signed policy (F1/F6).

Pure and offline: the transcription is real (a model), the comparison is code.
"""

import re
import unicodedata

from app.common.address import ADDRESS_RE, CITY_WORDS, COMPLEMENTS, DIRECTIONALS, STREET_TYPES

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
         "seventy": 70, "eighty": 80, "ninety": 90}
_HUNDRED = "hundred"
_THOUSAND = "thousand"
_MILLION = ("million", "millions")
_SCALES = (_HUNDRED, _THOUSAND) + _MILLION
_WORDS = set(_UNITS) | set(_TENS) | set(_SCALES)

MAX_AMOUNT = 999_999_999          # dollars: "nine hundred ninety-nine million ..."

# Words that take the confirmation back. Any of them (outside the destination's
# name) rejects it: "no", "not", "don't" (heard as "don t" or "dont"), "do not",
# "never", "cancel", "stop", "wait".
NEGATIONS = frozenset({
    "no", "not", "nope", "nah", "don", "dont", "doesn", "doesnt", "didn", "didnt",
    "isn", "isnt", "aren", "arent", "wasn", "wasnt", "cant", "cannot", "won", "wont",
    "shouldn", "shouldnt", "wouldn", "wouldnt", "never", "wrong", "incorrect",
    "cancel", "cancels", "cancelled", "canceled", "cancelling", "canceling",
    "stop", "stopped", "halt", "abort", "wait", "hold", "reject", "deny", "refuse",
})

# The only words allowed besides the amount and the destination's name (and an
# address read aloud, dropped by tokens()). Anything else rejects the
# confirmation (review of 8495675: "... I can't approve that" was accepted).
FILLER = frozenset({
    "ship", "shipping", "to", "for", "dollar", "dollars", "usd", "us", "please", "ok", "okay",
    "yes", "confirm", "confirmed", "approve", "approved", "the", "and", "a",
}) | frozenset(CITY_WORDS)

# A street address read aloud in words: its numbers, up to three name words
# and the street type ("one twenty Harbor Road"), then an optional complement
# with its number ("unit four"). Dropped with their numbers.
_STREET_WORDS = frozenset(STREET_TYPES)
_COMPLEMENT_WORDS = frozenset(COMPLEMENTS) | {"number"}
_DIRECTION_WORDS = frozenset(DIRECTIONALS)
# Never part of a street name read aloud (so the amount before them is kept).
_NOT_NAME = frozenset({"dollar", "dollars", "usd", "bucks", "cents", "and", "to", "ship", "at"})


def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")


# An apostrophe inside a word: "isn't", "can’t", "Market's" are one word.
_APOSTROPHE = re.compile(r"(?<=[a-z0-9])['\u2019\u2018\u02bc`\u00b4](?=[a-z])")


def normalize(text):
    text = strip_accents(str(text or "")).lower()
    text = _APOSTROPHE.sub("", text)
    return re.sub(r"[^a-z0-9\s]", " ", text)


def _join_digits(text):
    """Digits as a transcriber writes them: drop street addresses ("120 Harbor
    Road"), drop a ".00" cents part, make other cents malformed ("1240.50" ->
    "1240 50", never read as 1240), join thousands separators ("1,240" ->
    "1240")."""
    text = ADDRESS_RE.sub(" ", str(text or ""))
    text = re.sub(r"(?<=\d)[.,]00(?!\d)", "", text)
    text = re.sub(r"(?<=\d)[.,](\d{2})(?!\d)", r" \1", text)
    return re.sub(r"(?<!\d)(\d{1,3})((?:[.,\s]\d{3})+)(?!\d)",
                  lambda m: m.group(1) + re.sub(r"\D", "", m.group(2)), text)


def tokens(text):
    return _drop_spoken_addresses(normalize(_join_digits(text)).split())


def _is_num(tok):
    return tok.isdigit() or tok in _WORDS


is_number_word = _is_num
SCALES = _SCALES


def _drop_spoken_addresses(toks):
    """Remove an address read aloud: a run of number tokens followed by up to
    three name words and a street type ("one twenty harbor road"), then a
    complement and its number ("unit four"); and a complement word with the
    number after it anywhere ("unit 4"). An address is never part of the
    amount."""
    drop = set()
    for t, tok in enumerate(toks):
        if tok not in _STREET_WORDS:
            continue
        k = t - 1
        names = 0
        while k >= 0 and not _is_num(toks[k]) and toks[k] not in _NOT_NAME and names < 3:
            k -= 1
            names += 1
        if names == 0 or k < 0 or not _is_num(toks[k]):
            continue
        j = k
        while j >= 0 and (_is_num(toks[j]) or toks[j] in _DIRECTION_WORDS):
            j -= 1
        drop.update(range(j + 1, t + 1))
    for t, tok in enumerate(toks):
        if tok in _COMPLEMENT_WORDS and t + 1 < len(toks):
            v, nxt = _small_group(toks, t + 1)
            if v is not None:
                drop.update(range(t, nxt))
            elif len(toks[t + 1]) <= 2 and toks[t + 1].isalnum():
                drop.update((t, t + 1))           # "unit b", "dock 9b"
    return [tok for t, tok in enumerate(toks) if t not in drop]


def _small_group(toks, i):
    """A 0-999 number at toks[i] (words or digits) not followed by a scale."""
    if i < len(toks) and toks[i].isdigit():
        v, nxt = (int(toks[i]), i + 1) if int(toks[i]) < 1000 else (None, i)
    else:
        v, nxt = _below_1000(toks, i)
    if v is None or (nxt < len(toks) and toks[nxt] in _SCALES):
        return None, i
    return v, nxt


def number_phrases(toks):
    """Maximal runs of number tokens ("and" joins only between two of them;
    "a" counts only right before a scale: "a thousand"). A lone "a" is the
    article."""
    runs, cur = [], []
    n = len(toks)
    for i, t in enumerate(toks):
        if _is_num(t):
            cur.append(t)
        elif t == "a" and i + 1 < n and toks[i + 1] in _SCALES:
            cur.append(t)
        elif t == "and" and cur and i + 1 < n and _is_num(toks[i + 1]):
            cur.append(t)
        else:
            if cur:
                runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs


def _below_100(toks, i):
    """A 1-99 group in words at toks[i] -> (value, next index) or (None, i)."""
    n = len(toks)
    if i < n and toks[i] in _TENS:
        v = _TENS[toks[i]]
        if i + 1 < n and 1 <= _UNITS.get(toks[i + 1], 0) <= 9:
            return v + _UNITS[toks[i + 1]], i + 2
        return v, i + 1
    if i < n and _UNITS.get(toks[i], 0) > 0:
        return _UNITS[toks[i]], i + 1
    return None, i


def _rest_below_100(toks, i, v):
    """After "hundred" or a scale: an optional "and" and a 1-99 group."""
    j = i + 1 if i < len(toks) and toks[i] == "and" else i
    r, k = _below_100(toks, j)
    if r is not None:
        return v + r, k
    return v, i


def _below_1000(toks, i):
    """A 1-999 group in words at toks[i] -> (value, next index) or (None, i)."""
    n = len(toks)
    if i < n and toks[i] == "a" and i + 1 < n and toks[i + 1] == _HUNDRED:
        return _rest_below_100(toks, i + 2, 100)
    v, j = _below_100(toks, i)
    if v is not None and v <= 9 and j < n and toks[j] == _HUNDRED:
        return _rest_below_100(toks, j + 1, v * 100)
    return v, j


def parse_phrase(toks):
    """One number phrase (list of tokens) -> int, or None if malformed.
    [N million] [N thousand] [N], N being 1-999 in words or a digit group;
    or "twelve hundred forty" (10-99 hundred, then 1-99) with no scale."""
    n, i, total, used = len(toks), 0, 0, False

    def group(i):
        if i < n and toks[i].isdigit():
            return int(toks[i]), i + 1
        if i < n and toks[i] == "a" and i + 1 < n and toks[i + 1] in (_THOUSAND,) + _MILLION:
            return 1, i + 1
        return _below_1000(toks, i)

    # "twelve hundred forty", "fifteen hundred": hundreds counted past nine
    v, j = _below_100(toks, 0)
    if v is not None and v >= 10 and j < n and toks[j] == _HUNDRED:
        v, j = _rest_below_100(toks, j + 1, v * 100)
        return v if j == n else None

    for scale, words in ((1_000_000, _MILLION), (1000, (_THOUSAND,))):
        v, j = group(i)
        if j < n and toks[j] in words:
            if v is None or v >= 1000:
                return None                  # "million" with no count, "1240 thousand"
            total += v * scale
            i, used = j + 1, True
            if i < n and toks[i] == "and":
                i += 1
    v, j = group(i)
    if v is not None:
        if used and v >= 1000:
            return None                      # "five thousand 1240"
        total += v
        i, used = j, True
    if i != n or not used:
        return None
    return total


def _amount(toks):
    """(value in dollars or None, reason) from the tokens where the amount was said."""
    phrases = number_phrases(toks)
    if not phrases:
        return None, "no amount heard"
    if len(phrases) > 1:
        return None, "more than one number heard"
    v = parse_phrase(phrases[0])
    if v is None:
        return None, "the number heard is not well formed"
    if v > MAX_AMOUNT:
        return None, "the number heard is out of range"
    return v, ""


def words_to_int(text):
    """Parse the one English number phrase in `text` (up to 999,999,999), or
    None: no number, more than one separate number, or a malformed one.

    A transcriber may also write the number in digits with thousands
    separators ("1,240", "$1 240", "1240.00"); those groups are joined first
    so they do not read as 1 + 240."""
    return _amount(tokens(text))[0]


_LABEL_RE = re.compile(r"^\s*(?:deliver(?:y)? to|ship(?:ping)? to|send to)\s*:?\s*",
                       re.IGNORECASE)


def name_of(address_text):
    """The pixels read "Name · address" (maybe after a "Ship to" label); the
    spoken confirmation uses the name: what comes before "·", " - " or the
    street address."""
    text = str(address_text or "")
    m = ADDRESS_RE.search(text)
    after = ""
    if m:
        text, after = text[:m.start()], text[m.end():]
    name = _LABEL_RE.sub("", text.split("·")[0].split(" - ")[0]).strip(" ,;:")
    return name or _name_after(after)


def _name_after(rest):
    """The portal also paints the name after the address ("SHIP TO 120 Harbor
    Road, Unit 4, Riverton Larkspur Market", read by Spark on 3 Nov): skip the
    unit, directionals and city, and what remains is the name."""
    words = re.split(r"[\s,;:·]+", rest.split(" - ")[-1])
    words = [w for w in words if w]
    i = 0
    while i < len(words):
        w = words[i].lower().strip(".#")
        if w in COMPLEMENTS:
            i += 2                         # "Unit 4"
        elif w in CITY_WORDS or w in DIRECTIONALS or w.isdigit():
            i += 1
        else:
            break
    return " ".join(words[i:])


def _find_name(said, name):
    """Index where the name's words start in `said` (in order), or -1."""
    if not name:
        return -1
    for i in range(len(said) - len(name) + 1):
        if said[i:i + len(name)] == name:
            return i
    return -1


def address_matches(transcript, pixel_address_text):
    """True when the destination NAME read from the pixels is spoken, word by
    word and in order. The address digits are not part of it."""
    return _find_name(tokens(transcript), normalize(name_of(pixel_address_text)).split()) >= 0


def heard_amount(transcript, pixel_address_text=None):
    """(value in cents or None, reason). Only the amount phrase before the
    destination's name counts; after it only when nothing was said before (so
    an address read after the name cannot change the amount)."""
    toks = tokens(transcript)
    name = normalize(name_of(pixel_address_text)).split() if pixel_address_text else []
    at = _find_name(toks, name)
    if at < 0:
        v, why = _amount(toks)
    else:
        before, after = toks[:at], toks[at + len(name):]
        v, why = _amount(before) if number_phrases(before) else _amount(after)
    return (None if v is None else v * 100), why


def negated(transcript, pixel_address_text=None):
    """The negation/cancel words heard outside the destination's name."""
    name = set(normalize(name_of(pixel_address_text)).split()) if pixel_address_text else set()
    return [t for t in tokens(transcript) if t in NEGATIONS and t not in name]


def unexpected_words(transcript, pixel_address_text=None):
    """The words heard that are not the amount, the destination's name or a
    FILLER word (an address read aloud is already dropped)."""
    name = set(normalize(name_of(pixel_address_text)).split()) if pixel_address_text else set()
    return [t for t in tokens(transcript)
            if not (_is_num(t) or t in name or t in FILLER)]


def amount_in_range(pixel_amount_cents):
    try:
        return 1 <= int(pixel_amount_cents) <= MAX_AMOUNT * 100
    except (TypeError, ValueError):
        return False


def amount_check(transcript, pixel_amount_cents, pixel_address_text=None):
    """(ok, heard value in cents or None, reason when not ok)."""
    if not amount_in_range(pixel_amount_cents):
        return False, None, "amount out of range (voice supports USD 0.01 to %s)" % format(MAX_AMOUNT, ",")
    v, why = heard_amount(transcript, pixel_address_text)
    if v is None:
        return False, None, why
    if v != int(pixel_amount_cents):
        return False, v, "heard a different amount"
    return True, v, ""


def amount_matches(transcript, pixel_amount_cents, pixel_address_text=None):
    """True when the one amount spoken equals the amount read from the pixels."""
    return amount_check(transcript, pixel_amount_cents, pixel_address_text)[0]


def voice_matches(transcript, pixel_amount_cents, pixel_address_text):
    """Both the amount and the destination's name must match, with no negation.
    Returns (ok, detail)."""
    neg = negated(transcript, pixel_address_text)
    if neg:
        return False, "does not match: negation heard (%s)" % " ".join(neg)
    amt, _v, why = amount_check(transcript, pixel_amount_cents, pixel_address_text)
    rec = address_matches(transcript, pixel_address_text)
    extra = unexpected_words(transcript, pixel_address_text)
    if amt and rec and not extra:
        return True, "amount and destination match"
    missing = []
    if not amt:
        missing.append("amount (%s)" % why)
    if not rec:
        missing.append("destination")
    if extra:
        missing.append("unexpected words heard (%s)" % " ".join(extra))
    return False, "does not match: " + ", ".join(missing)
