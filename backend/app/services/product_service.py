from sqlalchemy.orm import Session

from app.models import Product


def search_products(
    db: Session,
    *,
    query: str | None = None,
    category: str | None = None,
    color: str | None = None,
    max_price: int | None = None,
    min_price: int | None = None,
    tags: list[str] | None = None,
    limit: int = 10,
) -> list[Product]:
    """Deterministic, filterable search over the real catalog table. The
    agent NEVER sees or invents products outside this function's output."""
    q = db.query(Product)
    if category:
        q = q.filter(Product.category.ilike(f"%{category}%"))
    if color:
        q = q.filter(Product.color.ilike(f"%{color}%"))
    if max_price is not None:
        q = q.filter(Product.price <= max_price)
    if min_price is not None:
        q = q.filter(Product.price >= min_price)
    q = q.filter(Product.stock > 0)

    results = q.all()

    if query:
        terms = [t.lower() for t in query.split() if t]
        def score(p: Product) -> int:
            haystack = " ".join([p.name, p.description, p.brand, p.category, " ".join(p.tags)]).lower()
            return sum(1 for t in terms if t in haystack)
        results = [p for p in results if score(p) > 0] or results
        results.sort(key=score, reverse=True)

    if tags:
        wanted = set(t.lower() for t in tags)
        results = [p for p in results if wanted & set(t.lower() for t in p.tags)] or results

    # rank by rating as a stable secondary sort
    results.sort(key=lambda p: p.rating, reverse=True)
    return results[:limit]


def get_product(db: Session, product_id: str) -> Product | None:
    return db.get(Product, product_id)


def get_upsell_candidates(db: Session, product: Product) -> list[Product]:
    ids = product.upsell_products or []
    if not ids:
        return []
    return db.query(Product).filter(Product.id.in_(ids), Product.stock > 0).all()


def get_cross_sell_candidates(db: Session, product: Product) -> list[Product]:
    ids = product.cross_sell_products or []
    if not ids:
        return []
    return db.query(Product).filter(Product.id.in_(ids), Product.stock > 0).all()


def explain_recommendation(product: Product, *, budget: int | None, color: str | None, category_hint: str | None) -> list[str]:
    """Human-readable, non-chain-of-thought explanation (section 22)."""
    bullets = []
    if budget is not None:
        bullets.append(f"Price ₹{product.price} is within your ₹{budget} budget")
    if category_hint:
        bullets.append(f"Matches your requirement for {category_hint}")
    if color and color.lower() in (product.color or "").lower():
        bullets.append(f"{product.color.capitalize()} color matches your request")
    bullets.append("Currently in stock" if product.stock > 0 else "Currently out of stock")
    if product.rating >= 4.5:
        bullets.append(f"Highly rated ({product.rating}/5)")
    return bullets
