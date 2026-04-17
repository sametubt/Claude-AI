"""
Grocery Shopping Agent — Claude Computer Use
=============================================
Setup (one-time):
    pip install anthropic pillow pyautogui
    export ANTHROPIC_API_KEY=your-key-here

Run:
    1. Open Chrome and navigate to lotus.co.th
    2. python grocery_computer_use.py
    3. Press ENTER — walk away

Claude sees your screen, shops the list, stops before checkout.
"""

import os
import base64
import io
import time
import anthropic
import pyautogui
from PIL import ImageGrab

# ── Config ──────────────────────────────────────────────────────
MODEL = "claude-sonnet-4-6"   # change to claude-opus-4-7 for best accuracy
# ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a grocery shopping agent for someone in Bangkok, Thailand.
You are viewing their screen — Chrome is open on lotus.co.th.

Rules (follow without exception):
- Never ask the user questions. Make best-judgment calls and keep moving.
- Do not pause to confirm each item. Add it and move straight to the next.
- Dismiss all popups, cookie banners, login prompts immediately when they appear.
- For each item: search → pick best match → set quantity → add to cart → next item.
- If an item is not found after 1 search attempt, note it as flagged and move on.
- Prefer Thai brands when quality is comparable.
- STOP at the cart page. Do not proceed to checkout under any circumstances.

Substitution logic (silent — never ask):
- Pork shoulder not found → try pork neck or pork collar
- Shredded cheese not found → buy block cheese, flag for user to shred
- Sour cream not found → plain full-fat Greek yogurt
- Jalapeños (fresh) not found → pickled jalapeños jar
- Salsa not found → flag it, skip
- Any spice not found → flag it, skip
- Any fresh produce not found → flag it, skip

When all items are done:
- Navigate to the cart page
- Take a screenshot
- Print a summary:
    ADDED: [item] x[qty] → found as [product name]
    FLAGGED: [item] → [reason]
- Then stop and wait for user confirmation."""


def screenshot() -> str:
    img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def run_action(action: dict) -> str | None:
    t = action.get("type")

    if t == "screenshot":
        return screenshot()

    elif t == "left_click":
        pyautogui.click(action["coordinate"][0], action["coordinate"][1])
        time.sleep(0.6)

    elif t == "double_click":
        pyautogui.doubleClick(action["coordinate"][0], action["coordinate"][1])
        time.sleep(0.6)

    elif t == "right_click":
        pyautogui.rightClick(action["coordinate"][0], action["coordinate"][1])
        time.sleep(0.4)

    elif t == "mouse_move":
        pyautogui.moveTo(action["coordinate"][0], action["coordinate"][1], duration=0.2)

    elif t == "type":
        pyautogui.typewrite(action["text"], interval=0.04)

    elif t == "key":
        pyautogui.press(action["key"])
        time.sleep(0.3)

    elif t == "scroll":
        amt = action.get("coordinate", [0, 0])
        direction = action.get("direction", "down")
        clicks = action.get("clicks", 3)
        pyautogui.scroll(-clicks if direction == "down" else clicks, x=amt[0], y=amt[1])
        time.sleep(0.3)

    return None


def make_screenshot_result(tool_use_id: str) -> dict:
    time.sleep(0.8)
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": [{
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": screenshot()},
        }],
    }


def run(task: str):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY environment variable first.")

    client = anthropic.Anthropic(api_key=api_key)
    w, h = pyautogui.size()

    tools = [{
        "type": "computer_20241022",
        "name": "computer",
        "display_width_px": w,
        "display_height_px": h,
        "display_number": 1,
    }]

    messages = [{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": screenshot()},
            },
            {"type": "text", "text": task},
        ],
    }]

    print("Claude is shopping. Check back when done.\n" + "=" * 52)
    step = 0

    while True:
        step += 1
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
            betas=["computer-use-2024-10-22"],
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print("\n" + "=" * 52)
                    print(block.text)
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use" or block.name != "computer":
                continue

            action = block.input
            label = str(action.get("coordinate", action.get("text", "")))[:60]
            print(f"  [{step}] {action.get('type')}  {label}")

            result = run_action(action)
            if result:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": [{
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": result},
                    }],
                })
            else:
                tool_results.append(make_screenshot_result(block.id))

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    print("\nDone. Review cart in browser and confirm purchase.")


# ── Edit your shopping list here ────────────────────────────────
SHOPPING_LIST = """
Shop for these items on lotus.co.th:

1.  Tissue large bulk pack x1
2.  Tipco orange juice 1L x1
3.  Pork shoulder or pork neck x2kg
4.  Large flour tortillas x16 (2 packs of 8)
5.  Jasmine rice x1kg
6.  Black beans canned x3
7.  Shredded mozzarella or cheddar cheese x500g
8.  Sour cream x250g
9.  Salsa x2 jars
10. Romaine or iceberg lettuce x1 head
11. Tomatoes x5
12. Avocados x5
13. Pickled jalapeños x1 jar
14. Limes x6
15. Onions x2
16. Bell peppers mixed colors x3
17. Corn canned x2
18. Smoked paprika x1
19. Cumin powder x1
20. Chili powder x1
21. Garlic powder x1
22. Brown sugar x1
23. BBQ sauce x1
24. Cooking oil x1 (Thai brand preferred)

Start shopping now.
"""
# ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("Grocery Agent — Claude Computer Use")
    print("Make sure Chrome is open on lotus.co.th")
    input("Press ENTER to start...")
    time.sleep(1)
    run(SHOPPING_LIST)
