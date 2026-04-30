# SuperAjan12 Roadmap

## Faz 1 - Veri okuma ve paper trading cekirdegi

- [x] Python proje yapisi
- [x] Polymarket public market connector
- [x] Market scanner agent
- [x] Risk engine v1
- [x] CLI scan komutu
- [x] Temel testler
- [ ] Polymarket endpoint formatlarini canli calisma ile dogrula
- [ ] Orderbook token id eslestirmesini sertlestir
- [ ] JSON audit log ekle
- [ ] SQLite/PostgreSQL veri kaydi ekle
- [ ] Resolution metni parser v1 ekle

## Faz 2 - Dogrulama katmani

- [ ] Kalshi market data connector
- [ ] Binance BTC/ETH/SOL referans verisi
- [ ] OKX referans verisi
- [ ] Coinbase spot referans verisi
- [ ] Kaynak tutarsizligi alarmi

## Faz 3 - Ajan kalitesi

- [ ] Resolution Agent
- [ ] Liquidity Agent
- [ ] News Reliability Agent
- [ ] Social Signal Agent
- [ ] Smart Wallet Intelligence Agent

## Faz 4 - Shadow trading

- [ ] Canli veri ile emir gondermeden karar kaydi
- [ ] Karar-sonuc performans raporu
- [ ] Strateji skor sistemi

## Faz 5 - Kontrollu canli test

- [ ] API key secret manager
- [ ] Live execution connector
- [ ] Kill-switch
- [ ] Reconciliation Agent
- [ ] Kucuk sermaye limitleri

## Degismez kurallar

- Varsayilan mod paper mode.
- Risk motoru onay vermeden emir yok.
- Resolution belirsizse islem yok.
- Likidite yetersizse islem yok.
- Safe-mode aktifse yeni islem yok.
- Canli sistem kendi kodunu degistirmez.
