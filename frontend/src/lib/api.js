const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail;
    try {
      detail = await res.json();
    } catch {
      detail = { detail: res.statusText };
    }
    const err = new Error(typeof detail.detail === "string" ? detail.detail : JSON.stringify(detail.detail));
    err.payload = detail.detail;
    throw err;
  }
  return res.json();
}

export const api = {
  sendChat: (body) => request("/api/chat", { method: "POST", body: JSON.stringify(body) }),
  getCart: (sessionId, userId) =>
    request(`/api/cart?session_id=${sessionId}&user_id=${userId}`),
  createPayment: (orderId) =>
    request("/api/payments/create", { method: "POST", body: JSON.stringify({ order_id: orderId }) }),
  verifyPayment: (body) =>
    request("/api/payments/verify", { method: "POST", body: JSON.stringify(body) }),
  mockComplete: (orderId, razorpayOrderId, outcome) =>
    request("/api/payments/mock-complete", {
      method: "POST",
      body: JSON.stringify({
        order_id: orderId,
        razorpay_order_id: razorpayOrderId,
        razorpay_payment_id: `pay_SIM${Date.now()}`,
        razorpay_signature: outcome === "success" ? "SIMULATE_SUCCESS" : "SIMULATE_FAILURE",
      }),
    }),
  retryPayment: (orderId) =>
    request("/api/payments/retry", { method: "POST", body: JSON.stringify({ order_id: orderId }) }),
  getOrderDetail: (orderId) => request(`/api/orders/${orderId}/detail`),
  getAnalytics: () => request("/api/analytics"),
  runSimulation: (numSessions = 100) =>
    request(`/api/demo/simulate?num_sessions=${numSessions}`, { method: "POST" }),
  getLatestSimulation: () => request("/api/demo/simulate/latest"),
  health: () => request("/api/health"),
};
