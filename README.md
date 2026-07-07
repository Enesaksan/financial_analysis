# Hisse & Fon Analiz Raporu — Otomatik + Online

## Yapı

```
├── analiz_motoru.py       # Tüm analiz mantığı (senin orijinal kodun, fonksiyon bazlı)
├── app.py                 # Streamlit web arayüzü (buton + tablo + Excel indirme)
├── scheduled_run.py        # GitHub Actions'ın hafta içi 20:00'de çalıştırdığı script
├── requirements.txt
├── data/
│   └── hisse_senetleri.xlsx   # BIST hisse kod listen (BURAYA senin dosyan gelecek)
├── raporlar/                  # Otomatik üretilen rapor CSV'leri (kod tarafından oluşturulur)
└── .github/workflows/rapor.yml  # Zamanlama tanımı
```

## Kurulum Adımları

### 1) GitHub reposu oluştur
- github.com üzerinde yeni bir repo aç (public ya da private, ikisi de olur).
- Bu klasördeki tüm dosyaları o repoya yükle (GitHub web arayüzünden sürükle-bırak ile de olur).

### 2) Hisse listeni ekle
- Kendi `hisse_senetleri.xlsx` dosyanı `data/` klasörünün içine koy.
- `Sirket` adında bir sütun olduğundan emin ol (kod bunu arıyor, yoksa ilk sütunu kullanıyor).

### 3) GitHub Actions'ı doğrula
- Repo ayarlarında **Settings → Actions → General → Workflow permissions** kısmından
  "Read and write permissions" seçeneğinin açık olduğundan emin ol
  (script'in `raporlar/` klasörüne otomatik commit atabilmesi için gerekli).
- **Actions** sekmesine gidip **"Otomatik Analiz Raporu"** iş akışını bul,
  sağdan **"Run workflow"** ile bir kere manuel çalıştır — ilk raporun hemen üretilsin.
- Sonrasında hafta içi her akşam TR saati 20:00'de otomatik çalışacak.

### 4) Streamlit Cloud'a deploy et
- share.streamlit.io adresine git, GitHub hesabınla giriş yap.
- "New app" → reponu seç → ana dosya olarak `app.py`'yi göster → Deploy.
- Birkaç dakika içinde sana özel bir link verecek (örn: `senin-uygulaman.streamlit.app`).
- Bu linki istediğin herkesle paylaşabilirsin — mobil tarayıcıdan da sorunsuz açılır.

## Kullanım

- **Manuel/anlık rapor:** Uygulamayı aç, Analiz Türü (BIST/FON) ve Periyodu seç,
  "🔄 Raporu Şimdi Üret" butonuna bas. O an Yahoo Finance'den canlı veri çekilir.
- **Otomatik rapor:** Hiçbir şey yapmasan da, hafta içi her akşam 20:00'de
  GitHub Actions arka planda raporu üretip repoya kaydeder. Uygulamayı açtığında
  bu son otomatik raporu görürsün ("🕗 Otomatik rapor (tarih saat)" etiketiyle).
- **Excel indirme:** Ekrandaki tabloyu "⬇️ Excel Olarak İndir" butonu ile
  `.xlsx` olarak indirebilirsin.

## Notlar

- `scheduled_run.py` içindeki `GOREVLER` listesine istediğin kadar
  (Analiz Türü, Periyot) kombinasyonu ekleyebilirsin — her biri otomatik
  olarak ayrı bir CSV'ye kaydedilir.
- Cron saatini değiştirmek istersen `.github/workflows/rapor.yml` içindeki
  `cron: '0 17 * * 1-5'` satırını düzenle (saat UTC cinsindendir,
  Türkiye şu an UTC+3, yaz-kış saati uygulaması yok).
- Repo'yu **public** yaparsan Streamlit Cloud ücretsiz planında sorunsuz çalışır.
  Private repo da Streamlit Cloud ile bağlanabilir, sadece GitHub hesabı yetkilendirmesi ister.
