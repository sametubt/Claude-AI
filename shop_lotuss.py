"""
Lotus's Thailand Grocery Shopping Bot
======================================
Setup (one-time):
    pip install playwright
    playwright install chromium

Run:
    python shop_lotuss.py

The script opens a real browser, searches each item on Lotus's,
adds it to cart, then pauses for your confirmation before you buy.
"""

import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

STORE_URL = "https://www.lotus.co.th/en"

# ── Edit your shopping list here ────────────────────────────────
# Each item: name (used for search), qty (default 1), note (optional label)
SHOPPING_LIST = [
    {"name": "tissue large pack",           "qty": 1,  "note": "bulk multi-roll pack"},
    {"name": "tipco orange juice",          "qty": 1,  "note": "1L bottle"},
    {"name": "pork shoulder",               "qty": 2,  "note": "kg — for pulled pork"},
    {"name": "flour tortilla large",        "qty": 2,  "note": "pack of 8, need 16 total"},
    {"name": "jasmine rice",                "qty": 1,  "note": "1kg"},
    {"name": "black beans canned",          "qty": 3,  "note": "400g cans"},
    {"name": "shredded mozzarella cheese",  "qty": 1,  "note": "500g"},
    {"name": "sour cream",                  "qty": 1,  "note": "250g"},
    {"name": "salsa",                       "qty": 2,  "note": "jars"},
    {"name": "romaine lettuce",             "qty": 1,  "note": "head"},
    {"name": "tomato",                      "qty": 5},
    {"name": "avocado",                     "qty": 5},
    {"name": "pickled jalapenos",           "qty": 1,  "note": "jar"},
    {"name": "lime",                        "qty": 6},
    {"name": "onion",                       "qty": 2},
    {"name": "bell pepper",                 "qty": 3,  "note": "mixed colors"},
    {"name": "sweet corn canned",           "qty": 2},
    {"name": "smoked paprika",              "qty": 1},
    {"name": "cumin powder",                "qty": 1},
    {"name": "chili powder",                "qty": 1},
    {"name": "garlic powder",               "qty": 1},
    {"name": "brown sugar",                 "qty": 1},
    {"name": "bbq sauce",                   "qty": 1},
    {"name": "cooking oil",                 "qty": 1,  "note": "Thai brand preferred"},
]
# ────────────────────────────────────────────────────────────────

ADDED = []
FLAGS = []

POPUP_SELECTORS = [
    "button:has-text('Accept')",
    "button:has-text('ยอมรับ')",
    "button:has-text('Close')",
    "button:has-text('ปิด')",
    "button:has-text('ไม่สนใจ')",
    "[aria-label='Close']",
    "[aria-label='ปิด']",
    ".modal-close",
    ".popup-close",
    ".close-btn",
]

ADD_TO_CART_SELECTORS = [
    "button:has-text('Add to Cart')",
    "button:has-text('Add to cart')",
    "button:has-text('เพิ่มลงตะกร้า')",
    "[data-testid='add-to-cart-button']",
    "[data-testid='add-to-cart']",
    ".add-to-cart-btn",
]

PRODUCT_CARD_SELECTORS = [
    "[data-testid='product-card']",
    ".product-card",
    ".plp-product-card",
    ".product-item",
    "article.product",
]

SEARCH_INPUT_SELECTORS = [
    "input[type='search']",
    "input[placeholder*='ค้นหา']",
    "input[placeholder*='Search']",
    "input[placeholder*='search']",
    "#search-input",
    ".search-input",
]


async def dismiss_popups(page):
    for sel in POPUP_SELECTORS:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=1000):
                await btn.click()
                await page.wait_for_timeout(400)
        except PlaywrightTimeout:
            pass


async def get_first_visible(page, selectors, timeout=4000):
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=timeout):
                return el
        except PlaywrightTimeout:
            continue
    return None


async def set_quantity(page, qty):
    if qty <= 1:
        return
    # Try numeric input field first
    try:
        qty_input = page.locator("input[type='number'], .quantity-input, input[name='quantity']").first
        if await qty_input.is_visible(timeout=1500):
            await qty_input.triple_click()
            await qty_input.fill(str(qty))
            return
    except PlaywrightTimeout:
        pass
    # Fall back to clicking + button
    try:
        plus_btn = page.locator("button:has-text('+'), [aria-label='Increase'], [data-testid='increase-qty']").first
        for _ in range(qty - 1):
            await plus_btn.click()
            await page.wait_for_timeout(250)
    except PlaywrightTimeout:
        pass


async def search_and_add(page, item):
    name = item["name"]
    qty  = item.get("qty", 1)
    note = item.get("note", "")

    print(f"\n  Searching: {name}  (qty: {qty})")

    try:
        # Search
        search_box = await get_first_visible(page, SEARCH_INPUT_SELECTORS)
        if not search_box:
            raise Exception("Search box not found on page")

        await search_box.click()
        await search_box.fill("")
        await search_box.type(name, delay=60)
        await search_box.press("Enter")
        await page.wait_for_load_state("networkidle", timeout=12000)
        await dismiss_popups(page)

        # Pick first product card
        product = await get_first_visible(page, PRODUCT_CARD_SELECTORS, timeout=6000)
        if not product:
            raise Exception("No products found in search results")

        # Try to read product name
        try:
            product_name = await product.locator("h3, h2, .product-name, .product-title, [data-testid='product-name']").first.inner_text(timeout=2000)
            product_name = product_name.strip()
        except Exception:
            product_name = name  # fallback to search term

        print(f"    Found: {product_name}")

        # Click through to product detail
        await product.click()
        await page.wait_for_load_state("networkidle", timeout=10000)
        await dismiss_popups(page)

        # Set quantity
        await set_quantity(page, qty)

        # Add to cart
        atc = await get_first_visible(page, ADD_TO_CART_SELECTORS, timeout=5000)
        if not atc:
            raise Exception("Add to cart button not found")

        await atc.click()
        await page.wait_for_timeout(1200)
        await dismiss_popups(page)

        ADDED.append({
            "name": name,
            "qty": qty,
            "found_as": product_name,
            "note": note,
        })
        print(f"    Added to cart")

    except Exception as e:
        FLAGS.append({"name": name, "qty": qty, "reason": str(e), "note": note})
        print(f"    FLAGGED: {e}")

    # Return to homepage for next search
    await page.goto(STORE_URL, wait_until="networkidle")
    await dismiss_popups(page)


async def apply_promo(page):
    promo_selectors = [
        "input[placeholder*='promo']",
        "input[placeholder*='coupon']",
        "input[placeholder*='โปร']",
        "input[placeholder*='คูปอง']",
        "#promo-code-input",
    ]
    for sel in promo_selectors:
        try:
            field = page.locator(sel).first
            if await field.is_visible(timeout=2000):
                print("\n  Promo code field found — no code available, leaving blank.")
                return
        except PlaywrightTimeout:
            continue
    print("\n  No promo code field visible at checkout.")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=250)
        ctx = await browser.new_context(
            locale="en-US",
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()

        print("Opening Lotus's Thailand...")
        print("=" * 52)
        await page.goto(STORE_URL, wait_until="networkidle")
        await dismiss_popups(page)

        for item in SHOPPING_LIST:
            await search_and_add(page, item)

        # Navigate to cart and check promo
        print("\nNavigating to cart...")
        await page.goto("https://www.lotus.co.th/en/cart", wait_until="networkidle")
        await dismiss_popups(page)
        await apply_promo(page)

        # Cart summary
        print("\n" + "=" * 52)
        print("CART SUMMARY — Lotus's Thailand")
        print("=" * 52)

        print(f"\nAdded ({len(ADDED)} items):")
        for i in ADDED:
            suffix = f"  [{i['note']}]" if i.get("note") else ""
            print(f"  + {i['name']} x{i['qty']}  ->  {i['found_as']}{suffix}")

        if FLAGS:
            print(f"\nFlagged — NOT added ({len(FLAGS)} items):")
            for f in FLAGS:
                suffix = f"  [{f['note']}]" if f.get("note") else ""
                print(f"  ! {f['name']} x{f['qty']}  ->  {f['reason']}{suffix}")

        print("\n" + "=" * 52)
        print("Review your cart in the browser above.")
        input("Press ENTER when done (browser will close)...")

        await browser.close()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
