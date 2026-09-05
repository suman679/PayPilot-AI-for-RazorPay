"""Seed script: run with `python -m app.seed` to populate the catalog and a
demo user. Safe to re-run (idempotent upsert by product id)."""
from app.database import Base, SessionLocal, engine
from app.models import Product, User

CATALOG = [
    dict(id="SHOE_101", name="Stride Pro Running Shoes", category="footwear", price=2799,
         brand="Stride", color="black", sizes=["6", "7", "8", "9", "10"], stock=42,
         tags=["running", "daily", "black", "budget"], rating=4.4, image_emoji="\U0001F45F",
         description="Lightweight daily trainer with breathable mesh upper, built for road running.",
         features=["Breathable mesh", "Cushioned midsole", "Reflective trim"],
         upsell_products=["SOCK_201"], cross_sell_products=["INSOLE_301", "BOTTLE_401"]),
    dict(id="SHOE_102", name="AeroFlex Runner", category="footwear", price=2999,
         brand="AeroFlex", color="black", sizes=["6", "7", "8", "9", "10", "11"], stock=25,
         tags=["running", "daily", "black", "budget"], rating=4.6, image_emoji="\U0001F45F",
         description="Our best-rated budget running shoe - responsive foam, black colourway, built for daily mileage.",
         features=["Responsive foam sole", "Breathable knit", "Durable rubber outsole"],
         upsell_products=["SOCK_201"], cross_sell_products=["INSOLE_301"]),
    dict(id="SHOE_103", name="TrailBlaze GTX", category="footwear", price=4499,
         brand="TrailBlaze", color="grey", sizes=["7", "8", "9", "10"], stock=15,
         tags=["running", "trail", "waterproof"], rating=4.7, image_emoji="\U0001F45F",
         description="Waterproof trail running shoe with aggressive grip for off-road daily runs.",
         features=["Waterproof membrane", "Aggressive lug grip", "Rock plate"],
         upsell_products=["SOCK_201"], cross_sell_products=["BOTTLE_401"]),
    dict(id="SHOE_104", name="Velocity X Racer", category="footwear", price=6999,
         brand="Velocity", color="red", sizes=["8", "9", "10"], stock=8,
         tags=["running", "race", "performance"], rating=4.8, image_emoji="\U0001F45F",
         description="Carbon-plated racing shoe for competitive 5K-marathon distances.",
         features=["Carbon fibre plate", "PEBA foam", "Racing fit"],
         upsell_products=["SOCK_201"], cross_sell_products=[]),
    dict(id="SOCK_201", name="CloudStep Running Socks (2-pack)", category="accessories", price=299,
         brand="CloudStep", color="white", sizes=["M", "L"], stock=120,
         tags=["running", "socks", "accessory"], rating=4.5, image_emoji="\U0001F9E6",
         description="Moisture-wicking cushioned running socks, commonly purchased with running shoes.",
         features=["Moisture-wicking", "Arch support", "Blister-resistant seam"],
         upsell_products=[], cross_sell_products=[]),
    dict(id="INSOLE_301", name="ComfortFit Gel Insoles", category="accessories", price=499,
         brand="ComfortFit", color="grey", sizes=["S", "M", "L"], stock=60,
         tags=["running", "comfort", "accessory"], rating=4.2, image_emoji="\U0001FA79",
         description="Gel cushioning insoles that improve shock absorption in any running shoe.",
         features=["Gel cushioning", "Trim-to-fit"],
         upsell_products=[], cross_sell_products=[]),
    dict(id="BOTTLE_401", name="HydroRun 500ml Sports Bottle", category="accessories", price=349,
         brand="HydroRun", color="blue", sizes=[], stock=80,
         tags=["running", "hydration", "accessory"], rating=4.3, image_emoji="\U0001F9C3",
         description="Leak-proof soft-flask sports bottle sized for daily training runs.",
         features=["Leak-proof cap", "BPA-free", "Compact 500ml"],
         upsell_products=[], cross_sell_products=[]),
    dict(id="TSHIRT_501", name="DryFit Running Tee", category="apparel", price=899,
         brand="DryFit", color="black", sizes=["S", "M", "L", "XL"], stock=50,
         tags=["running", "apparel", "black"], rating=4.1, image_emoji="\U0001F455",
         description="Quick-dry breathable running t-shirt for daily training.",
         features=["Quick-dry fabric", "Flatlock seams"],
         upsell_products=[], cross_sell_products=[]),
    dict(id="WATCH_601", name="PulseTrack GPS Running Watch", category="electronics", price=8999,
         brand="PulseTrack", color="black", sizes=[], stock=12,
         tags=["running", "electronics", "performance"], rating=4.6, image_emoji="\u231A",
         description="GPS running watch with heart-rate tracking - above typical daily-runner budget.",
         features=["Built-in GPS", "Heart-rate sensor", "7-day battery"],
         upsell_products=[], cross_sell_products=[]),
    dict(id="JACKET_701", name="StormShield Running Jacket", category="apparel", price=3499,
         brand="StormShield", color="black", sizes=["M", "L", "XL"], stock=20,
         tags=["running", "apparel", "weather"], rating=4.3, image_emoji="\U0001F9E5",
         description="Water-resistant lightweight jacket for early-morning or rainy runs.",
         features=["Water-resistant", "Packable", "Reflective zips"],
         upsell_products=[], cross_sell_products=[]),
]


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for p in CATALOG:
            existing = db.get(Product, p["id"])
            if existing:
                for k, v in p.items():
                    setattr(existing, k, v)
            else:
                db.add(Product(**p))

        demo_user = db.query(User).filter(User.email == "demo@paypilot.ai").first()
        if not demo_user:
            db.add(User(id="user_demo", name="Demo Customer", email="demo@paypilot.ai"))

        db.commit()
        print(f"Seeded {len(CATALOG)} products and demo user.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
