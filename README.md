# Çekmeköy Helal Market – Online Sipariş

- `public/` – müşterilerin gördüğü sayfa (index.html, logo, arka plan, data.json)
- `scraper.py` – Çekmeköy şubesi stok listesini tedarikçi sitesinden çeker, `public/data.json` dosyasını günceller
- `.github/workflows/guncelle.yml` – saat başı ürünleri çeker ve sayfayı yeniden yayınlar

Ayarlar: WhatsApp numarası `public/index.html` içinde `WHATSAPP_NO` satırındadır.
Elle güncelleme: GitHub'da **Actions → Ürünleri güncelle ve yayınla → Run workflow**.
