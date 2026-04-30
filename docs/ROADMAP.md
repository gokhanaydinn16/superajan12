# SuperAjan12 Roadmap

## Faz 1 - Veri okuma ve paper trading cekirdegi

- [x] Python proje yapisi
- [x] Polymarket public market connector
- [x] Market scanner agent
- [x] Risk engine v1
- [x] CLI scan komutu
- [x] Endpoint verification komutu
- [x] Orderbook midpoint/spread fallback
- [x] JSON audit log
- [x] SQLite veri kaydi
- [x] Resolution Agent v1
- [x] Probability Agent baseline v1
- [x] Paper Portfolio / paper position defteri
- [x] Reporting komutu
- [x] Safe-mode / kill-switch iskeleti
- [x] Temel testler
- [ ] Polymarket endpoint formatlarini kullanici ortaminda canli calisma ile dogrula
- [ ] Orderbook token id eslestirmesini canli veride sertlestir

## Faz 2 - Dogrulama katmani

- [x] Kalshi market data connector
- [x] Binance BTC/ETH/SOL referans verisi
- [x] OKX referans verisi
- [x] Coinbase spot referans verisi
- [x] Kaynak tutarsizligi alarmi v1
- [ ] Cross-market event mapping
- [ ] Kalshi-Polymarket benzer market eslestirme skoru
- [ ] Reference check sonucunu scanner risk kararina bagla

## Faz 3 - Ajan kalitesi

- [x] Resolution Agent v1
- [x] Probability Agent baseline v1
- [ ] Liquidity Agent v2
- [ ] News Reliability Agent
- [ ] Social Signal Agent
- [ ] Smart Wallet Intelligence Agent
- [ ] Manipulasyon riski skoru

## Faz 4 - Shadow trading

- [x] Paper position defteri v1
- [ ] Canli veri ile emir gondermeden karar kaydi
- [ ] Karar-sonuc performans raporu
- [ ] Strateji skor sistemi
- [ ] Model version tracking

## Faz 5 - Kontrollu canli test

- [ ] API key secret manager
- [ ] Live execution connector
- [x] Kill-switch iskeleti
- [ ] Reconciliation Agent
- [ ] Kucuk sermaye limitleri
- [ ] Manual approval gate

## Degismez kurallar

- Varsayilan mod paper mode.
- Risk motoru onay vermeden emir yok.
- Resolution belirsizse islem yok.
- Likidite yetersizse islem yok.
- Referans fiyat kaynaklari fazla saparsa kripto olay sinyalleri guvensiz sayilir.
- Safe-mode aktifse yeni islem yok.
- Canli sistem kendi kodunu degistirmez.
- Model gercek edge uretmedikce sahte guvenle islem acmaz.
