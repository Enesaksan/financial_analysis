"""
Bu script GitHub Actions tarafından çalıştırılır:
- Zamanlanmış (cron) çalışmada: aşağıdaki GOREVLER listesindeki tüm kombinasyonları üretir.
- Manuel tetiklemede ("Run workflow" ile SECIM/PERIYOT seçildiğinde): sadece o tek kombinasyonu üretir.

Sonuçlar 'raporlar/' klasörüne CSV olarak kaydedilir ve
Streamlit uygulaması (app.py) bu dosyaları okuyup gösterir.
"""
import os
from datetime import datetime

from analiz_motoru import rapor_olustur, period_transformer

RAPOR_KLASORU = "raporlar"
os.makedirs(RAPOR_KLASORU, exist_ok=True)

# Zamanlanmış (otomatik) çalışmada üretilecek raporlar
GOREVLER_VARSAYILAN = [
    ("BIST", "1d"),
    ("FON", "1d"),
]


def gorevleri_belirle():
    secim = os.environ.get("SECIM", "").strip().upper()
    periyot = os.environ.get("PERIYOT", "").strip()

    # Manuel tetikleme ile bir seçim geldiyse (workflow_dispatch)
    if secim and periyot:
        if secim == "HER IKISI":
            return [("BIST", periyot), ("FON", periyot)]
        return [(secim, periyot)]

    # Aksi halde (cron ile otomatik çalışma) sabit listeyi kullan
    return GOREVLER_VARSAYILAN


if __name__ == "__main__":
    for secim, period_secim in gorevleri_belirle():
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
