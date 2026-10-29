"""Approval: voice confirms the intent, the passkey proves it is the person.

The loop asks an `Approver` when the interceptor says a payment needs approval.
Offline, `AutoApprover` grants (the happy path) and `DenyApprover` refuses.

The real approver (not wired here) records a spoken confirmation, checks it
against the amount and recipient read from the pixels, and then asks WebAuthn
for a passkey. Voice decides *what*; the passkey decides *who*.
"""


class Approver:
    def approve(self, approval_event):      # pragma: no cover - interface
        """Return (granted: bool, info: dict) for an approval.requested event."""
        raise NotImplementedError


class AutoApprover(Approver):
    """Grants, as if the person read the amount aloud and tapped the passkey."""

    def __init__(self, voice_transcript="ciento veinte mil pesos a Distribuidora X"):
        self.voice_transcript = voice_transcript

    def approve(self, approval_event):
        return True, {
            "method": "passkey",
            "voice_transcript": self.voice_transcript,
            "voice_match": True,
        }


class DenyApprover(Approver):
    """Refuses — e.g. the spoken amount did not match the screen."""

    def __init__(self, voice_transcript="ciento cincuenta mil pesos", reason="voice did not match"):
        self.voice_transcript = voice_transcript
        self.reason = reason

    def approve(self, approval_event):
        return False, {
            "method": "passkey",
            "voice_transcript": self.voice_transcript,
            "voice_match": False,
            "reason": self.reason,
        }


class WebAuthnApprover(Approver):   # pragma: no cover - needs a browser + mic
    """Real approver: browser microphone + Voice Transcribe + WebAuthn passkey."""

    def __init__(self, transcribe, webauthn):
        self.transcribe = transcribe
        self.webauthn = webauthn

    def approve(self, approval_event):
        raise NotImplementedError("record voice, compare to pixels, then WebAuthn")
