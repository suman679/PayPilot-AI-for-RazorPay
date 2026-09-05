"""
Synthetic evaluation harness (section 15).

Runs N simulated shopping sessions through the SAME agent + policy code
path used by real chat, but with synthetic scripted user messages and a
seeded RNG so results are reproducible. Results are stored in
`SimulationRun` - a table that is never read by analytics_service, so
simulated numbers can never leak into "real" merchant metrics.
"""
import random
import uuid

from sqlalchemy.orm import Session

from app.agent import agent
from app.database import SessionLocal
from app.models import AgentSession, SimulationRun, User


SCRIPTS = [
    ["I need black running shoes under 3000", "add it", "yes", "checkout", "yes"],
    ["I need running shoes under 2500", "add it", "no", "checkout", "yes"],
    ["show me a running watch", "add it", "checkout", "yes"],  # likely over budget-> may be blocked at policy
    ["I need a jacket for running", "add it", "yes"],  # abandons before checkout
    ["running shoes under 3000", "first", "add it", "yes", "checkout", "no"],  # cancels at gate
]


def _ensure_sim_user(db: Session) -> str:
    user = db.query(User).filter(User.email == "sim@paypilot.ai").first()
    if not user:
        user = User(id="user_sim", name="Simulated Shopper", email="sim@paypilot.ai")
        db.add(user)
        db.commit()
    return user.id


def run_simulation(num_sessions: int = 100, seed: int = 42) -> dict:
    rng = random.Random(seed)
    db = SessionLocal()
    try:
        user_id = _ensure_sim_user(db)
        completed = 0
        abandoned = 0
        upsell_offered = 0
        upsell_taken = 0
        blocked = 0
        totals = []

        for _ in range(num_sessions):
            script = list(rng.choice(SCRIPTS))
            sess = AgentSession(user_id=user_id, demo_scenario="SIMULATION", state={})
            db.add(sess)
            db.commit()
            db.refresh(sess)

            order_completed = False
            for msg in script:
                turn = agent.handle_turn(db, sess, user_id, msg)
                for m in turn.messages:
                    if m.policy_notice and not m.policy_notice.get("allowed", True):
                        blocked += 1
                    if "Would you also like" in (m.text or ""):
                        upsell_offered += 1
                    if m.ui_action == "LAUNCH_PAYMENT":
                        # simulate a payment outcome deterministically from the seed
                        order_completed = rng.random() > 0.08  # ~92% simulated success rate
                db.refresh(sess)

            state = sess.state or {}
            if state.get("pending_upsell_id") is None and upsell_offered:
                pass  # accepted or declined already accounted in message text scan above

            if order_completed:
                completed += 1
                from app.models import Order
                order = db.get(Order, state.get("order_id")) if state.get("order_id") else None
                if order:
                    totals.append(order.total_amount)
            else:
                abandoned += 1

        gmv = sum(totals)
        aov = (gmv / len(totals)) if totals else 0

        results = {
            "num_sessions": num_sessions,
            "completed_orders": completed,
            "abandoned_sessions": abandoned,
            "upsell_impressions": upsell_offered,
            "blocked_unsafe_actions": blocked,
            "simulated_gmv": gmv,
            "simulated_average_order_value": round(aov, 2),
            "note": "SYNTHETIC/SIMULATED METRICS - not real Razorpay transactions.",
        }

        db.add(SimulationRun(num_sessions=num_sessions, results=results))
        db.commit()
        return results
    finally:
        db.close()
