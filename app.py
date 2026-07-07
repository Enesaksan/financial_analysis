import os
import io
from datetime import datetime

import pandas as pd
import streamlit as st

from analiz_motoru import rapor_olustur, period_transformer

st.set_page_config(page_title="Hisse & Fon Analiz Raporu", layout="wide")

RAPOR_KLASORU = "raporlar"
os.makedirs(RAPOR_KLASORU, exist_ok=True)

st.title("📊 Hisse & Fon Analiz Raporu")

col1, col2 = st.columns(2)
with col1:
    secim = st.selectbox("Analiz Türü", ["BIST", "FON"])
with col2:
    period_secim = st.selectbox(
        "Periyot",
        ["1d", "1wk", "1mo", "1h", "2h", "4h"],
        index=0,
        help="1d: Günlük, 1wk: Haftalık, 1mo: Aylık, 1h/2h/4h: Saatlik",
    )


def rapor_dosya_yolu(secim, period_secim):
    return os.path.join(RAPOR_KLASORU, f"{secim}_{period_transformer(period_secim)}_latest.csv")


manuel_uret = st.button("🔄 Raporu Şimdi Üret (Canlı Veri)", type="primary")

if manuel_uret:
    with st.spinner("Veriler Yahoo Finance'den çekiliyor, analiz yapılıyor... Bu biraz sürebilir."):
        df = rapor_olustur(secim, period_secim)
    if df is not None and not df.empty:
        st.success(f"Rapor üretildi — {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        st.session_state["son_rapor"] = df
        st.session_state["son_rapor_secim"] = (secim, period_secim)
    else:
        st.error("Rapor üretilemedi. Ticker listesini ya da bağlantıyı kontrol edin.")

# Gösterilecek veri: önce bu oturumda manuel üretileni, yoksa otomatik/zamanlanmış son raporu göster
df_goster = None
kaynak = ""

if "son_rapor" in st.session_state and st.session_state.get("son_rapor_secim") == (secim, period_secim):
    df_goster = st.session_state["son_rapor"]
    kaynak = "🟢 Canlı (az önce üretildi)"
else:
    dosya_yolu = rapor_dosya_yolu(secim, period_secim)
    if os.path.exists(dosya_yolu):
        df_goster = pd.read_csv(dosya_yolu, index_col=0)
        zaman = datetime.fromtimestamp(os.path.getmtime(dosya_yolu)).strftime('%d.%m.%Y %H:%M')
        kaynak = f"🕗 Otomatik rapor ({zaman})"

if df_goster is not None:
    st.caption(f"Gösterilen veri kaynağı: {kaynak}")

    with st.expander("🔍 Filtrele", expanded=False):
        df_filtreli = df_goster.copy()

        # Varlık adında arama
        arama = st.text_input("Varlık ara (örn: THYAO)", "")
        if arama:
            df_filtreli = df_filtreli[df_filtreli.index.str.contains(arama, case=False, na=False)]

        # Sinyal sütunları için çoklu seçim filtreleri
        sinyal_sutunlari = [
            "Supertrend_Sinyal", "Tilson_Sinyal", "Hacim_SMI",
            "Kombine_Dip", "SSL&EMA_Sinyal", "EMA_Sikisma",
        ]
        secili_sutunlar = st.multiselect(
            "Filtrelemek istediğin sinyal sütunları",
            [s for s in sinyal_sutunlari if s in df_filtreli.columns],
        )
        for sutun in secili_sutunlar:
            secenekler = sorted(df_filtreli[sutun].dropna().unique().tolist())
            secim_degerleri = st.multiselect(f"→ {sutun}", secenekler, key=f"filtre_{sutun}")
            if secim_degerleri:
                df_filtreli = df_filtreli[df_filtreli[sutun].isin(secim_degerleri)]

        # Sayısal sütunlar için aralık filtresi (RSI, StochRSI, TSI)
        sayisal_sutunlar = [c for c in ["RSI", "StochRSI", "TSI"] if c in df_filtreli.columns]
        secili_sayisal = st.multiselect("Aralık ile filtrelemek istediğin sayısal sütunlar", sayisal_sutunlar)
        for sutun in secili_sayisal:
            min_deger = float(df_goster[sutun].min())
            max_deger = float(df_goster[sutun].max())
            secili_aralik = st.slider(
                f"→ {sutun} aralığı", min_value=min_deger, max_value=max_deger,
                value=(min_deger, max_deger), key=f"slider_{sutun}",
            )
            df_filtreli = df_filtreli[
                (df_filtreli[sutun] >= secili_aralik[0]) & (df_filtreli[sutun] <= secili_aralik[1])
            ]

    st.caption(f"Gösterilen satır sayısı: {len(df_filtreli)} / {len(df_goster)}")
    st.dataframe(df_filtreli, use_container_width=True)

    buffer = io.BytesIO()
    df_filtreli.to_excel(buffer)
    st.download_button(
        "⬇️ Filtrelenmiş Tabloyu Excel Olarak İndir",
        data=buffer.getvalue(),
        file_name=f"{secim}_{period_transformer(period_secim)}_rapor.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.info(
        "Bu kombinasyon (Analiz Türü + Periyot) için henüz bir rapor yok. "
        "Yukarıdaki butona basarak hemen üretebilir, ya da otomatik zamanlanmış "
        "raporun (hafta içi 20:00) oluşmasını bekleyebilirsin."
    )

# =====================================================================
# GEÇMİŞ TAKİBİ
# =====================================================================
st.divider()
st.subheader("📜 Geçmiş")

gecmis_yolu = os.path.join(
    RAPOR_KLASORU, "gecmis", f"{secim}_{period_transformer(period_secim)}_gecmis.csv"
)

if not os.path.exists(gecmis_yolu):
    st.caption(
        "Bu kombinasyon için henüz geçmiş kaydı yok. Otomatik rapor birkaç kez "
        "çalıştıktan sonra burada geçmiş sinyalleri görebileceksin."
    )
else:
    df_gecmis = pd.read_csv(gecmis_yolu)

    varliklar = sorted(df_gecmis["Varlık"].dropna().unique().tolist())
    secili_varlik = st.selectbox("Bir varlık seç", varliklar)

    df_varlik_gecmis = df_gecmis[df_gecmis["Varlık"] == secili_varlik].sort_values("Tarih")

    st.caption(f"{secili_varlik} için kayıtlı geçmiş ({len(df_varlik_gecmis)} kayıt)")
    st.dataframe(
        df_varlik_gecmis.set_index("Tarih"),
        use_container_width=True,
    )

    # Fiyat ve RSI'ın zaman içindeki değişimi (varsa)
    grafik_sutunlari = [c for c in ["Fiyat", "RSI"] if c in df_varlik_gecmis.columns]
    if len(df_varlik_gecmis) > 1 and grafik_sutunlari:
        st.line_chart(
            df_varlik_gecmis.set_index("Tarih")[grafik_sutunlari],
            use_container_width=True,
        )
