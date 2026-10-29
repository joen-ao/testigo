"""Wonder, the agent. It observes a frame and proposes the next action.

  ComputerUseAgent   the real loop over Meta's computer-use API (F3).
  parse_action       the single seam that turns an API response into our action
                     dict. Gate test 2 finds the real format; only this changes.

The offline scripted agent used by unit tests lives in tests/fixtures/.

An action is a small dict the loop understands, e.g.:
  {"kind": "pay", "recipient_acct": "310-XXX-4417", "amount_cop": 120000}
"""


class Agent:
    is_test_double = False

    def propose(self, observation):         # pragma: no cover - interface
        raise NotImplementedError


class ComputerUseAgent(Agent):   # pragma: no cover - needs the API (F3)
    """Real agent over Meta's computer-use API, through common.meta_client."""

    def __init__(self, meta_client):
        self.meta = meta_client

    def propose(self, observation):
        raise NotImplementedError("F3: send the screenshot, parse the returned action")


def parse_action(api_response):
    """Turn a computer-use API response into our action dict.

    GATE TEST 2: Wonder's action format and coordinate convention are not
    confirmed. This is the only place that depends on them. g2 saves the raw
    responses under runs/gate/<date>/g2/ so the format can be read and filled in.
    """
    raise NotImplementedError("action format not confirmed yet: see runs/gate/<date>/g2/")
