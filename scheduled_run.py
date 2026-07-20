import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from analiz_motoru import rapor_olustur, period_transformer

TR_TZ = ZoneInfo("Europe/Istanbul")

RAPOR_KLASORU = "raporlar"
GECMIS_KLASORU = os.path.join(RAPOR_KLASORU, "gecmis")
os.makedirs(RAPOR_KLASORU, exist_ok=True)
os.makedirs(GECMIS_KLASORU, exist_ok=True)

# Haftalık analizi tetikleyen cron ifadesi (workflow dosyasındaki ile birebir aynı olmalı)
HAFTALIK_CRON = "30 17 * * 5"

# Zamanlanmış (otomatik) çalışmalarda üretilecek raporlar
GOREVLER_GUNLUK = [
    ("BIST", "1d"),
    ("BIST FAVORILER","1d"),
    ("FON", "1d"),
    ("ABD", "1d")
]
GOREVLER_HAFTALIK = [
    ("BIST", "1wk"),
    ("BIST FAVORILER","1wk"),
    ("FON", "1wk"),
    ("ABD", "1wk")
]


def gorevleri_belirle():
    secim = os.environ.get("SECIM", "").strip().upper()
    periyot = os.environ.get("PERIYOT", "").strip()

    if secim and periyot:
        if secim == "HEPSI":
            return [("BIST", periyot),("BIST FAVORILER", periyot), ("FON", periyot), ("ABD", periyot)]
        return [(secim, periyot)]

    cron_ifadesi = os.environ.get("GITHUB_SCHEDULE", "").strip()
    if cron_ifadesi == HAFTALIK_CRON:
        return GOREVLER_HAFTALIK
    return GOREVLER_GUNLUK


def kaydet_ve_gecmis(df, secim, period_secim):
    ek="_BIST_TUM" if secim=="BIST" else ""
    isim_koku = f"{secim}{ek}_{period_transformer(period_secim)}"
    tarih = datetime.now(TR_TZ).strftime("%Y-%m-%d %H:%M")

    latest_yol = os.path.join(RAPOR_KLASORU, f"{isim_koku}_latest.csv")
    df.to_csv(latest_yol)

    # Gerçek üretim zamanını AYRICA küçük bir dosyaya yaz. Dosyanın işletim
    # sistemi seviyesindeki değiştirilme zamanına (mtime) güvenilemez, çünkü
    # Streamlit Cloud repo'yu yeniden clone'ladığında mtime'lar clone anına
    # sıfırlanıyor — gerçek üretim zamanını yansıtmıyor.
    zaman_yolu = os.path.join(RAPOR_KLASORU, f"{isim_koku}_latest_zaman.txt")
    with open(zaman_yolu, "w") as f:
        f.write(tarih)

    df_yeni = df.reset_index().copy()
    df_yeni.insert(0, "Tarih", tarih)

    gecmis_yol = os.path.join(GECMIS_KLASORU, f"{isim_koku}_gecmis.csv")
    if os.path.exists(gecmis_yol):
        df_eski = pd.read_csv(gecmis_yol)
        df_birlesik = pd.concat([df_eski, df_yeni], ignore_index=True)
    else:
        df_birlesik = df_yeni

    df_birlesik.to_csv(gecmis_yol, index=False)
    print(f"Gecmise eklendi: {gecmis_yol} (toplam {len(df_birlesik)} satir)", flush=True)


if __name__ == "__main__":
    for secim, period_secim in gorevleri_belirle():
        print(f"[{datetime.now(TR_TZ).strftime('%Y-%m-%d %H:%M:%S')}] {secim} / {period_secim} raporu uretiliyor...", flush=True)
        try:
            df = rapor_olustur(secim, period_secim)
        except Exception as e:
            print(f"HATA ({secim}/{period_secim}): {e}", flush=True)
            continue

        if df is not None and not df.empty:
            kaydet_ve_gecmis(df, secim, period_secim)
            print(f"Kaydedildi ({len(df)} satir)", flush=True)
        else:
            print(f"UYARI: {secim}/{period_secim} icin veri uretilemedi, dosya guncellenmedi.", flush=True)
