# Kişisel Finans ve Muhasebe Uygulaması — Mimari Plan

> Bu plan, geliştirilecek uygulamanın mimarisini tanımlar. Tasarımın merkezinde iki ilke vardır: **davranış kodda, parametre veride** (dinamik sistem) ve **borç enstrümanı → ödeme planı → taksit bileşeni → ödeme anında bölünme** (omurga).

---

## 1. Amaç ve Kapsam

Kişisel finansı yönetmek için masaüstü bir PyQt5 uygulaması: banka hesapları, kredi kartları, KMH (ek hesap), krediler, taksitli nakit avans, para hareketleri ve gider/masraf takibi.

Ödemelerin yaklaşık %99'u bankalar üzerinden gerçekleşir (kredi kartı, KMH, kredi, taksitli nakit avans, taksitli ek hesap). Uygulama bu nedenle bir "banka bakiye defteri" değil, **kredi enstrümanları + ödeme takvimi + gider/masraf izleme** üçlüsü etrafında kurulur.

İlk geliştirilecek kapsam: **Finans → Bankalar**. Diğer ana modüller (Muhasebe, Trade, Bilim) arayüzde görünür ama devre dışıdır.

---

## 2. Temel Tasarım Kararları (Önce Bunlar)

Bu kararlar şemayı belirler; sonradan değişirse her şeyi etkiler.

### 2.1. Dinamik referans verisi — koda gömme yok

Para birimleri, gider/masraf kategorileri, varlıklar (araba, ev) ve taksit bileşen tipleri (anapara, faiz, KKDF, BSMV, fon, sigorta…) **kodda sabit değildir; veritabanında satırdır**. Kullanıcı yenisini ekleyebilir, özelliğini belirleyebilir. Kodda yalnızca *davranış* yaşar; her ayarlanabilir parametre veriye taşınır.

### 2.2. Para birimi dinamik + ondalık hassasiyeti (scale)

Para birimleri `currencies` tablosunda tanımlanır; her birinin bir **scale** (ondalık basamak) değeri vardır. Tutarlar veritabanında her zaman **tam sayı** olarak, ilgili para biriminin en küçük biriminde saklanır.

```
TRY scale=2  →  123,45 TL  saklanır: 12345
USD scale=2  →  10,50 USD  saklanır: 1050
XAU scale=3  →  2,500 gr   saklanır: 2500
```

Gösterim: `value / 10^scale`. Sabit `/100` **kullanılmaz** — altın gibi birimlerde yanlış olur. Float aritmetiği finansal alanda yasaktır; gösterimde bile tamsayı bölme/format ile yapılır (bkz. §7.3).

### 2.3. Borç omurgası — bankanın planı saklanır, yeniden hesaplanmaz

Kredi, taksitli KMH ve taksitli nakit avans yapısal olarak **aynı şeydir**: N taksitlik, her taksidi bileşenlerine ayrılmış bir ödeme planı. Kodda üç ayrı sınıf değil, **tek bir `debt_plan` + `plan_kind` parametresi** vardır.

Faiz/KKDF/BSMV **sistem tarafından yeniden hesaplanmaz**. Bankanın verdiği plan (ör. 45 günlük ilk dönem, bankaya özgü yuvarlama, vergi bindirme şekli) olduğu gibi **içeri alınıp saklanır**. Sistem bundan yaklaşan ödeme takvimini, kalan borcu ve aylık faiz yükünü *türetir*. Kullanıcı plan "yapmaz"; bankanınkini kaydeder.

### 2.4. Nitelik ekseni — gider / masraf / anapara / transfer

Bir nakit hareketinin her satırı bir **nitelik** taşır. Nitelik sabit, küçük bir kümedir (kullanıcı uyduramaz):

| Nitelik | Anlam | Örnek |
|---|---|---|
| `income` | Gelir | Maaş, kira geliri |
| `expense` | Gider (düzenli, beklenen) | Yakıt, kira, aidat, faiz |
| `cost` | Masraf (arızi, beklenmedik onarım) | Eksantrik mili, patlayan ampül |
| `principal` | Anapara ödemesi (borcu azaltır, tüketim değil) | Taksidin anapara payı |
| `transfer` | Hesaplar arası yer değiştirme | Havale, döviz bozdurma |

Bu eksen işlevsel olarak kritik: bir kredi taksidini ödediğinde 49.079 TL çıkar ama bunun ~16.114'ü `principal` (borç azaltır), ~33.000'i `expense` (gerçek gider). "Bu ay ne harcadım?" sorusu ancak bu ayrımla doğru cevaplanır: 49 bin değil, ~33 bin harcadın.

Buna karşılık **kategori** (yakıt, kira, tamir…) ve **varlık** (Twingo, Ev, Genel) tamamen kullanıcının tanımladığı veridir. Her kategori bir `expense`/`cost`/`income` niteliği taşır; `principal` ve `transfer` satırları sistem üretir, kategori taşımaz.

### 2.5. Tek girişli + bölünme (split)

Her nakit olayı bir **işlem başlığı** (`transactions`) + bir veya daha çok **işlem satırı** (`transaction_lines`) olarak modellenir. Basit gider tek satırdır; bir taksit ödemesi çok satırdır (anapara + faiz + KKDF + BSMV…). Çift girişli muhasebe değildir — o, ileride "Muhasebe" ana modülünün işidir.

### 2.6. Likidite bir özelliktir, kodda "if" değildir

"Kart limiti likidite değildir, nakit avans/KMH limiti likiditedir" kuralı kodda dallanma olarak değil, enstrümanın `counts_as_liquidity` bayrağı olarak yaşar. Kullanılabilir likidite = nakit bakiyeler + bayrağı açık enstrümanların kullanılabilir tutarı.

### 2.7. Hareket-kaynaklı bakiye + bilinçli snapshot istisnası

Hesap bakiyesi hareketlerden türetilebilir; `current_balance` bir önbellektir, doğruluk kaynağı hareketlerdir (§9). Bilinçli istisna: kartın dönen alışveriş borcu ve KMH'nin dönen kullanımı her işlem girilmeyeceği için **snapshot** olarak tutulur (ekstreden / kullanıcıdan). Taksitli olan her şey omurgaya (plan) bağlıdır ve türetilir. Bu asimetri tesadüf değil, karardır.

---

## 3. Navigasyon ve Arayüz

### 3.1. Yapı

```
┌─────────────────────────────────────────────────────────┐
│  Finans   |   Muhasebe   |   Trade   |   Bilim          │  ← Üst nav (4 modül)
├──────────────────┬──────────────────────────────────────┤
│ Banka Özeti      │                                      │
│ Hesaplar         │            İçerik alanı              │
│ Kredi Kartları   │                                      │
│ KMH / Ek Hesap   │   (seçilen sayfa burada açılır)      │
│ Krediler         │                                      │
│ Taksitli Avanslar│                                      │
│ Para Hareketleri │                                      │
│ Transferler      │                                      │
│ Tanımlar         │   ← para birimi, kategori, varlık,   │
│ Raporlar         │      bileşen tipi yönetimi           │
└──────────────────┴──────────────────────────────────────┘
```

Bankalar giriş sayfası: üstte özet kartlar (toplam nakit, KK borcu, KMH+kredi borcu, kullanılabilir likidite, net durum), altta hızlı erişim butonları (Banka Ekle, Hesap Ekle, Hareket Ekle, Tüm Hesaplar).

### 3.2. Arayüz teknolojisi — PyQt-Fluent-Widgets

Arayüz **PyQt-Fluent-Widgets (`qfluentwidgets`)** üzerine kurulur. Üst-nav + sol-sidebar + özet-kart düzeni bu kütüphanenin hazır verdiği yapıdır, yani sıfırdan kurmaya gerek kalmaz.

Kurulum ve lisans: `pip install PyQt-Fluent-Widgets` (PyQt5 sürümü). Kişisel kullanımda GPLv3 — ücretsiz. Lite sürüm yeterlidir; Pro bileşenlere gerek yok.

Bileşen eşlemesi:

| İhtiyaç | Fluent bileşeni |
|---|---|
| Ana pencere + üst/yan navigasyon | `MSFluentWindow` / `FluentWindow` + `navigationInterface` |
| Özet kartlar (toplam nakit, borç, likidite…) | `CardWidget` / `HeaderCardWidget` |
| Butonlar, giriş alanları, tablolar | `PrimaryPushButton`, `LineEdit`, `TableWidget` |
| Bildirim / uyarı (negatif bakiye vb.) | `InfoBar` |
| İkonlar | `FluentIcon` (ek olarak gerekirse `QtAwesome`) |

Bağlanma sınırı: bu kütüphane **yalnızca UI katmanını** etkiler. `service`, `repository`, `database` katmanları kütüphaneden bağımsızdır; iş kuralı, validasyon ve hesaplama UI'ya asla gömülmez. Stiller tema düzeyinde merkezîdir (`setTheme`, `setThemeColor`); her widget'a ayrı stil yazılmaz.

---

## 4. Teknoloji Kararları

| Bileşen | Karar |
|---|---|
| Dil | Python |
| Arayüz | PyQt5 + PyQt-Fluent-Widgets (`qfluentwidgets`) |
| Veritabanı | SQLite (`PRAGMA foreign_keys = ON`) |
| Para tipi | INTEGER, para biriminin en küçük biriminde (scale ile) |
| ORM | Yok — sade SQL + repository katmanı |
| Faiz motoru | Yok — bankanın planı saklanır |
| Migrasyon | `schema_version` tablosu + basit migration runner |

---

## 5. Mimari Prensipler

### 5.1. Katman sırası

```
UI → Service → Repository → Database
```

Her katman yalnızca bir alt katmanla konuşur. UI SQL bilmez; Service UI bilmez. Validasyon, hesaplama, kontrol service katmanına aittir.

### 5.2. Modüller arası izolasyon

Hiçbir modül başka modülün iç dosyalarını doğrudan import etmez. Haberleşme `core`, `services`, `repositories` ve `event_bus` üzerinden olur. `event_bus` baştan yazılır, ilk sürümde basit tutulur.

### 5.3. Sabit vs dinamik sınırı

Kodda kalan (sabit, küçük küme): nitelikler, `plan_kind`, taksit durumu, yön, takip modu — bunlar rapor mantığının iskeletidir.
Veriye taşınan (dinamik): para birimleri, kategoriler, varlıklar, bileşen tipleri. Kullanıcı bunları çalışırken ekler/düzenler.

---

## 6. Klasör Yapısı

```
app/
├── main.py
│
├── core/
│   ├── database.py          # bağlantı, init, PRAGMA, migration runner
│   ├── schema.sql           # tüm CREATE TABLE + index ifadeleri
│   ├── migrations/          # sürümlü şema değişiklikleri
│   ├── event_bus.py
│   ├── constants.py         # SABİT enum'lar (nitelik, plan_kind, durum…)
│   ├── seed.py              # düzenlenebilir başlangıç verisi (TRY, kategoriler…)
│   ├── money.py             # scale'e göre format/parse
│   ├── validators.py
│   └── exceptions.py
│
├── repositories/
│   ├── currency_repository.py
│   ├── category_repository.py
│   ├── asset_repository.py
│   ├── component_type_repository.py
│   ├── bank_repository.py
│   ├── account_repository.py
│   ├── credit_card_repository.py
│   ├── kmh_repository.py
│   ├── debt_plan_repository.py
│   ├── transaction_repository.py
│   └── transfer_repository.py
│
├── services/
│   ├── reference_service.py     # para birimi/kategori/varlık/bileşen tipi
│   ├── bank_service.py
│   ├── account_service.py       # reconcile dahil
│   ├── transaction_service.py   # split mantığı
│   ├── debt_plan_service.py     # plan + taksit + bileşen + ödeme→split
│   ├── credit_card_service.py
│   ├── kmh_service.py
│   ├── transfer_service.py
│   ├── summary_service.py       # özet kartlar, likidite, net durum
│   └── audit_service.py
│
├── modules/
│   └── banks/
│       ├── banks_module.py
│       ├── banks_landing_page.py
│       ├── pages/
│       │   ├── bank_summary_page.py
│       │   ├── accounts_page.py
│       │   ├── credit_cards_page.py
│       │   ├── kmh_page.py
│       │   ├── loans_page.py
│       │   ├── installment_advances_page.py
│       │   ├── transactions_page.py
│       │   ├── transfers_page.py
│       │   ├── definitions_page.py   # Tanımlar (dinamik veri yönetimi)
│       │   └── reports_page.py
│       ├── dialogs/
│       │   ├── add_bank_dialog.py
│       │   ├── add_account_dialog.py
│       │   ├── add_transaction_dialog.py
│       │   ├── add_debt_plan_dialog.py     # plan satırlarını manuel girme
│       │   └── pay_installment_dialog.py
│       └── widgets/
│           ├── summary_card_widget.py
│           └── installment_table_widget.py
│
└── ui/
    ├── main_window.py       # MSFluentWindow tabanlı; üst + yan navigasyon
    ├── navigation.py         # navigationInterface kurulumu, modül kayıtları
    └── theme.py              # setTheme / setThemeColor, merkezi tema ayarı
```

---

## 7. Çekirdek Sabitler ve Yardımcılar

### 7.1. Nitelik ve durum sabitleri (`core/constants.py`)

```python
class Nature:
    INCOME = "income"          # gelir
    EXPENSE = "expense"        # gider
    COST = "cost"              # masraf
    PRINCIPAL = "principal"    # anapara ödemesi (borcu azaltır)
    TRANSFER = "transfer"      # hesaplar arası

class PlanKind:
    LOAN = "loan"                              # kredi
    KMH_INSTALLMENT = "kmh_installment"        # taksitli ek hesap (KMH)
    CASH_ADVANCE_INSTALLMENT = "ca_installment"# taksitli nakit avans

class InstallmentStatus:
    PLANNED = "planned"
    PARTIAL = "partial"
    PAID = "paid"

class Direction:
    IN = "in"
    OUT = "out"

class TrackingMode:
    LEDGER = "ledger"      # bakiye hareketlerden türetilir
    SNAPSHOT = "snapshot"  # bakiye elle güncellenir

# Türkçe etiketler yalnızca arayüzde:
NATURE_LABELS = {
    Nature.INCOME: "Gelir", Nature.EXPENSE: "Gider", Nature.COST: "Masraf",
    Nature.PRINCIPAL: "Anapara", Nature.TRANSFER: "Transfer",
}
```

### 7.2. Düzenlenebilir başlangıç verisi (`core/seed.py`)

İlk açılışta yazılır ama kullanıcı sonradan değiştirebilir/silebilir/ekleyebilir.

```python
SEED_CURRENCIES = [
    # (code, symbol, scale)
    ("TRY", "₺", 2), ("USD", "$", 2), ("EUR", "€", 2), ("XAU", "gr", 3),
]

SEED_COMPONENT_TYPES = [
    # (code, name, nature)  → KKDF/BSMV/Fon/sigorta hepsi expense; anapara principal
    ("principal", "Anapara", Nature.PRINCIPAL),
    ("interest",  "Faiz",    Nature.EXPENSE),
    ("kkdf",      "KKDF",    Nature.EXPENSE),
    ("bsmv",      "BSMV",    Nature.EXPENSE),
    ("fund",      "Fon",     Nature.EXPENSE),    # Garanti "Fon"
    ("tax",       "Vergi",   Nature.EXPENSE),    # Garanti "Vergi"
    ("life_ins",  "Hayat sigortası", Nature.EXPENSE),
    ("fee",       "Masraf/ücret",    Nature.EXPENSE),
]

SEED_CATEGORIES = [
    # (name, nature)
    ("Faiz gideri", Nature.EXPENSE), ("Sigorta", Nature.EXPENSE),
    ("Yakıt", Nature.EXPENSE), ("Kira", Nature.EXPENSE), ("Aidat", Nature.EXPENSE),
    ("Elektrik", Nature.EXPENSE), ("Su", Nature.EXPENSE),
    ("Tamir", Nature.COST), ("Onarım", Nature.COST),
    ("Maaş", Nature.INCOME),
]

SEED_ASSETS = [
    # (name, type)
    ("Genel", "other"), ("Twingo", "vehicle"), ("Ev", "property"),
]
```

### 7.3. Para gösterimi (`core/money.py`)

```python
def format_amount(value: int, scale: int) -> str:
    """Tamsayı en-küçük-birim → görüntü dizesi. Float'a düşmeden."""
    sign = "-" if value < 0 else ""
    v = abs(value)
    base = 10 ** scale
    whole, frac = divmod(v, base)
    # binlik ayırıcı arayüzde locale ile; burada sade:
    return f"{sign}{whole},{str(frac).zfill(scale)}" if scale else f"{sign}{whole}"

def parse_amount(text: str, scale: int) -> int:
    """Görüntü dizesi → tamsayı en-küçük-birim."""
    text = text.strip().replace(".", "").replace(",", ".")
    from decimal import Decimal
    return int((Decimal(text) * (10 ** scale)).to_integral_value())
```

---

## 8. Veritabanı Şeması

> Tablolar bağımlılık sırasına göre tanımlanır. `PRAGMA foreign_keys = ON` baştan aktiftir. Tüm tablolarda soft delete (`deleted_at`) standarttır; sorgular varsayılan olarak `WHERE deleted_at IS NULL` uygular. Benzersizlik kuralları **kısmi index** ile kurulur (silinen kaydın adı yeni kaydı kilitlemesin diye, bkz. §8.13).

### 8.1. schema_version

```sql
CREATE TABLE schema_version (
    version     INTEGER NOT NULL,
    applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 8.2. currencies (dinamik)

```sql
CREATE TABLE currencies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL,              -- 'TRY','USD','EUR','XAU'
    symbol      TEXT,
    scale       INTEGER NOT NULL DEFAULT 2, -- ondalık basamak sayısı
    is_active   INTEGER NOT NULL DEFAULT 1,
    deleted_at  TIMESTAMP NULL
);
```

### 8.3. categories (dinamik)

```sql
CREATE TABLE categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    nature      TEXT NOT NULL,   -- 'income' | 'expense' | 'cost'
    parent_id   INTEGER NULL REFERENCES categories(id),
    is_active   INTEGER NOT NULL DEFAULT 1,
    deleted_at  TIMESTAMP NULL
);
```

### 8.4. assets (dinamik — varlık/bağlam: Twingo, Ev…)

```sql
CREATE TABLE assets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    type        TEXT,            -- 'vehicle' | 'property' | 'other'
    is_active   INTEGER NOT NULL DEFAULT 1,
    deleted_at  TIMESTAMP NULL
);
```

### 8.5. component_types (dinamik — taksit bileşeni tipleri)

```sql
CREATE TABLE component_types (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL,   -- 'principal','interest','kkdf','bsmv','fund'...
    name        TEXT NOT NULL,
    nature      TEXT NOT NULL,   -- 'principal' (borç azaltır) | 'expense' (gider)
    is_active   INTEGER NOT NULL DEFAULT 1,
    deleted_at  TIMESTAMP NULL
);
```

### 8.6. banks

```sql
CREATE TABLE banks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    short_name  TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    note        TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at  TIMESTAMP NULL
);
```

### 8.7. accounts (banka nakit hesabı)

```sql
CREATE TABLE accounts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id          INTEGER NOT NULL REFERENCES banks(id),
    name             TEXT NOT NULL,
    currency_id      INTEGER NOT NULL REFERENCES currencies(id),
    opening_balance  INTEGER NOT NULL DEFAULT 0,    -- en küçük birim
    current_balance  INTEGER NOT NULL DEFAULT 0,    -- ÖNBELLEK (cache)
    tracking_mode    TEXT NOT NULL DEFAULT 'ledger',-- 'ledger' | 'snapshot'
    is_active        INTEGER NOT NULL DEFAULT 1,
    note             TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at       TIMESTAMP NULL
);
-- Hesap oluşturulurken current_balance = opening_balance atanır (service'te).
-- account_type alanı yoktur: hesabın para birimi yalnızca currency_id'dir.
```

### 8.8. credit_cards (dönen alışveriş borcu çekirdeği)

```sql
CREATE TABLE credit_cards (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id             INTEGER NOT NULL REFERENCES banks(id),
    name                TEXT NOT NULL,
    card_limit          INTEGER NOT NULL DEFAULT 0,   -- en küçük birim
    statement_day       INTEGER,                      -- ekstre günü
    due_day             INTEGER,                      -- son ödeme günü
    counts_as_liquidity INTEGER NOT NULL DEFAULT 0,   -- alışveriş limiti likidite DEĞİL
    is_active           INTEGER NOT NULL DEFAULT 1,
    note                TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMP NULL
);
```

### 8.9. card_statements (ekstre snapshot'ı — aylık girilir)

```sql
CREATE TABLE card_statements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    credit_card_id  INTEGER NOT NULL REFERENCES credit_cards(id),
    statement_date  DATE NOT NULL,
    statement_debt  INTEGER NOT NULL DEFAULT 0,   -- ekstre borcu
    min_payment     INTEGER NOT NULL DEFAULT 0,
    due_date        DATE,
    available_limit INTEGER,                      -- ekstredeki kullanılabilir limit
    note            TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TIMESTAMP NULL
);
-- Kartın "taksitli nakit avans" kalemleri burada DEĞİL, debt_plans'ta yaşar (§8.11).
```

### 8.10. kmh_accounts (ek hesap / KMH — bir banka hesabına bağlı)

```sql
CREATE TABLE kmh_accounts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id             INTEGER NOT NULL REFERENCES banks(id),
    account_id          INTEGER NOT NULL REFERENCES accounts(id),
    kmh_limit           INTEGER NOT NULL DEFAULT 0,
    used_amount         INTEGER NOT NULL DEFAULT 0,   -- DÖNEN kullanım snapshot'ı
    interest_rate       REAL,                         -- aylık %, referans
    counts_as_liquidity INTEGER NOT NULL DEFAULT 1,   -- KMH limiti likidite
    is_active           INTEGER NOT NULL DEFAULT 1,
    note                TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMP NULL
);
-- available = kmh_limit - used_amount (türetilir, saklanmaz).
-- Taksitli ek hesap kullanımı debt_plans'a (plan_kind='kmh_installment') gider.
```

### 8.11. debt_plans (OMURGA — kredi / taksitli KMH / taksitli nakit avans)

```sql
CREATE TABLE debt_plans (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id           INTEGER NOT NULL REFERENCES banks(id),
    plan_kind         TEXT NOT NULL,   -- 'loan' | 'kmh_installment' | 'ca_installment'
    source_card_id    INTEGER NULL REFERENCES credit_cards(id),   -- karttan çekildiyse
    source_kmh_id     INTEGER NULL REFERENCES kmh_accounts(id),   -- ek hesaptan ise
    name              TEXT NOT NULL,
    principal_amount  INTEGER NOT NULL DEFAULT 0,   -- kullandırım tutarı
    currency_id       INTEGER NOT NULL REFERENCES currencies(id),
    interest_rate     REAL,            -- aylık %, yalnızca gösterim
    start_date        DATE,
    installment_count INTEGER NOT NULL DEFAULT 0,
    is_active         INTEGER NOT NULL DEFAULT 1,
    note              TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at        TIMESTAMP NULL
);
```

### 8.12. transactions (nakit olayı başlığı)

```sql
CREATE TABLE transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      INTEGER NOT NULL REFERENCES accounts(id),
    txn_date        DATE NOT NULL,
    direction       TEXT NOT NULL,        -- 'in' | 'out'
    total_amount    INTEGER NOT NULL,     -- en küçük birim, hesabın para biriminde
    description     TEXT,
    affects_balance INTEGER NOT NULL DEFAULT 1,
    source_type     TEXT NULL,            -- 'manual' | 'installment' | 'transfer'
    source_id       INTEGER NULL,         -- yumuşak bağ (FK yok → döngü yok)
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TIMESTAMP NULL
);
-- Para birimi ayrı saklanmaz: işlemin para birimi, bağlı hesabın para birimidir.
-- Σ(transaction_lines.amount) = total_amount (service doğrular).
```

### 8.13. transaction_lines (bölünme/split satırları)

```sql
CREATE TABLE transaction_lines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  INTEGER NOT NULL REFERENCES transactions(id),
    nature          TEXT NOT NULL,        -- income|expense|cost|principal|transfer
    category_id     INTEGER NULL REFERENCES categories(id),  -- expense/cost/income için
    asset_id        INTEGER NULL REFERENCES assets(id),      -- Twingo, Ev… (opsiyonel)
    amount          INTEGER NOT NULL,
    note            TEXT,
    deleted_at      TIMESTAMP NULL
);
-- principal/transfer satırları kategori taşımaz (sistem üretir).
-- expense/cost satırının nature'ı, kategorinin nature'ı ile uyumlu olmalı (validasyon).
```

### 8.14. installments (taksit — bankanın planından)

```sql
CREATE TABLE installments (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    debt_plan_id               INTEGER NOT NULL REFERENCES debt_plans(id),
    seq                        INTEGER NOT NULL,    -- sıra no
    due_date                   DATE NOT NULL,
    total_amount               INTEGER NOT NULL,    -- taksit tutarı
    remaining_principal_after  INTEGER,             -- plandaki kalan anapara (gösterim)
    status                     TEXT NOT NULL DEFAULT 'planned',
    paid_transaction_id        INTEGER NULL REFERENCES transactions(id),
    paid_date                  DATE NULL,
    note                       TEXT,
    deleted_at                 TIMESTAMP NULL
);
```

### 8.15. installment_components (taksidin dinamik bileşenleri)

```sql
CREATE TABLE installment_components (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    installment_id    INTEGER NOT NULL REFERENCES installments(id),
    component_type_id INTEGER NOT NULL REFERENCES component_types(id),
    amount            INTEGER NOT NULL,
    deleted_at        TIMESTAMP NULL
);
-- KKDF/BSMV/Fon/Vergi/sigorta hepsi satırdır, kolon değil → bankalar arası esneklik.
-- Σ(amount) = installments.total_amount (service doğrular).
```

### 8.16. transfers (FX-farkında — hesaplar arası, döviz/altın dahil)

```sql
CREATE TABLE transfers (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    from_account_id  INTEGER NOT NULL REFERENCES accounts(id),
    to_account_id    INTEGER NOT NULL REFERENCES accounts(id),
    from_amount      INTEGER NOT NULL,
    from_currency_id INTEGER NOT NULL REFERENCES currencies(id),
    to_amount        INTEGER NOT NULL,
    to_currency_id   INTEGER NOT NULL REFERENCES currencies(id),
    exchange_rate    REAL NULL,            -- döviz bozdurma / altın alımı için
    transfer_date    DATE NOT NULL,
    description      TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at       TIMESTAMP NULL
);
-- Her transfer iki transaction üretir: from_account'ta 'out', to_account'ta 'in';
-- ikisinin de satırı nature='transfer', source_type='transfer', source_id=transfer.id.
```

### 8.17. audit_logs (değişiklik izi — yazıcısı tanımlı, öksüz değil)

```sql
CREATE TABLE audit_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type  TEXT NOT NULL,
    entity_id    INTEGER NOT NULL,
    action       TEXT NOT NULL,    -- 'create' | 'update' | 'delete'
    old_value    TEXT,             -- JSON
    new_value    TEXT,             -- JSON
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- audit_service her service mutasyonunda (create/update/soft-delete) çağrılır.
```

### 8.18. Kısmi benzersizlik index'leri (soft-delete uyumlu)

```sql
CREATE UNIQUE INDEX ux_currency_code  ON currencies(code)            WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX ux_comptype_code  ON component_types(code)       WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX ux_bank_name      ON banks(name)                 WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX ux_account_name   ON accounts(bank_id, name)     WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX ux_category_name  ON categories(name, nature)    WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX ux_asset_name     ON assets(name)                WHERE deleted_at IS NULL;

-- Performans index'leri (FK'ler üzerinde):
CREATE INDEX ix_txn_account     ON transactions(account_id)         WHERE deleted_at IS NULL;
CREATE INDEX ix_line_txn        ON transaction_lines(transaction_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_inst_plan       ON installments(debt_plan_id)        WHERE deleted_at IS NULL;
CREATE INDEX ix_comp_inst       ON installment_components(installment_id) WHERE deleted_at IS NULL;
```

---

## 9. Bakiye, Ödeme ve Reconcile Kuralları

Uygulamanın en kritik bölümüdür. Tüm bakiye etkileri **tek bir SQLite transaction** içinde gerçekleşir.

### 9.1. Hareket ekleme

1. `transactions` başlığı eklenir, `transaction_lines` satırları eklenir; Σ satır = `total_amount` doğrulanır.
2. `affects_balance = 1` ve hesap `tracking_mode = 'ledger'` ise `current_balance` güncellenir:
   - `direction = 'in'` → `current_balance += total_amount`
   - `direction = 'out'` → `current_balance -= total_amount`
3. `snapshot` hesaplarda otomatik güncelleme yapılmaz; bakiye elle ayarlanır.

### 9.2. Hareket düzenleme / silme (soft delete)

- Düzenleme: eski etkisi geri alınır, yeni etki uygulanır — aynı SQLite transaction'ında.
- Silme: `deleted_at` doldurulur, bakiye etkisi geri alınır.
- `updated_at` her UPDATE'te repository katmanında **elle** set edilir (SQLite `DEFAULT` UPDATE'te tetiklenmez).

### 9.3. Reconcile (doğru formül — yön + soft-delete dahil)

```python
def reconcile_balance(account_id: int) -> int:
    """
    Gerçek bakiye = açılış + giriş toplamı - çıkış toplamı
    (yalnızca affects_balance=1 VE deleted_at IS NULL hareketler).
    current_balance ile karşılaştırılıp drift tespit edilir.
    """
    # SELECT opening_balance ...
    # + SUM(total_amount) WHERE direction='in'  AND affects_balance=1 AND deleted_at IS NULL
    # - SUM(total_amount) WHERE direction='out' AND affects_balance=1 AND deleted_at IS NULL
```

İlk sürümde pasif bekler; denetim/hata ayıklama için baştan yazılır. `ledger` hesaplarda anlamlıdır; `snapshot` hesaplarda atlanır.

### 9.4. Taksit ödeme → niteliğe göre bölünme (omurganın kalbi)

Bir taksit ödendiğinde, tek SQLite transaction'ında:

1. `transactions` (out, ilgili hesap, `total_amount` = taksit tutarı, `source_type='installment'`, `source_id=installment.id`).
2. Taksidin her `installment_component` satırı için bir `transaction_line`:
   - `component_type.nature = 'principal'` → satır `nature='principal'` (borcu azaltır, gider değil).
   - `component_type.nature = 'expense'` → satır `nature='expense'`, uygun kategoriye (faiz/sigorta) yazılır.
3. `installments.status = 'paid'`, `paid_transaction_id`, `paid_date` set edilir.
4. Hesap `current_balance` taksit tutarı kadar azalır.

### 9.5. Transfer (atomik, FX-farkında)

Tek SQLite transaction'ında: `transfers` kaydı + `from_account`'ta 'out' transaction + `to_account`'ta 'in' transaction. İkisi de `nature='transfer'`. Transfer soft-delete edilirse **her iki transaction da** geri alınır ve soft-delete edilir.

### 9.6. Türetilen değerler (saklanmaz)

| Değer | Türetme |
|---|---|
| Hesap gerçek bakiyesi | açılış + Σgiriş − Σçıkış (§9.3) |
| KMH kullanılabilir | `kmh_limit − used_amount` |
| Kredi kartı kullanılabilir | `card_limit − güncel ekstre borcu` (veya ekstreden) |
| Bir planın kalan borcu | Σ(ödenmemiş taksitlerin tutarı) |
| Kullanılabilir likidite | Σ nakit bakiye + Σ(likidite bayraklı enstrümanların kullanılabilir tutarı) |

---

## 10. Banka Özeti Sayfası

`summary_service` üretir. Farklı para birimleri **asla toplanmaz**; her biri ayrı gösterilir.

| Kart | İçerik |
|---|---|
| TRY / USD / EUR / XAU Bakiye | Her para birimi için aktif hesap toplamı (ayrı) |
| Toplam Hesap Sayısı | Aktif hesap adedi |
| Kredi Kartı Borcu | Güncel ekstre borçları toplamı |
| KMH + Kredi Borcu | Kullanılan KMH + ödenmemiş plan taksitleri toplamı |
| Kullanılabilir Likidite | Nakit + likidite bayraklı kullanılabilir tutarlar |
| Net Finansal Durum | TRY Nakit − TRY Toplam Borç (yalnızca TRY) |

Tek "net servet (TL)" rakamı **ilk sürümde yoktur** — kur tablosu gerektirir, ileride eklenir.

---

## 11. Servis Katmanı Kuralları (iş mantığı)

- Banka silinmeden önce bağlı aktif hesap kontrolü.
- Hesap pasife alınmadan önce bakiye sıfır kontrolü.
- KMH mutlaka bir banka hesabına bağlı.
- Negatif limit girilemez; para birimi ve isim boş bırakılamaz.
- Aynı bankada aynı hesap adı (aktif) tekrar girilemez (kısmi index + service kontrolü).
- Σ(işlem satırları) = işlem toplamı; Σ(taksit bileşenleri) = taksit tutarı.
- `expense`/`cost` satırının niteliği, seçilen kategorinin niteliğiyle uyumlu olmalı.
- Bir debt_plan en az 1 taksit içermeden aktifleştirilemez.
- Bakiye sıfırın altına düşüren hareket: ilk sürümde **uyarı**, ileride zorunlu kılınabilir.

---

## 12. Event Bus

`core/event_bus.py` baştan yazılır, ilk sürümde basit. Planlanan olaylar: `account_balance_changed`, `debt_plan_created`, `installment_paid`, `card_statement_added`, `kmh_used`, `transfer_completed`. İlk sürümde kullanılmasa da yeri ayrılır.

---

## 13. Geliştirme Sırası

Her aşama bir öncekinin üstüne çalışan ve test edilmiş bir katman koyar. Test edilmemiş kod büyütülmez.

**Aşama 1 — İskelet.** Klasör yapısı, `main.py`, `MSFluentWindow` tabanlı ana pencere, üst nav (4 modül) + yan navigasyon, Finans→Bankalar boş giriş sayfası. Tema `theme.py`'de merkezî olarak ayarlanır.

**Aşama 2 — Veritabanı + dinamik referans verisi.** `database.py`, `schema.sql`, `PRAGMA`, migration runner, `schema_version`. `currencies`, `categories`, `assets`, `component_types` tabloları + `seed.py`. "Tanımlar" sayfasından bunları ekle/düzenle/sil. *Her şey para birimine bağlı olduğu için bu önce gelir.*

**Aşama 3 — Bankalar + Hesaplar.** `bank_*`, `account_*`. Banka ve hesap ekleme/listeleme/düzenleme; hesap bir bankaya ve bir para birimine bağlı; `current_balance = opening_balance` ataması.

**Aşama 4 — Para Hareketleri (split motoru).** `transaction_*`. İşlem başlığı + satırlar; nitelik + kategori + varlık seçimi; ekleme/düzenleme/soft-delete; bakiye tutarlı güncellenir (§9). Basit gider/masraf/gelir akışı çalışır.

**Aşama 5 — Banka Özeti (gerçek veri, artımlı).** Özet kartlar mevcut modüllerden beslenir. KK/KMH/kredi kartları ilgili aşamalar geldikçe dolar — özet artımlı kurulur.

**Aşama 6 — Borç Omurgası (manuel plan girişi).** `debt_plan_*`. Plan + taksitler + bileşenler manuel girilir (ilk sürümde PDF parse yok). Kalan borç, yaklaşan ödemeler türetilir.

**Aşama 7 — Taksit Ödeme (split + bakiye/borç).** Taksit ödendiğinde §9.4 akışı: niteliğe göre bölünme, hesap düşer, taksit "paid" olur, borç azalır.

**Aşama 8 — Kredi Kartları.** `credit_card_*`, `card_statements`. Dönen ekstre snapshot'ı + kart içi taksitli avansın omurgaya (`source_card_id`) bağlanması. Özete KK borcu eklenir.

**Aşama 9 — KMH / Ek Hesap.** `kmh_*`. Dönen kullanım snapshot'ı; taksitli ek hesap kullanımı omurgaya (`source_kmh_id`) bağlanır.

**Aşama 10 — Transferler (FX).** Hesaplar arası, döviz/altın bozdurma dahil; iki transaction; atomik geri-alma.

**Aşama 11 — Raporlar + reconcile aktivasyonu.** Gider/masraf raporları (kategori ve varlık bazında), aylık faiz yükü, ödeme takvimi; `reconcile` ile drift denetimi; audit görüntüleme.

---

## 14. Yasaklar

- UI dosyasına SQL veya iş kuralı gömmek.
- Modüllerin birbirini doğrudan import etmesi.
- Para tutarını REAL/float olarak saklamak; gösterimde bile float üretmek.
- Sabit `/100` varsayımı (scale kullan).
- Para birimi, kategori, varlık, bileşen tipini **koda gömmek** (hepsi veri).
- Taksit bileşenlerini sabit kolon yapmak (KKDF/BSMV/Fon satırdır).
- Bankanın faizini yeniden hesaplamaya çalışmak (planı sakla).
- Farklı para birimlerini kur olmadan toplamak.
- Türetilebilir alanları (kullanılabilir limit, kalan borç) saklamak.
- Bakiyeyi SQLite transaction dışında güncellemek.
- Hard delete (fiziksel silme).
- `expense`/`cost` ile `principal`/`transfer` satırlarını karıştırıp "ne harcadım"ı bozmak.
- Test edilmemiş kodu büyütmeye devam etmek.

---

## 15. Kritik Mimari Uyarılar (özet)

- **Para:** INTEGER + scale. Sabit /100 yok. XAU dahil her birim dinamik.
- **Omurga:** kredi/taksitli KMH/taksitli avans = tek `debt_plan`. Banka planı saklanır, hesaplanmaz.
- **Bileşen:** kolon değil satır (`installment_components`) → bankalar arası esneklik.
- **Nitelik:** gider/masraf/anapara/transfer; ödeme niteliğe göre bölünür → "ne harcadım" doğru.
- **Dinamik:** para birimi/kategori/varlık/bileşen tipi = kullanıcı verisi.
- **Likidite:** `counts_as_liquidity` bayrağı; KMH evet, kart alışveriş limiti hayır.
- **Bakiye:** hareketler doğruluk kaynağı; `current_balance` cache; `reconcile` baştan yazılır.
- **Soft delete:** `deleted_at IS NULL` standart; benzersizlik kısmi index ile.
- **Transfer:** FX-farkında (from/to amount+currency+rate); iki hareket, atomik.
- **İlk hedef:** çalışan, sağlam iskelet — mükemmel değil.
