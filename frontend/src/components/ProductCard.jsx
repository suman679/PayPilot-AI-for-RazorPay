export default function ProductCard({ product }) {
  return (
    <div className="min-w-[180px] max-w-[200px] bg-ledger border border-line rounded-xl p-3 flex flex-col gap-1">
      <div className="text-2xl">{product.image_emoji}</div>
      <div className="text-sm font-medium leading-snug">{product.name}</div>
      <div className="text-signal font-mono text-sm">₹{product.price}</div>
      <div className="text-xs text-muted">{product.brand} · {product.color}</div>
      <div className="text-xs text-muted">
        {product.stock > 0 ? `${product.stock} in stock` : "Out of stock"}
      </div>
    </div>
  );
}
