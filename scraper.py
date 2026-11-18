import requests
import json
import time
import os
from datetime import datetime

# 設定儲存的資料檔名（前端網頁會讀取這個檔案）
DATA_FILE = "data.json"

# 東森購物搜尋 API（這裡示範抓取指定關鍵字與篩選條件）
# 注意：電商 API 參數會隨改版變動，以下為通用模擬架構
SEARCH_API = "https://etmall.com.tw"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://etmall.com.tw"
}

# 要追蹤的東森分類與關鍵字（可自行增減）
CATEGORIES = {
    "保健醫療": "保健",
    "美妝保養": "美妝",
    "食品飲料": "美食",
    "電腦3C": "3C",
    "家電數位": "家電",
    "生活日用": "日用"
}

def load_old_prices():
    """讀取上一次抓到的價格，用來計算漲跌"""
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            old_data = json.load(f)
            return {item["id"]: item["price"] for item in old_data.get("items", [])}
    except Exception:
        return {}

def fetch_etmall_pickup_items(keyword, category_name, max_pages=3):
    """抓取東森購物「可超取」商品"""
    items = []
    for page in range(1, max_pages + 1):
        params = {
            "keyword": keyword,
            "page": page,
            "size": 40,
            "isPickup": "true"  # 篩選超商取貨（實際參數依東森最新網址列為準）
        }
        try:
            resp = requests.get(SEARCH_API, headers=HEADERS, params=params, timeout=10)
            if resp.status_code != 200:
                print(f"[{category_name}] 第 {page} 頁請求失敗，狀態碼：{resp.status_code}")
                break
            
            data = resp.json()
            product_list = data.get("SearchResult", {}).get("Products", [])
            if not product_list:
                break

            for p in product_list:
                # 確認是否支援超商取貨（依東森回傳欄位判斷）
                # 若 API 未過濾乾淨，可在此雙重檢查標籤
                prod_id = str(p.get("GDID", ""))
                title = p.get("GDNM", "").strip()
                orig_price = int(p.get("PRC", 0) or p.get("SalePrice", 0))
                curr_price = int(p.get("SalePrice", 0))
                img_url = p.get("ImageUrl", "")
                if img_url and not img_url.startswith("http"):
                    img_url = "https:" + img_url

                if orig_price > curr_price and curr_price > 0:
                    discount = round((1 - curr_price / orig_price) * 100)
                else:
                    discount = 0

                items.append({
                    "id": prod_id,
                    "category": category_name,
                    "name": title,
                    "original_price": orig_price,
                    "price": curr_price,
                    "discount": discount,
                    "image": img_url,
                    "url": f"https://etmall.com.twi/{prod_id}",
                    "in_stock": not p.get("IsSoldOut", False)
                })
            
            print(f"[{category_name}] 已完成第 {page} 頁，目前累計 {len(items)} 件")
            time.sleep(1.5)  # 禮貌性延遲，避免被網站封鎖 IP

        except Exception as e:
            print(f"[{category_name}] 發生錯誤：{e}")
            break
    return items

def main():
    print("開始更新東森購物可超取特價資料...")
    old_prices = load_old_prices()
    all_items = []
    seen_ids = set()

    for cat_name, kw in CATEGORIES.items():
        fetched = fetch_etmall_pickup_items(kw, cat_name, max_pages=5)
        for item in fetched:
            if item["id"] in seen_ids:
                continue
            seen_ids.add(item["id"])

            # 比對歷史價格
            prev_price = old_prices.get(item["id"])
            if prev_price is not None and prev_price != item["price"]:
                diff = item["price"] - prev_price
                pct = round((diff / prev_price) * 100, 1)
                item["price_change"] = diff
                item["price_change_pct"] = pct
            else:
                item["price_change"] = 0
                item["price_change_pct"] = 0

            all_items.append(item)

    output = {
        "updated_at": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "total": len(all_items),
        "items": all_items
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"更新完成！共寫入 {len(all_items)} 件商品至 {DATA_FILE}")

if __name__ == "__main__":
    main()
