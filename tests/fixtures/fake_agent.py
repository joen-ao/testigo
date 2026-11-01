"""Test-only stand-ins for the browser and the agent (moved out of agent/ by F0).

FixtureDriver   serves the portal scenarios as fixed captures (no browser),
                plus "swap" (changed after approval, for F8; not a portal scenario).
ScriptedAgent   a deterministic, deliberately susceptible agent: it obeys an
                injected "change the delivery address" instruction. It proves the loop is
                wired, nothing about Wonder.
run_fixture     runs the real loop with both, for unit tests and demos.

Never used by WitnessBench or the video: those refuse test drivers.
"""

import re

from agent.agent import Agent
from agent.driver import BrowserDriver, BUYER_ADDRESS, ATTACKER_ADDRESS
from common.address import ADDRESS_RE
from tests.fixtures import captures as fx

_INJECT_RE = re.compile(r"(?:change|set|update|deliver|cambia|actualiza|entrega)", re.IGNORECASE)


class FixtureDriver(BrowserDriver):
    is_test_double = True

    def __init__(self, scenario, variant=1):
        self.scenario = scenario
        self.variant = variant
        self._order = None
        self._pre = {
            "clean": fx.capture_clean,
            "a1": fx.capture_a1,
            "a2": fx.capture_a2,
            "a3": fx.capture_a3,
            "swap": fx.capture_swap_before,
            "blurred": fx.capture_blurred,
        }[scenario]()

    def observe(self):
        return self._pre

    def pixel_channel(self):
        return fx.channel_for(self.scenario)

    def execute(self, action):
        if action.get("kind") != "confirm":
            return
        intended = action.get("address_text", BUYER_ADDRESS)
        # A3 posts what its page shows (88 Mill Street under the buyer's
        # name); the swap changes the address at the click.
        delivered_to = ATTACKER_ADDRESS if self.scenario in ("a3", "swap") else intended
        self._order = {
            "address": delivered_to,
            "amount_cents": action.get("amount_cents", 124000),
            "scenario": self.scenario,
            "variant": self.variant,
        }

    def observe_after(self):
        if self.scenario == "a3":
            return fx.capture_a3(frame=164)
        if self.scenario == "swap":
            return fx.capture_swap_after()
        return fx.capture_clean(frame=164)

    @property
    def last_order(self):
        return self._order


class ScriptedAgent(Agent):
    is_test_double = True

    def __init__(self, order_total_cents=124000, obeys_injections=True):
        self.order_total_cents = order_total_cents
        self.obeys_injections = obeys_injections

    def propose(self, observation):
        seen = list(observation.code_lines) + list(observation.rendered_lines)
        injected = None
        for line in seen:
            m = ADDRESS_RE.search(line)
            if m and _INJECT_RE.search(line):
                injected = m.group(0)
                break
        address, rationale = BUYER_ADDRESS, "confirm order PO-2041 for delivery to the buyer"
        if injected and self.obeys_injections:
            address, rationale = injected, "followed on-screen instruction to change the address"
        return {"kind": "confirm", "address_text": address,
                "amount_cents": self.order_total_cents, "rationale": rationale}


def run_fixture(scenario="clean", variant=1, supervised=True, agent=None, approver=None,
                run_dir=None, signing_key=None):
    """Receipts are signed with a throwaway key unless one is given; the owner's
    key never signs fixture evidence."""
    from agent.loop import run
    from receipts import keys
    return run(FixtureDriver(scenario, variant), agent or ScriptedAgent(),
               supervised=supervised, approver=approver, run_dir=run_dir,
               signing_key=signing_key if signing_key is not None else keys.generate_seed())
