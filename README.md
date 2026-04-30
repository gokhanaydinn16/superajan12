# superajan12

Polymarket merkezli, coklu veri kaynagi ile dogrulama yapan, risk kontrollu otonom prediction market ajan sistemi.

## Ilk hedef

Bu repo once canli para kullanmadan calisacak bir cekirdek kurar:

1. Polymarket marketlerini okur.
2. Fiyat, spread, hacim ve likidite olcer.
3. Resolution metnini ve risk bayraklarini kaydeder.
4. Risk motorundan gecmeyen marketlerde islem acmaz.
5. Paper trading sinyali uretir.
6. Her karari SQLite ve JSONL audit trail olarak kaydeder.

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
Liquidity + Risk checks
        |
Risk Engine
        |
Paper Trade Idea
        |
SQLite + JSONL Audit log
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
superajan12 scan --limit 25
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
- Safe-mode aktifse yeni karar uretilmez.
- Faz 1'de trading/auth endpointleri kullanilmaz.

## Endpoint notlari

- Gamma API: aktif marketleri bulmak icin `/markets`.
- CLOB API: `/book`, `/midpoint`, `/spread` ile orderbook ve fiyat okuma.
- `verify-endpoints` komutu public endpointleri canli kontrol eder.
- Full orderbook basarisizsa scanner midpoint/spread fallback kullanir.
- Trading endpointleri bu fazda kapali tutulur.

Detay: `docs/ENDPOINTS.md`

## Yol haritasi

- Faz 1: Polymarket veri okuma + market puanlama + SQLite/audit log + paper trading.
- Faz 2: Resolution agent + haber/kaynak dogrulama.
- Faz 3: Kalshi, Binance, OKX, Coinbase veri katmani.
- Faz 4: Shadow trading.
- Faz 5: Reconciliation, kill-switch, secret manager ve kucuk sermaye ile kontrollu canli test.
