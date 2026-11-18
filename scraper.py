"""
Çekmeköy şubesi ürün listesini tedarikçi sitesinden çeker ve public/data.json dosyasına yazar.
GitHub Actions tarafından saat başı çalıştırılır.

Çıktı biçimi (uygulamanın beklediği):
  B: [[marka adı, logo dosyası], ...]
  P: [[ürün id, ürün adı, resim dosyası, marka indeksi (-1 = diğer), fiyat (kuruş), eski fiyat (kuruş, varsa)], ...]
"""
import json, re, sys, time, os
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

BASE = "https://helaldunyamarketleri.com"
STOCK_URL = "/cekmekoy-subesi-urunleri?productTagId=157&pagenumber={}"
IMG_BASE = BASE + "/images/thumbs/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "data.json")
DELAY = 0.4          # istekler arası bekleme (siteye yük bindirmemek için)
MAX_PAGES = 60

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (compatible; CekmekoyKatalog/1.0)"


def get(path):
    for attempt in range(3):
        try:
            r = session.get(BASE + path, timeout=30)
            r.raise_for_status()
            time.sleep(DELAY)
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            print(f"  ! {path} ({attempt+1}. deneme): {e}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Sayfa alınamadı: {path}")


def img_src(img):
    if img is None:
        return ""
    for k in ("data-lazyloadsrc", "data-original", "src"):
        v = img.get(k) or ""
        if v and not v.startswith("data:"):
            return v
    return ""


def money(text):
    """'₺1.234,50' -> 123450 (kuruş)"""
    if not text:
        return 0
    t = re.sub(r"[^\d,]", "", text).replace(",", ".")
    try:
        return round(float(t) * 100)
    except ValueError:
        return 0


def product_items(soup):
    return soup.select(".product-item[data-productid]")


def scrape_stock():
    products = {}
    for page in range(1, MAX_PAGES + 1):
        soup = get(STOCK_URL.format(page))
        items = product_items(soup)
        new = 0
        for it in items:
            pid = it["data-productid"]
            if pid in products:
                continue
            a = it.select_one(".product-title a")
            if not a:
                continue
            new += 1
            cur, old = it.select_one(".actual-price"), it.select_one(".old-price")
            products[pid] = {
                "id": int(pid),
                "name": a.get_text(strip=True),
                "img": img_src(it.select_one(".picture img")),
                "price": money(cur.get_text()) if cur else 0,
                "old": money(old.get_text()) if old else 0,
            }
        print(f"Stok sayfası {page}: {len(items)} ürün ({new} yeni)")
        if not items or not new:
            break
    return products


def scrape_brands():
    soup = get("/manufacturer/all")
    brands = []
    seen = set()
    for box in soup.select(".manufacturer-item"):
        a = box.select_one("h2.title a, .title a")
        if not a or not a.get("href"):
            continue
        href = a["href"]
        if href in seen or "manufacturer/all" in href:
            continue
        seen.add(href)
        brands.append({"name": a.get_text(strip=True), "href": href, "logo": img_src(box.select_one("img"))})
    print(f"{len(brands)} marka bulundu")
    return brands


def brand_product_ids(href):
    ids = set()
    sep = "&" if "?" in href else "?"
    for page in range(1, MAX_PAGES + 1):
        soup = get(f"{href}{sep}pagenumber={page}")
        items = product_items(soup)
        page_ids = {it["data-productid"] for it in items}
        if not page_ids or page_ids <= ids:
            break
        ids |= page_ids
        if not soup.select_one(".pager .next-page"):
            break
    return ids


def strip_base(url):
    return url[len(IMG_BASE):] if url.startswith(IMG_BASE) else url


def main():
    products = scrape_stock()
    if len(products) < 100:
        raise SystemExit(f"Beklenenden az ürün geldi ({len(products)}), mevcut veri korunuyor.")

    brands = scrape_brands()
    brand_of = {}
    for b in brands:
        ids = brand_product_ids(b["href"])
        for pid in ids:
            brand_of.setdefault(pid, b["href"])
    print(f"{len(brand_of)} ürün markayla eşleşti")

    used = [b for b in brands if any(brand_of.get(pid) == b["href"] for pid in products)]
    index = {b["href"]: i for i, b in enumerate(used)}

    out_b = [[b["name"], strip_base(b["logo"])] for b in used]
    out_p = []
    for pid, p in products.items():
        row = [p["id"], p["name"], strip_base(p["img"]).replace("_360.", "~"), index.get(brand_of.get(pid), -1), p["price"]]
        if p["old"] and p["old"] > p["price"]:
            row.append(p["old"])
        out_p.append(row)

    data = {"updated": datetime.now(timezone.utc).isoformat(timespec="minutes"), "B": out_b, "P": out_p}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    # Sadece içerik değiştiyse dosyayı yaz (gereksiz güncellemeleri önler)
    old = None
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            old = None
    if old and old.get("B") == data["B"] and old.get("P") == data["P"]:
        print("Değişiklik yok.")
        return
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Yazıldı: {len(out_p)} ürün, {len(out_b)} marka")


if __name__ == "__main__":
    main()
