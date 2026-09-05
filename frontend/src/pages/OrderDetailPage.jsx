import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../lib/api.js";

const RESULT_COLOR = { OK: "text-signal", BLOCKED: "text-caution", ERROR: "text-danger" };

export default function OrderDetailPage() {
  const { orderId } = useParams();
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    api.getOrderDetail(orderId).then(setDetail).catch(() => {});
  }, [orderId]);

  if (!detail) return <div className="max-w-4xl mx-auto px-4 py-10 text-muted">Loading…</div>;

  const { order, items, payments, audit_trail } = detail;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 flex flex-col gap-8">
      <Link to="/dashboard" className="text-xs text-muted hover:text-paper">
        ← back to dashboard
      </Link>

      <div>
        <h1 className="font-display text-2xl mb-1">Order {order.id}</h1>
        <div className="flex gap-4 text-sm text-muted">
          <span>Status: <span className="text-paper">{order.status}</span></span>
          <span>Total: <span className="font-mono text-signal">₹{order.total_amount}</span></span>
          <span>Confirmed: {order.user_confirmed ? "yes" : "no"}</span>
        </div>
      </div>

      <div>
        <h2 className="font-display text-lg mb-3">Items</h2>
        <div className="border border-line rounded-xl divide-y divide-line">
          {items.map((i, idx) => (
            <div key={idx} className="flex justify-between px-4 py-3 text-sm">
              <span>
                {i.name} {i.is_upsell && <span className="text-caution text-xs ml-1">(upsell)</span>}
              </span>
              <span className="font-mono">₹{i.unit_price} × {i.quantity}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="font-display text-lg mb-3">Payment attempts</h2>
        <div className="border border-line rounded-xl divide-y divide-line">
          {payments.length === 0 && <div className="p-4 text-sm text-muted">No payment initiated yet.</div>}
          {payments.map((p) => (
            <div key={p.id} className="px-4 py-3 text-sm flex flex-col gap-1">
              <div className="flex justify-between">
                <span className="font-mono text-muted">{p.razorpay_order_id}</span>
                <span>{p.status}</span>
              </div>
              {p.attempts.map((a, i) => (
                <div key={i} className="text-xs text-muted pl-3">
                  attempt {a.attempt_number}: {a.result} {a.failure_reason ? `- ${a.failure_reason}` : ""}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="font-display text-lg mb-3">Audit trail</h2>
        <div className="border border-line rounded-xl divide-y divide-line font-mono text-xs">
          {audit_trail.map((e, i) => (
            <div key={i} className="px-4 py-3 flex flex-col gap-1">
              <div className="flex justify-between">
                <span className="text-paper">{e.event_type}</span>
                <span className={RESULT_COLOR[e.result] || "text-muted"}>{e.result}</span>
              </div>
              <div className="text-muted">{new Date(e.timestamp).toLocaleTimeString()} · {e.actor}
                {e.amount != null && <> · ₹{e.amount}</>}
              </div>
              {e.reason && <div className="text-muted">{e.reason}</div>}
              {(e.previous_state || e.new_state) && (
                <div className="text-muted">{e.previous_state} → {e.new_state}</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
