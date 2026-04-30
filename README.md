# superajan12

Polymarket merkezli, coklu veri kaynagi ile dogrulama yapan, risk kontrollu otonom prediction market ajan sistemi.

## Ilk hedef

Bu repo once canli para kullanmadan calisacak bir cekirdek kurar:

1. Polymarket marketlerini okur.
2. Fiyat, spread, hacim ve likidite olcer.
3. Resolution metnini ve risk bayraklarini kaydeder.
4. Risk motorundan gecmeyen marketlerde islem acmaz.
5. Paper trading sinyali uretir.
6. Binance, OKX ve Coinbase ile kripto referans fiyatlarini capraz kontrol eder.
7. Kalshi ile olay piyasasi karsilastirma katmanina hazirlik yapar.
8. Her karari SQLite ve JSONL audit trail olarak kaydeder.

## Ana prensip

> Once sermayeyi koru, sonra firsat ara.

Canli emir motoru basit, disiplinli ve risk motoruna bagli kalacak. Ajanlar dusunecek; risk motoru izin verecek; emir motoru sadece onayli emri uygulayacak.

## Mimari

```text
Polymarket Gamma markets
        |
Market Scanner Agent
        |
Polymarket CLOB orderbook / midpoint / spread
        |
Resolution + Probability + Liquidity checks
        |
Risk Engine
        |
Paper Trade Idea
        |
Paper Portfolio
        |
SQLite + JSONL Audit log

Binance / OKX / Coinbase
        |
Crypto Reference Agent
        |
Reference deviation alarm

Kalshi
        |
Cross-market event comparison layer
```

Ilk asamada canli emir yoktur. Varsayilan mod `paper` modudur.

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
superajan12 init-db
superajan12 verify-endpoints
superajan12 reference-check --symbols BTC,ETH,SOL
superajan12 scan --limit 25
superajan12 report
```

Kaydetmeden deneme:

```bash
superajan12 scan --limit 25 --no-save
```

Test:

```bash
ruff check src tests
pytest -q
```

## Local ciktilar

Varsayilan olarak su dosyalar olusur:

```text
data/superajan12.sqlite3
data/audit/events.jsonl
```

Bu dosyalar `.gitignore` icindedir ve repoya yazilmaz.

## Guvenlik

- API keyler repoya yazilmaz.
- Varsayilan mod paper trading'dir.
- Risk motoru onay vermeden emir olusmaz.
- Resolution belirsizse islem yoktur.
- Likidite yetersizse islem yoktur.
- Referans fiyat kaynaklari fazla saparsa kripto olay sinyalleri guvensiz sayilir.
- Safe-mode aktifse yeni karar uretilmez.
- Faz 1/Faz 2 public-data katmaninda trading/auth endpointleri kullanilmaz.

## Endpoint notlari

- Polymarket Gamma API: aktif marketleri bulmak icin `/markets`.
- Polymarket CLOB API: `/book`, `/midpoint`, `/spread` ile orderbook ve fiyat okuma.
- Binance USD-M Futures public API: mark price, funding, open interest.
- OKX public API: ticker.
- Coinbase Advanced Trade public market API: product ve best bid/ask.
- Kalshi public market data: market kesfi ve olay karsilastirma.
- `verify-endpoints` komutu Polymarket public endpointlerini canli kontrol eder.
- `reference-check` komutu kripto referans fiyatlarini capraz kontrol eder.
- Full Polymarket orderbook basarisizsa scanner midpoint/spread fallback kullanir.
- Trading endpointleri bu fazda kapali tutulur.

Detay: `docs/ENDPOINTS.md`

## Yol haritasi

- Faz 1: Polymarket veri okuma + market puanlama + SQLite/audit log + paper trading.
- Faz 2: Kalshi, Binance, OKX, Coinbase public-data dogrulama katmani.
- Faz 3: Haber/kaynak guvenilirligi, sosyal sinyal ve smart wallet ajanlari.
- Faz 4: Shadow trading performans raporu.
- Faz 5: Reconciliation, kill-switch, secret manager ve kucuk sermaye ile kontrollu canli test.
