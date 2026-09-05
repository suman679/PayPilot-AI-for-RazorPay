import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";
import MessageBubble from "../components/MessageBubble.jsx";
import CartSidebar from "../components/CartSidebar.jsx";
import CheckoutModal from "../components/CheckoutModal.jsx";

const USER_ID = "user_demo";

const DEMO_SCENARIOS = [
  { label: "A · Successful purchase", msg: "I need black running shoes under 3000" },
  { label: "B · Upsell flow", msg: "I need running shoes under 3000" },
  { label: "C · Payment failure", msg: "I need running shoes under 3000" },
  { label: "D · Over spending limit", msg: "show me a running watch" },
  { label: "E · Duplicate retry protection", msg: "I need running shoes under 3000" },
];

export default function ShoppingPage() {
  const [sessionId, setSessionId] = useState(null);
  const [orderId, setOrderId] = useState(null);
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text:
        "Hi! I'm the PayPilot shopping agent. Tell me what you're looking for - " +
        "e.g. \"I need black running shoes under ₹3000 for daily running.\"",
    },
  ]);
  const [cart, setCart] = useState(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [checkoutPayload, setCheckoutPayload] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async (text) => {
    if (!text.trim() || busy) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const res = await api.sendChat({ session_id: sessionId, user_id: USER_ID, message: text });
      setSessionId(res.session_id);
      if (res.order_id) setOrderId(res.order_id);
      setMessages((m) => [...m, ...res.messages]);
      const last = res.messages[res.messages.length - 1];
      if (last?.cart) setCart(last.cart);
      if (last?.ui_action === "SHOW_CHECKOUT_GATE") {
        // gate is conversational (agent asked "would you like to proceed?");
        // no modal yet - waits for the user's explicit "yes" in chat.
      }
      if (last?.ui_action === "LAUNCH_PAYMENT") {
        setCheckoutPayload(last.checkout_payload);
      }
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", text: `Something went wrong: ${e.message}` }]);
    } finally {
      setBusy(false);
    }
  };

  const handlePaymentResult = (result) => {
    setCheckoutPayload(null);
    const text = result.success
      ? `✅ ${result.message} Order status: ${result.order_status}.`
      : `⚠️ ${result.message}` +
        (result.retries_remaining > 0
          ? ` You have ${result.retries_remaining} retry remaining. Type "retry" to try again.`
          : "");
    setMessages((m) => [...m, { role: "assistant", text }]);

    if (result.retries_remaining > 0 && !result.success) {
      // mark session awaiting retry so the chat understands "retry"
      api.sendChat({ session_id: sessionId, user_id: USER_ID, message: "__mark_awaiting_retry__" }).catch(() => {});
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2">
          {DEMO_SCENARIOS.map((s) => (
            <button
              key={s.label}
              onClick={() => send(s.msg)}
              className="text-xs border border-line rounded-full px-3 py-1.5 text-muted hover:text-paper hover:border-signal transition-colors"
            >
              {s.label}
            </button>
          ))}
        </div>

        <div
          ref={scrollRef}
          className="border border-line rounded-2xl p-4 h-[60vh] overflow-y-auto ledger-scroll flex flex-col gap-4"
        >
          {messages.map((m, i) => (
            <MessageBubble key={i} message={m} />
          ))}
          {busy && <div className="text-xs text-muted">PayPilot is thinking…</div>}
        </div>

        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder='Try: "add it", "yes", "checkout"...'
            className="flex-1 bg-ledger border border-line rounded-full px-4 py-3 text-sm focus:outline-none focus:border-signal"
          />
          <button
            type="submit"
            className="bg-signal text-ink rounded-full px-5 py-3 text-sm font-medium disabled:opacity-50"
            disabled={busy}
          >
            Send
          </button>
        </form>

        {orderId && (
          <div className="text-xs text-muted">
            Order <span className="font-mono">{orderId}</span> ·{" "}
            <Link to={`/orders/${orderId}`} className="text-signal underline">
              view audit trail
            </Link>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-4">
        <CartSidebar cart={cart} />
        <div className="border border-line rounded-xl p-4 text-xs text-muted leading-relaxed">
          <div className="text-paper font-medium mb-1">Safety model</div>
          Every payment requires your explicit confirmation, is capped at a policy
          spending limit, and is recorded to an immutable audit trail. The agent
          can suggest — only the backend policy engine can allow a charge.
        </div>
      </div>

      <CheckoutModal
        payload={checkoutPayload}
        onResult={handlePaymentResult}
        onClose={() => setCheckoutPayload(null)}
      />
    </div>
  );
}
