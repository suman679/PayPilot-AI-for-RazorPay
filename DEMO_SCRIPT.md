# DEMO_SCRIPT.md — PayPilot AI, 5-Minute Walkthrough

**Setup before you go on stage:** backend running (`./run.sh` or manual steps),
frontend running (`npm run dev`), browser open to the Shop page, dashboard open in a
second tab. If you have real Razorpay TEST keys in `.env`, great — otherwise the app
runs in mock mode automatically and the checkout modal will say so.

---

### 0:00–0:30 — Problem

> "AI shopping agents are everywhere right now, but almost none of them answer the
> question a payments company actually cares about: what stops the agent from
> spending money it shouldn't? PayPilot AI is a conversational shopping agent where
> every recommendation is explainable and every payment is bounded, gated, and
> audited — the agent can *propose* a charge, but only our backend policy engine can
> *approve* one."

### 0:30–1:15 — AI product discovery

Type (or click demo button **A**):

> "I need black running shoes under ₹3000 for daily running."

**Say:** "The agent is searching our real product catalog — no hallucinated products,
no invented prices. It's ranking by fit and explaining *why* each one qualifies."

Point at the reasons under each product card (budget, color, category, stock).

### 1:15–2:00 — Recommendation + upsell

Type: `add it`

**Say:** "It adds the top pick and — because this is commonly bought together —
suggests one bounded upsell. Notice it doesn't add the socks automatically; it waits
for my yes."

Type: `yes`

**Say:** "Now the cart total updates and we track that as an AI-influenced upsell,
which shows up on the merchant dashboard later."

### 2:00–2:45 — Cart + safety gate

Type: `checkout`

**Say:** "Before anything financial happens, the backend independently validates the
cart against policy — this cart passes, so it asks me to explicitly confirm. This
confirmation gate exists no matter what the agent inferred from the conversation."

Type: `yes`

**Say:** "Only now — with explicit confirmation and inside the ₹5,000 policy limit —
does it create a real Razorpay TEST MODE order and launch Checkout."

### 2:45–3:30 — Razorpay test payment

Complete the checkout (real Razorpay test card, or the "Simulate successful payment"
button in mock mode).

**Say:** "The frontend never decides if a payment succeeded — it just relays what
Razorpay sends back. Our backend independently verifies the cryptographic signature
before marking this order paid. That's the one source of truth."

### 3:30–4:15 — Failure handling

Click demo button **C** (or start a fresh search), add a product, checkout, confirm,
and this time click **"Simulate failed payment"** (or use a Razorpay test failure
card).

**Say:** "Here's the failure path the brief asked for. Payment fails — the system
detects it, does *not* create a duplicate order, and tells me plainly: no successful
payment was recorded, and I have one retry remaining."

Type: `retry` and complete the payment successfully this time.

**Say:** "It reused the *same* Razorpay order for the retry — that's our idempotency
guarantee. If I'd failed twice, it would have stopped and told me to contact support
instead of retrying forever."

### 4:15–4:45 — Merchant dashboard + audit trail

Switch to the Dashboard tab.

**Say:** "Every order I just placed shows up here — GMV, AI-assisted orders, upsell
acceptance, payment success rate — computed only from real orders in this session."

Click into a recent order.

**Say:** "And here's the full audit trail for that one order: every tool call, every
policy check, every state transition, timestamped and immutable. A Razorpay engineer
reviewing this agent can see exactly what it did and why."

### 4:45–5:00 — Metrics + final pitch

Scroll to the "Synthetic evaluation" panel, click **Run 100-session simulation**.

**Say:** "For business-impact numbers beyond what we can generate live, we run a
reproducible, seeded batch of 100 scripted sessions through the exact same agent and
policy code — and it's clearly labeled synthetic, never mixed with the real GMV
figures above. Reliability over flashy AI, safety over autonomy, real working flow
over a mocked demo — that's PayPilot AI."

---

## Quick reference: what to type for each scenario

| Scenario | Steps |
|---|---|
| **A** Successful purchase | search → `add it` → `no` (skip upsell) → `checkout` → `yes` → complete payment |
| **B** Upsell accepted | search → `add it` → `yes` (accept upsell) → `checkout` → `yes` → complete payment |
| **C** Payment failure | ... → `checkout` → `yes` → simulate/trigger failure → `retry` → complete payment |
| **D** Over spending limit | "show me a running watch" → `add it` → `checkout` (blocked, ₹8999 > ₹5000) |
| **E** Duplicate/retry protection | type `checkout` twice in a row — same order id both times; retry reuses same Razorpay order id (visible in order detail page) |
