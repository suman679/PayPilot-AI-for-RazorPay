import ProductCard from "./ProductCard.jsx";
import PolicyBadge from "./PolicyBadge.jsx";

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[85%] ${isUser ? "items-end" : "items-start"} flex flex-col gap-2`}>
        <div
          className={`rounded-2xl px-4 py-3 text-sm whitespace-pre-line leading-relaxed ${
            isUser ? "bg-signal text-ink" : "bg-ledger border border-line"
          }`}
        >
          {message.text}
        </div>

        {message.product_cards && message.product_cards.length > 0 && (
          <div className="flex gap-2 overflow-x-auto ledger-scroll pb-1">
            {message.product_cards.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
        )}

        {message.policy_notice && <PolicyBadge notice={message.policy_notice} />}
      </div>
    </div>
  );
}
