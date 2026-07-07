"""
Bu script GitHub Actions tarafından zamanlanmış olarak (hafta içi akşam 20:00 TR saati)
otomatik çalıştırılır. Sonuçlar 'raporlar/' klasörüne CSV olarak kaydedilir ve
Streamlit uygulaması (app.py) bu dosyaları okuyup gösterir.

Otomatik üretilmesini istediğin her (Analiz Türü, Periyot) kombinasyonunu
GOREVLER listesine ekleyebilirsin.
"""
import os
from datetime import datetime

from analiz_motoru import rapor_olustur, period_transformer

RAPOR_KLASORU = "raporlar"
os.makedirs(RAPOR_KLASORU, exist_ok=True)

# Otomatik olarak her çalıştığında üretilecek raporlar
GOREVLER = [
    ("BIST", "1d"),
    ("FON", "1d"),
]

if __name__ == "__main__":
    for secim, period_secim in GOREVLER:
        print(f"[{datetime.now()}] {secim} / {period_secim} raporu üretiliyor...")
        try:
            df = rapor_olustur(secim, period_secim)
        except Exception as e:
            print(f"HATA ({secim}/{period_secim}): {e}")
            continue

        if df is not None and not df.empty:
            dosya_yolu = os.path.join(
                RAPOR_KLASORU, f"{secim}_{period_transformer(period_secim)}_latest.csv"
            )
            df.to_csv(dosya_yolu)
            print(f"Kaydedildi: {dosya_yolu} ({len(df)} satır)")
        else:
            print(f"UYARI: {secim}/{period_secim} için veri üretilemedi, dosya güncellenmedi.")
