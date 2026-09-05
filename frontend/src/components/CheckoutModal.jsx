import { useState } from "react";
import { api } from "../lib/api.js";

export default function CheckoutModal({ payload, onResult, onClose }) {
  const [busy, setBusy] = useState(false);

  if (!payload) return null;

  const launchRealRazorpay = () => {
    const options = {
      key: payload.razorpay_key_id,
      amount: payload.amount_paise,
      currency: payload.currency,
      order_id: payload.razorpay_order_id,
      name: "PayPilot AI (TEST MODE)",
      description: `Order ${payload.order_id}`,
      theme: { color: "#2FBF8F" },
      handler: async (response) => {
        setBusy(true);
        try {
          const result = await api.verifyPayment({
            order_id: payload.order_id,
            razorpay_order_id: response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature,
          });
          onResult(result);
        } finally {
          setBusy(false);
        }
      },
      modal: {
        ondismiss: () => onClose(),
      },
    };
    const rzp = new window.Razorpay(options);
    rzp.on("payment.failed", async (response) => {
      setBusy(true);
      try {
        const paymentId = response?.error?.metadata?.payment_id || `pay_FAILED${Date.now()}`;
        const result = await api.verifyPayment({
          order_id: payload.order_id,
          razorpay_order_id: payload.razorpay_order_id,
          razorpay_payment_id: paymentId,
          razorpay_signature: "",
        });
        onResult(result);
      } finally {
        setBusy(false);
      }
    });
    rzp.open();
  };

  const simulate = async (outcome) => {
    setBusy(true);
    try {
      const result = await api.mockComplete(payload.order_id, payload.razorpay_order_id, outcome);
      onResult(result);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4">
      <div className="bg-ledger border border-line rounded-2xl p-6 w-full max-w-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="font-display text-lg">Razorpay Checkout</div>
          <button onClick={onClose} className="text-muted hover:text-paper text-sm">
            close
          </button>
        </div>

        <div className="text-sm text-muted mb-1">Order {payload.order_id}</div>
        <div className="font-mono text-2xl text-signal mb-4">
          ₹{(payload.amount_paise / 100).toFixed(0)}
        </div>

        {payload.is_mock ? (
          <>
            <div className="text-xs text-caution border border-caution/40 bg-caution/10 rounded-lg px-3 py-2 mb-4">
              SIMULATED CHECKOUT — no Razorpay test keys configured. This is not a
              real Razorpay transaction.
            </div>
            <div className="flex flex-col gap-2">
              <button
                disabled={busy}
                onClick={() => simulate("success")}
                className="bg-signal text-ink rounded-full py-2 text-sm font-medium disabled:opacity-50"
              >
                Simulate successful payment
              </button>
              <button
                disabled={busy}
                onClick={() => simulate("failure")}
                className="border border-danger/50 text-danger rounded-full py-2 text-sm font-medium disabled:opacity-50"
              >
                Simulate failed payment
              </button>
            </div>
          </>
        ) : (
          <button
            disabled={busy}
            onClick={launchRealRazorpay}
            className="bg-signal text-ink rounded-full py-2 w-full text-sm font-medium disabled:opacity-50"
          >
            Pay with Razorpay (Test Mode)
          </button>
        )}
      </div>
    </div>
  );
}
