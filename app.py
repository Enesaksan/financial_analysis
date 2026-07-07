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
    st.dataframe(df_goster, use_container_width=True)

    buffer = io.BytesIO()
    df_goster.to_excel(buffer)
    st.download_button(
        "⬇️ Excel Olarak İndir",
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
