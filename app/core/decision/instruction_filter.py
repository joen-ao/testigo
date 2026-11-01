"""F5: does a line of divergent text look like an instruction for the agent?

The divergence check finds text that is in one channel (page code / pixels) and
not the other. Most such text is legitimate: collapsed menus, screen-reader
labels, promos. Only text that reads as an instruction aimed at the agent
should raise the alarm, or TESTIGO+ would block normal pages (false positives).

A line is flagged if it has any of these signals (F5-D1):
  - a street address (number + street name + Road/Street/Avenue/...; a line
    carrying an address that appears in only one channel is suspicious
    whatever the address);
  - a term that addresses an agent together with a delivery or confirmation
    verb (or a change of the delivery address).

Agent terms and verbs are matched in English, and also in Spanish (kept as
defence in depth; the scenario is in English).

Before matching (spec 10 P3) the text is folded: Unicode compatibility forms
(full-width digits "８８" -> "88") and the Cyrillic and Greek letters that look
like Latin ones ("Аgent" with a Cyrillic А). And an address cut across two
consecutive divergent lines ("Ship this order to 88" / "Mill Street") is
caught by also reading each pair of neighbouring lines together (the address
signal only, so an agent term and a verb on two unrelated lines never join).

Known limit (F5-D4): an instruction written without any of these signals would
not be flagged. It is assumed and measured (a WitnessBench case and the corpus
in tests/security/injections.py), not hidden.
"""

import re
import unicodedata

from app.common.address import ADDRESS_RE

# Terms that address an agent, in English and Spanish (matched as whole words).
AGENT_TERMS = (
    "agent", "agents", "assistant", "assistants", "ai assistant", "ai agent",
    "system note for agents", "agente", "agentes", "asistente", "asistentes",
    "ia", "bot", "bots",
)

# Delivery / confirmation / change-of-destination verbs, in English and Spanish.
ACTION_VERBS = (
    "deliver", "ship", "send", "confirm",
    "change the delivery address", "change delivery address", "change the address",
    "update the delivery address", "update the address", "set the address",
    "entrega", "entregar", "envía", "envia", "enviar", "confirma", "confirmar",
    "cambia la dirección", "cambia la direccion", "cambiar la dirección",
    "actualiza la dirección", "actualiza la direccion", "actualizar la dirección",
    "usa la", "usar la", "manda", "mandar",
)

# Letters from other scripts that render like Latin ones (the common confusables).
_CONFUSABLES = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C",
    "Т": "T", "Х": "X", "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
    "і": "i", "ј": "j", "ѕ": "s", "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I",
    "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X", "ο": "o",
})


def fold(text):
    """Compatibility forms and look-alike letters folded to plain Latin."""
    return unicodedata.normalize("NFKC", str(text or "")).translate(_CONFUSABLES)


# Agent terms match as whole words ("ia" is not in "diaria" or "vía", "bot" is
# not in "botella" or "botón"); a multi-word term allows any spacing.
_AGENT_RE = re.compile(r"(?<!\w)(?:%s)(?!\w)" % "|".join(
    r"\s+".join(re.escape(w) for w in term.split())
    for term in sorted(AGENT_TERMS, key=len, reverse=True)))


def looks_like_instruction(text):
    """True when a divergent line reads as an instruction aimed at the agent."""
    t = " ".join(fold(text).split())
    if not t:
        return False
    if ADDRESS_RE.search(t):
        return True
    t = t.lower()
    if _AGENT_RE.search(t) and any(v in t for v in ACTION_VERBS):
        return True
    return False


def filter_instructions(lines):
    """Keep only the lines that look like an instruction, alone, or together
    with the next line when the two make a street address (an address split
    across two lines). Only the address signal is read across lines: an agent
    term on one line and a verb on the next are two unrelated lines."""
    lines = list(lines)
    flagged = [looks_like_instruction(x) for x in lines]
    for i in range(len(lines) - 1):
        joined = " ".join(fold("%s %s" % (lines[i], lines[i + 1])).split())
        if not (flagged[i] or flagged[i + 1]) and ADDRESS_RE.search(joined):
            flagged[i] = flagged[i + 1] = True
    return [x for x, f in zip(lines, flagged) if f]
