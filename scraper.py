import json
import os
import re
from datetime import datetime
from urllib.parse import quote
from playwright.sync_api import sync_playwright

DATA_FILE = "data.json"

CATEGORIES = {
    "手機": "手機殼",
    "電腦3C": "滑鼠",
    "家電數位": "吹風機",
    "食品飲料": "咖啡",
    "美妝保養": "面膜",
    "保健醫療": "葉黃素",
    "寵物": "貓砂",
    "母嬰": "濕紙巾",
    "餐廚用品": "保溫杯",
    "生活日用": "衛生紙"
}

def load_old_data():
    if not os.path.exists(DATA_FILE):
        return {}, []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = data.get("items", [])
            return {str(x["id"]): x["price"] for x in items}, items
    except Exception:
        return {}, []

def run_scraper():
    old_prices, old_items = load_old_data()
    all_items = []
    seen_ids = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="zh-TW"
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        for cat_name, keyword in CATEGORIES.items():
            url = f"https://etmall.com.tw{quote(keyword)}"
            try:
                page.goto(url, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(3000)

                title = page.title()
                print(f"[{cat_name}] 網頁標題: {title}")

                pickup = page.locator("label:has-text('超商取貨'), span:has-text('超商取貨'), a:has-text('超商取貨')").first
                if pickup.count() > 0 and pickup.is_visible():
                    pickup.click()
                    page.wait_for_timeout(3000)

                for _ in range(3):
                    page.mouse.wheel(0, 1200)
                    page.wait_for_timeout(800)

                products = page.evaluate("""() => {
                    const results = [];
                    const links = document.querySelectorAll('a[href*="/i/"]');
                    const seen = new Set();
                    links.forEach(a => {
                        const m = a.href.match(/\\/i\\/(\\d+)/);
                        if (!m) return;
                        const id = m[1];
                        if (seen.has(id)) return;
                        let card = a.parentElement;
                        for (let i = 0; i < 5; i++) {
                            if (card && card.innerText && card.innerText.includes('$')) break;
                            if (card) card = card.parentElement;
                        }
                        if (!card) return;
                        const text = card.innerText || '';
                        const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);
                        const name = lines.find(l => l.length > 5 && !l.includes('$') && !l.includes('折') && !l.includes('超商')) || '';
                        const prices = (text.match(/\\$\\s*([\\d,]+)/g) || [])
                            .map(x => parseInt(x.replace(/[^\\d]/g, ''), 10))
                            .filter(n => n > 0 && n < 500000);
                        if (!name || prices.length === 0) return;
                        seen.add(id);
                        const currPrice = Math.min(...prices);
                        const origPrice = Math.max(...prices);
                        const img = card.querySelector('img');
                        let imgSrc = img ? (img.getAttribute('src') || img.getAttribute('data-src') || '') : '';
                        if (imgSrc.startsWith('//')) imgSrc = 'https:' + imgSrc;
                        results.push({
                            id: id,
                            name: name,
                            price: currPrice,
                            original_price: origPrice > currPrice ? origPrice : Math.round(currPrice * 1.25),
                            image: imgSrc,
                            url: 'https://etmall.com.tw' + id
                        });
                    });
                    return results;
                }""")

                print(f"[{cat_name}] 抓到 {len(products)} 筆")
                for item in products:
                    if item["id"] in seen_ids:
                        continue
                    seen_ids.add(item["id"])
                    orig = item["original_price"]
                    curr = item["price"]
                    discount = round((1 - curr / orig) * 100) if orig > curr else 0
                    prev = old_prices.get(item["id"])
                    diff = (curr - prev) if prev is not None else 0
                    pct = round((diff / prev) * 100, 1) if (prev and diff != 0) else 0

                    all_items.append({
                        "id": item["id"],
                        "category": cat_name,
                        "name": item["name"],
                        "original_price": orig,
                        "price": curr,
                        "discount": discount,
                        "price_change": diff,
                        "price_change_pct": pct,
                        "image": item["image"],
                        "url": item["url"],
                        "in_stock": True
                    })
            except Exception as e:
                print(f"[{cat_name}] 錯誤: {e}")

        browser.close()

    if not all_items and old_items:
        all_items = old_items
    else:
        all_items.sort(key=lambda x: x["discount"], reverse=True)

    output = {
        "updated_at": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "total": len(all_items),
        "items": all_items
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"總計寫入 {len(all_items)} 筆商品")

if __name__ == "__main__":
    run_scraper()
