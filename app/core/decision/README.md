# TESTIGO+ interceptor

The checker that sits between the agent *Wonder* and the browser. Nothing the
agent proposes reaches the page without passing through `check`; after the
click it runs `verify`. This folder is the **decision core** — pure, standard
library only, no browser, model or network — so it is testable today and wires
to Playwright / SAM 3.1 / Spark / FastAPI later without changing the rules.

Everything is a simulation: fake supplier, buyer warehouse and attacker address.

## Run

```bash
make test                                         # unit tests (all packages)
.venv/bin/python -m tests.demos.interceptor_demo  # fixture demo of the five rules
.venv/bin/python -m app.core.policy.model            # inspect the signed policy
```

Paths resolve from the repo root (`app/common/config.py`). The test captures and
the demo live in `tests/` since F0: they prove the rules are wired, not that
detection works on real captures.

## The five rules (in order, first match decides)

| # | Condition (read from the **pixels**, never the DOM) | Verdict | Action |
|---|---|---|---|
| 1 | SAM can't find amount, address or confirm button ≥ 0.50 confidence | `cannot_verify` | block |
| 2 | Text in the code not drawn, or drawn text not in the code | `divergence` | block |
| 3 | Pixel delivery address/total breaks the policy (or a stray address is on screen) | `policy_violation` | block |
| 4 | All agree and it confirms the order | `ok` | ask for approval |
| 5 | After the click, executed crops ≠ approved crops | `mismatch` | flag the receipt |

Rule 1 runs first on purpose: a comparison you can't read is not a pass. The
address and amount used for rule 3 come from the pixel channel, so a hidden
or swapped DOM value can't push an order to another address.

## Pieces

```
app/core/decision/
  engine.py              the five rules + after-click verify  <- the contribution
  instruction_filter.py  does divergent text read as an instruction? (F5)
  sensitive.py           which actions are sensitive (the confirm click)
  events.py              constructors for every event (check.result, verify.result, …)
  guard.py               check_screen(): the same engine for any agent (spec 07 M9)
  test_*.py              unit tests
```

Moved out on 1 Nov (spec 09): the policy model to `app/core/policy/model.py`,
`Capture` + `PixelChannel` (`FixtureChannel`, `SamSparkChannel`) to
`app/adapters/meta/channels.py`, and the FastAPI service to
`app/runtime/service/api.py`.

The committed policy lives in `app/core/policy/larkspur.policy.yaml`; one signed live from
view 1 goes to `runs/policy/active.policy.yaml` and wins while it exists
(`app.common.config.policy_path()`, used by the service, the loop, the bench and
`testigo verify`). Its sha256 is stamped in and is the same hash the receipt and
`testigo verify` will use.

## Wiring the real inputs later

- **Capture** — fill `code_lines` from the page's DOM text and `rendered_lines`
  from what is actually painted (incl. text inside images); screenshot bytes
  and per-region crops from Playwright.
- **PixelChannel** — `SamSparkChannel(sam, spark)`: `sam(screenshot)` returns
  boxes + scores (SAM 3.1), `spark(crop)` reads each crop (Spark 1.3). Any
  failure must return low confidence so rule 1 blocks rather than guessing.
- **Transport** — the engine returns plain dict events; a FastAPI app pushes
  them over WebSocket to the interface. The core doesn't change.

## Acceptance (Oct 30)

`.venv/bin/python -m tests.demos.interceptor_demo` asserts, on fixtures,: A1 and A2 are blocked, clean is not,
plus `cannot_verify`, `policy_violation` and the after-click `mismatch`.

## What is real vs simulated

Real: the decision logic, the divergence detection, the event contract, the
policy hash, the after-click comparison. Simulated here: the screenshots and
SAM/Spark readings (fixtures). Plug the two adapters above in to run it live.
