"""F5: does a line of divergent text look like an instruction for the agent?

The divergence check finds text that is in one channel (page code / pixels) and
not the other. Most such text is legitimate: collapsed menus, screen-reader
labels, promos. Only text that reads as an instruction aimed at the agent
should raise the alarm, or TESTIGO+ would block normal pages (false positives).

A line is flagged if, in English or Spanish, it has any of these signals (F5-D1):
  - a payment account number (a line carrying an account that appears in only
    one channel is suspicious whatever the account);
  - a term that addresses an agent together with a payment/action verb.

Known limit (F5-D4): an instruction written without any of these signals would
not be flagged. It is assumed and measured (a WitnessBench case), not hidden.
"""

import re

# Nequi-style account the demo uses (300-XXX-0000, 310-XXX-4417), case-insensitive.
ACCOUNT_RE = re.compile(r"\b\d{3}-[\dx]{3}-\d{4}\b", re.IGNORECASE)

# Terms that address an agent, in English and Spanish.
AGENT_TERMS = (
    "agent", "assistant", "ai assistant", "ai agent", "system note for agents",
    "agente", "asistente", "ia", "bot",
)

# Payment / change-of-target verbs, in English and Spanish.
ACTION_VERBS = (
    "pay", "transfer", "send", "change recipient", "update the recipient",
    "update recipient", "set recipient", "change the recipient",
    "pagar", "paga", "transferir", "transfiere", "enviar", "envía", "envia",
    "cambia el destinatario", "cambiar el destinatario", "cambia destinatario",
    "actualiza el destinatario", "actualizar el destinatario",
)


def looks_like_instruction(text):
    """True when a divergent line reads as an instruction aimed at the agent."""
    t = " ".join(str(text or "").split()).lower()
    if not t:
        return False
    if ACCOUNT_RE.search(t):
        return True
    if any(a in t for a in AGENT_TERMS) and any(v in t for v in ACTION_VERBS):
        return True
    return False


def filter_instructions(lines):
    """Keep only the lines that look like an instruction."""
    return [x for x in lines if looks_like_instruction(x)]
