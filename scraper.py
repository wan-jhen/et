import json
import os
import re
import time
import urllib.request
from datetime import datetime
from urllib.parse import quote
from bs4 import BeautifulSoup

DATA_FILE = "data.json"

CATEGORIES = {
    "手機": "東森購物 手機殼 充電線",
    "電腦3C": "東森購物 滑鼠 鍵盤",
    "家電數位": "東森購物 吹風機 循環扇",
    "食品飲料": "東森購物 咖啡 零食",
    "美妝保養": "東森購物 面膜 化妝水",
    "保健醫療": "東森購物 葉黃素 益生菌",
    "寵物": "東森購物 貓砂 飼料",
    "母嬰": "東森購物 濕紙巾 尿布",
    "餐廚用品": "東森購物 保溫杯 不沾鍋",
    "生活日用": "東森購物 衛生紙 洗衣精"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9"
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

def fetch_from_feebee(query, cat_name):
    items = []
    url = f"https://feebee.com.tw{quote(query)}/?shop=etmall"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        for li in soup.select("li.items, div.product_item, li[data-pid]"):
            title_el = li.select_one("h3, h2, .items_name, a[title]")
            price_el = li.select_one(".price, .items_price, span[class*='price']")
            link_el = li.select_one("a[href]")
            img_el = li.select_one("img")
            if not title_el or not price_el or not link_el:
                continue
            name = title_el.get_text(strip=True)
            price_nums = re.findall(r"\d+", price_el.get_text().replace(",", ""))
            if not name or not price_nums:
                continue
            curr = int(price_nums[0])
            if curr <= 0 or curr > 300000:
                continue
            href = link_el.get("href", "")
            if href.startswith("/"):
                href = "https://feebee.com.tw" + href
            pid_match = re.search(r"(\d{6,})", href + name)
            pid = pid_match.group(1) if pid_match else str(abs(hash(name)))[:8]
            img = ""
            if img_el:
                img = img_el.get("data-src") or img_el.get("src") or ""
                if img.startswith("//"):
                    img = "https:" + img
            orig = int(round(curr * 1.35))
            items.append({
                "id": pid,
                "category": cat_name,
                "name": name,
                "original_price": orig,
                "price": curr,
                "discount": round((1 - curr / orig) * 100),
                "image": img,
                "url": href,
                "in_stock": True
            })
    except Exception as e:
        print(f"[{cat_name}] 錯誤: {e}")
    return items

def main():
    old_prices, old_items = load_old_data()
    all_items = []
    seen_ids = set()

    for cat_name, kw in CATEGORIES.items():
        fetched = fetch_from_feebee(kw, cat_name)
        print(f"[{cat_name}] 取得 {len(fetched)} 筆")
        for item in fetched:
            if item["id"] in seen_ids:
                continue
            seen_ids.add(item["id"])
            prev = old_prices.get(item["id"])
            diff = (item["price"] - prev) if prev is not None else 0
            pct = round((diff / prev) * 100, 1) if (prev and diff != 0) else 0
            item["price_change"] = diff
            item["price_change_pct"] = pct
            all_items.append(item)
        time.sleep(1)

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
    main()
