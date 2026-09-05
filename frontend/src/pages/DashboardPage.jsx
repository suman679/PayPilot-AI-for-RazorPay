import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";

function Stat({ label, value, accent }) {
  return (
    <div className="border border-line rounded-xl p-4">
      <div className="text-xs uppercase tracking-wide text-muted mb-1">{label}</div>
      <div className={`font-mono text-2xl ${accent ? "text-signal" : "text-paper"}`}>{value}</div>
    </div>
  );
}

export default function DashboardPage() {
  const [analytics, setAnalytics] = useState(null);
  const [sim, setSim] = useState(null);
  const [loadingSim, setLoadingSim] = useState(false);

  const load = () => {
    api.getAnalytics().then(setAnalytics).catch(() => {});
    api.getLatestSimulation().then(setSim).catch(() => {});
  };

  useEffect(() => {
    load();
  }, []);

  const runSimulation = async () => {
    setLoadingSim(true);
    try {
      const res = await api.runSimulation(100);
      setSim(res);
    } finally {
      setLoadingSim(false);
    }
  };

  if (!analytics) return <div className="max-w-6xl mx-auto px-4 py-10 text-muted">Loading…</div>;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 flex flex-col gap-8">
      <div>
        <h1 className="font-display text-2xl mb-1">AI Commerce Overview</h1>
        <p className="text-muted text-sm">
          Computed from real Razorpay TEST MODE orders processed by this instance.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="GMV" value={`₹${analytics.gmv.toLocaleString()}`} accent />
        <Stat label="AI-assisted GMV" value={`₹${analytics.ai_assisted_gmv.toLocaleString()}`} />
        <Stat label="Paid orders" value={analytics.total_orders} />
        <Stat label="AI-assisted orders" value={analytics.ai_assisted_orders} />
        <Stat label="Avg order value" value={`₹${analytics.average_order_value}`} />
        <Stat label="Upsell acceptance" value={`${analytics.upsell_acceptance_rate}%`} />
        <Stat label="Payment success rate" value={`${analytics.payment_success_rate}%`} />
        <Stat label="Blocked unsafe actions" value={analytics.blocked_actions} />
      </div>

      <div>
        <h2 className="font-display text-lg mb-3">Top products</h2>
        <div className="border border-line rounded-xl divide-y divide-line">
          {analytics.top_products.length === 0 && (
            <div className="p-4 text-sm text-muted">No paid orders yet - run the demo checkout first.</div>
          )}
          {analytics.top_products.map((p) => (
            <div key={p.product_id} className="flex justify-between px-4 py-3 text-sm">
              <span>{p.name}</span>
              <span className="font-mono text-signal">₹{p.revenue.toLocaleString()} · qty {p.qty}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="font-display text-lg mb-3">Recent orders</h2>
        <div className="border border-line rounded-xl divide-y divide-line">
          {analytics.recent_orders.length === 0 && (
            <div className="p-4 text-sm text-muted">No orders yet.</div>
          )}
          {analytics.recent_orders.map((o) => (
            <Link
              key={o.id}
              to={`/orders/${o.id}`}
              className="flex justify-between px-4 py-3 text-sm hover:bg-ledger transition-colors"
            >
              <span className="font-mono text-muted">{o.id}</span>
              <span
                className={
                  o.status === "PAID" ? "text-signal" : o.status === "FAILED" ? "text-danger" : "text-caution"
                }
              >
                {o.status}
              </span>
              <span className="font-mono">₹{o.total_amount}</span>
            </Link>
          ))}
        </div>
      </div>

      <div className="border border-caution/40 bg-caution/5 rounded-xl p-5">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-display text-lg">Synthetic evaluation (SIMULATED)</h2>
          <button
            onClick={runSimulation}
            disabled={loadingSim}
            className="text-xs border border-caution/60 text-caution rounded-full px-3 py-1.5 disabled:opacity-50"
          >
            {loadingSim ? "Running…" : "Run 100-session simulation"}
          </button>
        </div>
        <p className="text-xs text-caution/80 mb-3">
          {sim?.note || "SYNTHETIC/SIMULATED METRICS - reproducible, seeded batch of scripted shopping "
            + "sessions run through the real agent + policy code path. Never presented as production performance."}
        </p>
        {sim && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm font-mono">
            <div>Sessions: {sim.num_sessions}</div>
            <div>Completed: {sim.completed_orders}</div>
            <div>Abandoned: {sim.abandoned_sessions}</div>
            <div>Upsell impressions: {sim.upsell_impressions}</div>
            <div>Blocked actions: {sim.blocked_unsafe_actions}</div>
            <div>Simulated GMV: ₹{sim.simulated_gmv}</div>
            <div>Simulated AOV: ₹{sim.simulated_average_order_value}</div>
          </div>
        )}
      </div>
    </div>
  );
}
