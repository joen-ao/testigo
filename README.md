# TESTIGO+

An independent witness for computer-use AI agents. TESTIGO+ sits between the
agent and the browser, reads the **pixels** of the screen, and checks that what
the agent asked for, what the person approved and what actually executed are
the same. If anything differs, it blocks, and it leaves a signed receipt anyone
can verify.

**This is a simulation.** Simulated: the supplier portal and the payment (no
real money, no real accounts), Doña Marta's shop data, and the attacker account
`300-XXX-0000`. Real: the agent, the detection, the approval, the receipt
signature and the measurement.

## Run

Needs macOS or Linux, `git`, `make`, and Python 3.12 (`brew install python@3.12`).

```bash
cp .env.example .env    # fill in your own Meta API key; never commit .env
make run                # installs what is missing, starts portal + interceptor
```

Then open the interface at <http://localhost:8090/>. It shows the live events of
a run (arrow keys or 0–8 move between views). To check that the views paint
without a real run, replay the offline fixtures. They are marked as test data on
screen and are never for the video:

```bash
.venv/bin/python -m tests.demos.ui_replay a3 --both
```

| Command | What it does |
| --- | --- |
| `make test` | unit tests with test data (no network, no keys) |
| `make test-live` | tests against real Meta models (needs `.env`) |
| `make doctor` | versions, Chromium, a 1280×800 capture of the portal |
| `make check-secrets` | no keys, signing keys or evidence in files to commit |
| `make gate` | today's gate checklist |

Specs (Spanish) are the source of truth: [`docs/specs/`](docs/specs/).

## License

Apache-2.0. See [LICENSE](LICENSE).
