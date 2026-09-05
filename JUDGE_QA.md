# JUDGE_QA.md — Anticipated Questions & Answers

**Why did you use an AI agent instead of a normal search UI?**
Because the customer's real requirement — "black running shoes under ₹3000 for daily
running" — is expressed in natural language with implicit trade-offs (budget vs.
quality vs. color). A form-based filter UI forces the customer to do that translation
themselves. The agent does it, and explains its reasoning in plain language, which a
filter UI can't do as naturally.

**Why not just a normal search system, then?**
We do have one — `product_service.search_products` is a deterministic, filterable
query over the real catalog. The agent's job is only to turn conversation into calls
to that search function and to explain results — it never replaces the actual data
layer, and it never invents a product that search didn't return.

**How does tool calling work here?**
The agent (currently rule-based NLU, swappable for Claude tool-calling) can only call
a fixed set of narrow functions in `app/agent/tools.py` — search, recommend, add to
cart, get cart, validate checkout, etc. It cannot execute raw SQL or call Razorpay
directly. Every call is logged to `agent_actions` with input, output, and whether the
backend allowed it.

**How do you prevent hallucinated products?**
`Product.to_agent_dict()` is the *only* representation of a product the agent ever
sees, and it's built directly from the `products` table. There's no free-text
generation step between the catalog and what the agent presents — the agent narrates
existing rows, it doesn't compose new ones.

**How do you prevent unauthorized payments?**
Three independent gates in `app/policy.py`, all re-checked from the database on every
call, not trusted from prior state: (1) `check_user_confirmation` — no payment without
an explicit "yes" captured on the order; (2) `check_transaction_limit` — hard ceiling
(₹5,000 by default); (3) `check_automatic_payment` — the agent can never trigger a
charge on its own regardless of what it inferred. Even if a bug let the agent call the
payment tool without user input, these three checks are on the write path, not just
suggested to the agent.

**How do you handle duplicate payments?**
Two layers: (1) `Order.idempotency_key` is a hash of the cart's contents, so
re-submitting the same cart returns the same order; (2)
`payment_service.create_payment_for_order` checks for an existing `Payment` row before
ever calling Razorpay's order-create API, and reuses it if found. Retries use the same
Razorpay order id rather than minting a new one. Webhooks are deduplicated by
`event_id` with a unique DB constraint.

**How do you verify Razorpay payments?**
Server-side only, via `razorpay.Client.utility.verify_payment_signature`, which checks
the HMAC-SHA256 signature Razorpay returns against our key secret. The frontend
forwards whatever Razorpay's Checkout.js gives it, but the order is only marked `PAID`
after our backend independently verifies that signature. We never trust a frontend
"success" callback by itself.

**Why is auditability important?**
Because "trust me, the agent did the right thing" isn't a defensible position for
money movement. Every tool call, policy decision (allowed *and* blocked), and payment
state transition is written to an append-only `audit_events` table with a reason
string, previous/new state, and amount — visible per-order in the merchant dashboard.
A human can always reconstruct exactly what happened and why.

**What happens when payment fails?**
The failed attempt is recorded (`payment_attempts`), the order is *not* left in an
ambiguous state, and no duplicate order is created. The customer is told plainly that
no successful payment was recorded and how many retries remain
(`MAX_PAYMENT_RETRY_ATTEMPTS`, default 2). After the limit, the order is marked
`FAILED` and the customer is told to try another method or contact support — no
infinite retry loop.

**How did you measure business impact?**
`GET /api/analytics` computes GMV, AOV, upsell acceptance, and payment success rate
from real orders processed in this running instance — no invented numbers. For a
larger sample, `POST /api/demo/simulate` runs a reproducible, seeded batch of 100
scripted sessions through the *same* agent and policy code path and stores results
separately, clearly labeled synthetic.

**What is synthetic data, here specifically?**
Scripted conversational sessions (e.g. "I need running shoes under 2500" → "add it" →
"checkout" → "yes") run through the real code, with a seeded RNG only for simulating
the payment-success coin flip at the very end. It's not fabricated business metrics —
it's real code execution against synthetic user input, and it's stored in a separate
table (`simulation_runs`) that the real-metrics endpoint never reads from.

**What would you change for production?**
Swap SQLite for Postgres (models are already dialect-agnostic), add per-user auth and
session ownership checks, add Alembic migrations, put the policy limits behind a
merchant-configurable admin panel instead of `.env`, add rate limiting, and expand
webhook coverage to refunds/disputes.

**What was the hardest engineering problem?**
Keeping the "agent suggests, backend decides" boundary airtight while still making the
conversation feel natural — e.g. the upsell flow needed to feel like a normal
back-and-forth ("would you also like socks?") while guaranteeing that `is_upsell=True`
items are never added without a real user turn confirming it, even defensively inside
the tool layer itself (see the redundant check in `tools.tool_add_to_cart`).

**What broke during development and how did you fix it?**
Early on, retries could have created a second Razorpay order per failed attempt.
Fixed by making `create_payment_for_order` check for an existing `Payment` row *before*
calling Razorpay at all, and by making the retry endpoint explicitly reuse
`payment.razorpay_order_id` rather than calling create-order again.
