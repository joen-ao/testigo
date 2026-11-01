Build a one-page marketing landing page for **TESTIGO+**, an evidence-grade oversight layer for AI computer-use agents. It must look like a premium, professional product site (think Linear, Vercel, Stripe-level craft), not a template. Single HTML file (or React + Tailwind), no backend.

## The product (use this, don't invent features)
- TESTIGO+ sits between an AI agent that operates a browser and the browser itself.
- Before any sensitive action (e.g. clicking "Confirm order") it reads the screen in pixels with Meta's SAM 3.1 (finds the total, the shipping address and the button) and Muse Spark (reads each crop), compares them with a policy the owner said out loud and signed (Muse Voice transcribes it), and also checks that the page code and the pixels agree.
- If something doesn't match, the order is HELD for a person, who approves by reading the exact cropped values aloud; the voice must match the pixels.
- After the click it reads the screen again and seals everything in an Ed25519-signed receipt with hashes of the crops; `testigo verify receipt.json` re-checks signature, policy, evidence and "executed = approved".
- The agent is Meta's Muse Wonder. Everything else in the demo is simulated: buyer **Larkspur Market** (warehouse: 120 Harbor Road, Unit 4, Riverton), supplier portal **Crestline Wholesale**, attacker **Dock 9 Storage** (88 Mill Street, Riverton), order PO-2041, total USD 1,240.00, limit USD 1,500 per order.
- Three attacks it catches: A1 an instruction hidden in the page code (font-size:0) — caught because code says what pixels don't; A2 an instruction painted faintly inside a banner image — caught because pixels say what code doesn't; A3 a forged address: the attacker's street shown under the buyer's own name — the agent can't know, but it isn't in the signed rules.
- Honest limits: each check adds roughly [N] seconds; an instruction written only in words can slip past the instruction filter (measured separately); when it can't read the screen it holds the order for a person; voice confirms intent, not identity (no passkey in this prototype).
- Results (WitnessBench, real models, 15 attacks + 5 clean orders, with and without TESTIGO+): use placeholders [X]/15 attacks succeed without, [Y]/15 with, [Z]/5 clean orders held, [N] s median per check.

## Visual direction: "forensic, but trustworthy"
- Dark ink background #0B0F14 with alternating warm-paper sections #F4F1EA. Accent "verified" teal #3CC9A9 (#0E7C66 on light). SAM boxes cobalt #3B6FD4. "Held" amber #F0B254. No alarm red anywhere except tiny mismatch marks.
- Type: Instrument Serif (huge editorial headlines, italic accents), Inter Tight (body), JetBrains Mono (labels, evidence, code, receipts). Headlines clamp(56px, 7vw, 112px), tight leading.
- Evidence motifs: corner crop marks, frame numbers, sha256 snippets, mono uppercase eyebrow labels, a faint 64px grid texture. Vertical section index on the left edge ("01 — THE WITNESS").

## Layout rules (important)
- Every main section is a full screen: `min-height: 100vh`, content vertically centered, generous padding; only the nav and footer are small. Max content width ~1280px with fluid side padding. Fully responsive down to 375px.
- Sticky blurred nav: logo, Demo, Threats, How it works, Proof, FAQ, "Talk to us", primary pill button "Try the live demo".

## Sections, in order
1. **Hero**: headline "Your agent can be fooled. / The screen can't." (last line italic teal), one-sentence subhead, primary + secondary CTA, "Built on Meta: Muse Wonder · SAM 3.1 · Muse Spark · Muse Voice". Right side: an animated "capture" of the Crestline review screen on paper: a teal scan line sweeps down, SAM boxes draw in with labels ("TOTAL · 0.94", "SHIP TO · 0.92"), the ship-to line morphs from "120 Harbor Road, Unit 4" to "88 Mill Street, Riverton", the box turns amber, and an amber "HELD — address not in policy" stamp lands. Loop every ~9 s.
2. **Demo video**: big 16:9 player placeholder (play button, "[DEMO VIDEO]"), headline "A real agent. A real attack. Two minutes.", chapter list 0:00 rules / 0:25 agent fooled / 0:55 held / 1:30 receipt verified.
3. **The threat**: headline "Agents read things you never see." Three exhibit cards (A1/A2/A3) each with a mini visual; the hidden text "decodes" (from blank to amber) on view; hover lifts the card.
4. **How it works**: headline "Trust the screen, not the story." A three-node pipeline Agent → TESTIGO+ → Browser with an animated packet traveling and pausing at TESTIGO+ (which pulses). Below, four numbered steps: Sign your rules / Witness each sensitive click / Confirm what is real / Prove it afterwards.
5. **Proof**: headline "Don't trust us. Verify." Terminal window that types `testigo verify receipt.json` → 4 green checks, then `testigo verify swapped.json` → "4 executed = approved .. no · ship_to differs" in amber with a blinking caret.
6. **Measured**: three giant numbers with placeholders and one line of method.
7. **FAQ / limits** (paper background): accordion with the honest limits above.
8. **Final CTA**: "Put a witness between your agent and the world." + buttons.
9. Small footer: "Simulation only: simulated company, supplier and addresses. No real brands."

## Motion
- Entrance: staggered rise-in of hero lines. Scroll: each section's content reveals as it enters (CSS scroll-driven animations or IntersectionObserver), terminal lines type in sequence, numbers count up when visible. Subtle hover states on cards and buttons.
- Respect `prefers-reduced-motion` (show final states, no motion).

## Quality bar
- No lorem ipsum, no emoji, no generic gradients, no left-border accent cards, no stock illustrations. Real `<button>`/`<a>`, aria labels, visible focus, 4.5:1 contrast. Keep copy short and specific; every element must earn its place.
