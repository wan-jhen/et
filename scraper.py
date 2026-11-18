import json
import os
import time
from datetime import datetime
from urllib.parse import quote
from playwright.sync_api import sync_playwright

DATA_FILE = "data.json"

CATEGORIES = {
    "手機": "手機殼 充電線",
    "電腦3C": "滑鼠 鍵盤 隨身碟",
    "家電數位": "循環扇 吹風機 除濕機",
    "食品飲料": "咖啡 零食 泡麵",
    "美妝保養": "面膜 化妝水 防曬",
    "保健醫療": "葉黃素 益生菌 魚油",
    "寵物": "貓砂 飼料 肉泥",
    "母嬰": "濕紙巾 尿布 奶瓶",
    "餐廚用品": "保溫杯 餐盒 不沾鍋",
    "生活日用": "衛生紙 洗衣精 收納箱"
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
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()

        for cat_name, keyword in CATEGORIES.items():
            url = f"https://etmall.com.tw{quote(keyword)}"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)

                pickup_btn = page.locator("text=超商取貨").first
                if pickup_btn.is_visible():
                    pickup_btn.click()
                    page.wait_for_timeout(2500)

                for _ in range(3):
                    page.mouse.wheel(0, 1500)
                    page.wait_for_timeout(1000)

                products = page.evaluate("""() => {
                    const results = [];
                    const links = document.querySelectorAll('a[href*="/i/"]');
                    const seen = new Set();
                    links.forEach(a => {
                        const match = a.href.match(/\\/i\\/(\\d+)/);
                        if (!match) return;
                        const id = match[1];
                        if (seen.has(id)) return;
                        const card = a.closest('li, div[class*="product"], div[class*="item"]') || a.parentElement;
                        const text = card ? card.innerText : a.innerText;
                        const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);
                        const name = lines.find(l => l.length > 6 && !l.includes('$') && !l.includes('折')) || '';
                        const prices = (text.match(/\\$\\s*([\\d,]+)/g) || []).map(p => parseInt(p.replace(/[^\\d]/g, ''), 10)).filter(n => n > 0);
                        if (!name || prices.length === 0) return;
                        seen.add(id);
                        const currPrice = Math.min(...prices);
                        const origPrice = Math.max(...prices);
                        const img = card ? card.querySelector('img') : null;
                        results.push({
                            id: id,
                            name: name,
                            price: currPrice,
                            original_price: origPrice > currPrice ? origPrice : Math.round(currPrice * 1.2),
                            image: img ? (img.src || img.getAttribute('data-src') || '') : '',
                            url: 'https://etmall.com.tw' + id
                        });
                    });
                    return results;
                }""")

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
                print(f"[{cat_name}] 抓到 {len(products)} 筆")
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

    print(f"完成！共寫入 {len(all_items)} 筆商品")

if __name__ == "__main__":
    run_scraper()
