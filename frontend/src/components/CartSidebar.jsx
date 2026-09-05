export default function CartSidebar({ cart }) {
  if (!cart || cart.items.length === 0) {
    return (
      <div className="border border-line rounded-xl p-5 text-sm text-muted">
        Your cart is empty. Ask the agent for something you need.
      </div>
    );
  }

  return (
    <div className="border border-line rounded-xl p-5 flex flex-col gap-3">
      <div className="text-xs uppercase tracking-wide text-muted">Cart</div>
      <div className="flex flex-col gap-2">
        {cart.items.map((item) => (
          <div key={item.id} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <span>{item.product.image_emoji}</span>
              <div>
                <div className="leading-tight">{item.product.name}</div>
                {item.is_upsell && (
                  <span className="text-[10px] text-caution uppercase tracking-wide">
                    upsell · qty {item.quantity}
                  </span>
                )}
                {!item.is_upsell && (
                  <span className="text-[10px] text-muted">qty {item.quantity}</span>
                )}
              </div>
            </div>
            <div className="font-mono text-signal">₹{item.line_total}</div>
          </div>
        ))}
      </div>
      <div className="border-t border-line pt-3 flex flex-col gap-1 text-sm font-mono">
        <div className="flex justify-between text-muted">
          <span>Subtotal</span>
          <span>₹{cart.subtotal}</span>
        </div>
        {cart.upsell_amount > 0 && (
          <div className="flex justify-between text-caution">
            <span>incl. upsell</span>
            <span>₹{cart.upsell_amount}</span>
          </div>
        )}
        <div className="flex justify-between text-paper text-base font-semibold pt-1">
          <span>Total</span>
          <span>₹{cart.total}</span>
        </div>
      </div>
    </div>
  );
}
