"""
Bu script GitHub Actions tarafından çalıştırılır:
- Zamanlanmış (cron) çalışmada: aşağıdaki GOREVLER listesindeki tüm kombinasyonları üretir.
- Manuel tetiklemede ("Run workflow" ile SECIM/PERIYOT seçildiğinde): sadece o tek kombinasyonu üretir.

Sonuçlar 'raporlar/' klasörüne CSV olarak kaydedilir (en güncel hali) ve
ayrıca 'raporlar/gecmis/' klasörüne tarihli olarak eklenir (geçmiş takibi için).
Streamlit uygulaması (app.py) bu dosyaları okuyup gösterir.
"""
import os
from datetime import datetime

import pandas as pd

from analiz_motoru import rapor_olustur, period_transformer

RAPOR_KLASORU = "raporlar"
GECMIS_KLASORU = os.path.join(RAPOR_KLASORU, "gecmis")
os.makedirs(RAPOR_KLASORU, exist_ok=True)
os.makedirs(GECMIS_KLASORU, exist_ok=True)

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


def kaydet_ve_gecmis(df, secim, period_secim):
    """Güncel raporu kaydeder ve ayrıca tarihli 'geçmiş' dosyasına ekler."""
    isim_koku = f"{secim}_{period_transformer(period_secim)}"
    tarih = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 1) En güncel hali (Streamlit varsayılan olarak bunu gösterir)
    latest_yol = os.path.join(RAPOR_KLASORU, f"{isim_koku}_latest.csv")
    df.to_csv(latest_yol)

    # 2) Geçmiş dosyasına ekle (Tarih sütunuyla birlikte)
    df_yeni = df.reset_index().copy()
    df_yeni.insert(0, "Tarih", tarih)

    gecmis_yol = os.path.join(GECMIS_KLASORU, f"{isim_koku}_gecmis.csv")
    if os.path.exists(gecmis_yol):
        df_eski = pd.read_csv(gecmis_yol)
        df_birlesik = pd.concat([df_eski, df_yeni], ignore_index=True)
    else:
        df_birlesik = df_yeni

    df_birlesik.to_csv(gecmis_yol, index=False)
    print(f"Geçmişe eklendi: {gecmis_yol} (toplam {len(df_birlesik)} satır)")


if __name__ == "__main__":
    for secim, period_secim in gorevleri_belirle():
        print(f"[{datetime.now()}] {secim} / {period_secim} raporu üretiliyor...")
        try:
            df = rapor_olustur(secim, period_secim)
        except Exception as e:
            print(f"HATA ({secim}/{period_secim}): {e}")
            continue

        if df is not None and not df.empty:
            kaydet_ve_gecmis(df, secim, period_secim)
            print(f"Kaydedildi ({len(df)} satır)")
        else:
            print(f"UYARI: {secim}/{period_secim} için veri üretilemedi, dosya güncellenmedi.")
