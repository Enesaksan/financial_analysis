import os
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from analiz_motoru import rapor_olustur, period_transformer, tekil_analiz

TR_TZ = ZoneInfo("Europe/Istanbul")

st.set_page_config(page_title="Hisse & Fon Analiz Raporu", layout="wide")

RAPOR_KLASORU = "raporlar"
os.makedirs(RAPOR_KLASORU, exist_ok=True)

st.title("Hisse & Fon Analiz Raporu")

col1, col2 = st.columns(2)
with col1:
    secim = st.selectbox("Analiz Turu", ["BIST", "FON", "ABD"])
with col2:
    period_secim = st.selectbox(
        "Periyot",
        ["1d", "1wk"],
        index=0,
        help="1d: Gunluk, 1wk: Haftalik",
    )


def rapor_dosya_yolu(secim, period_secim):
    return os.path.join(RAPOR_KLASORU, f"{secim}_{period_transformer(period_secim)}_latest.csv")


def gun_ici_mi(saat_dt):
    """BIST seans saatleri (10:00-18:00 TR) icinde mi, yoksa kapanis sonrasi mi?"""
    return 10 <= saat_dt.hour < 18 and saat_dt.weekday() < 5


manuel_uret = st.button("Raporu Simdi Uret (Canli Veri)", type="primary")

if manuel_uret:
    with st.spinner("Veriler Yahoo Finance'den cekiliyor, analiz yapiliyor... Bu biraz surebilir."):
        df = rapor_olustur(secim, period_secim)
    if df is not None and not df.empty:
        simdi = datetime.now(TR_TZ)
        st.success(f"Rapor uretildi - {simdi.strftime('%d.%m.%Y %H:%M')}")
        st.session_state["son_rapor"] = df
        st.session_state["son_rapor_secim"] = (secim, period_secim)
        st.session_state["son_rapor_zaman"] = simdi
    else:
        st.error("Rapor uretilemedi. Excel dosyasini/ticker listesini ya da baglantiyi kontrol edin.")

df_goster = None
kaynak = ""
zaman_dt = None

if "son_rapor" in st.session_state and st.session_state.get("son_rapor_secim") == (secim, period_secim):
    df_goster = st.session_state["son_rapor"]
    zaman_dt = st.session_state["son_rapor_zaman"]
    kaynak = "Canli (az once uretildi)"
else:
    dosya_yolu = rapor_dosya_yolu(secim, period_secim)
    if os.path.exists(dosya_yolu):
        df_goster = pd.read_csv(dosya_yolu, index_col=0)
        zaman_dt = datetime.fromtimestamp(os.path.getmtime(dosya_yolu), tz=TR_TZ)
        kaynak = f"Otomatik rapor ({zaman_dt.strftime('%d.%m.%Y %H:%M')})"

if df_goster is not None:
    st.caption(f"Gosterilen veri kaynagi: {kaynak}")

    if period_secim == "1d" and zaman_dt is not None:
        if gun_ici_mi(zaman_dt):
            st.warning(
                "Gun Ici (kapanis kesinlesmedi) - bu rapor, gunun henuz tamamlanmamis "
                "anlik fiyatlarina gore uretildi. Sinyaller gunun kapanisina kadar degisebilir."
            )
        else:
            st.success("Kapanis (Kesin) - bu rapor, gunun tamamlanmis kapanis verisine gore uretildi.")

    with st.expander("Filtrele", expanded=False):
        df_filtreli = df_goster.copy()

        arama = st.text_input("Varlik ara (orn: THYAO)", "")
        if arama:
            df_filtreli = df_filtreli[df_filtreli.index.str.contains(arama, case=False, na=False)]

        sinyal_sutunlari = [
            "Supertrend_Sinyal", "Tilson_Sinyal", "Hacim_SMI",
            "Kombine_Dip", "SSL&EMA_Sinyal", "BB_Sikisma","BB_Fiyat_Durum"
        ]
        secili_sutunlar = st.multiselect(
            "Filtrelemek istedigin sinyal sutunlari",
            [s for s in sinyal_sutunlari if s in df_filtreli.columns],
        )
        for sutun in secili_sutunlar:
            secenekler = sorted(df_filtreli[sutun].dropna().unique().tolist())
            secim_degerleri = st.multiselect(f"-> {sutun}", secenekler, key=f"filtre_{sutun}")
            if secim_degerleri:
                df_filtreli = df_filtreli[df_filtreli[sutun].isin(secim_degerleri)]

        sayisal_sutunlar = [c for c in ["RSI", "StochRSI", "TSI"] if c in df_filtreli.columns]
        secili_sayisal = st.multiselect("Aralik ile filtrelemek istedigin sayisal sutunlar", sayisal_sutunlar)
        for sutun in secili_sayisal:
            min_deger = float(df_goster[sutun].min())
            max_deger = float(df_goster[sutun].max())
            secili_aralik = st.slider(
                f"-> {sutun} araligi", min_value=min_deger, max_value=max_deger,
                value=(min_deger, max_deger), key=f"slider_{sutun}",
            )
            df_filtreli = df_filtreli[
                (df_filtreli[sutun] >= secili_aralik[0]) & (df_filtreli[sutun] <= secili_aralik[1])
            ]

    st.caption(f"Gosterilen satir sayisi: {len(df_filtreli)} / {len(df_goster)}")
    st.dataframe(df_filtreli, use_container_width=True)

    buffer = io.BytesIO()
    df_filtreli.to_excel(buffer)
    st.download_button(
        "Filtrelenmis Tabloyu Excel Olarak Indir",
        data=buffer.getvalue(),
        file_name=f"{secim}_{period_transformer(period_secim)}_rapor.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.info(
        "Bu kombinasyon (Analiz Turu + Periyot) icin henuz bir rapor yok. "
        "Yukaridaki butona basarak hemen uretebilir, ya da otomatik zamanlanmis "
        "raporun olusmasini bekleyebilirsin."
    )

# =====================================================================
# TEKIL HISSE ANALIZI
# =====================================================================
st.divider()
st.subheader("Tekil Hisse/Varlik Analizi")
st.caption("Listede olmayan ya da anlik olarak bakmak istedigin tek bir sembolu buradan sorgulayabilirsin.")

tk_col1, tk_col2, tk_col3, tk_col4 = st.columns([2, 1, 1, 1])
with tk_col1:
    tekil_kod = st.text_input("Sembol (orn: ASELS, AAPL, GC=F)", "")
with tk_col2:
    tekil_market = st.selectbox("Piyasa", ["BIST", "ABD", "Ham Ticker"])
with tk_col3:
    tekil_periyot = st.selectbox("Periyot ", ["1d", "1wk"], key="tekil_periyot")
with tk_col4:
    st.write("")
    st.write("")
    tekil_buton = st.button("Analiz Et")

if tekil_buton and tekil_kod.strip():
    market_map = {"BIST": "BIST", "ABD": "ABD", "Ham Ticker": "HAM"}
    with st.spinner(f"{tekil_kod.upper()} icin veri cekiliyor..."):
        tekil_df = tekil_analiz(tekil_kod, market_tipi=market_map[tekil_market], period_selection=tekil_periyot)

    if tekil_df is not None and not tekil_df.empty:
        st.dataframe(tekil_df, use_container_width=True)
    else:
        st.error(
            f"'{tekil_kod}' icin veri bulunamadi. Sembolu ve piyasa secimini kontrol et "
            "(BIST icin sadece kod yeterli, orn ASELS; ABD icin Yahoo sembolu, orn AAPL; "
            "fon/emtia/doviz icin 'Ham Ticker' secip tam Yahoo sembolunu yaz, orn GC=F)."
        )

# =====================================================================
# GECMIS TAKIBI
# =====================================================================
st.divider()
st.subheader("Gecmis")

gecmis_yolu = os.path.join(
    RAPOR_KLASORU, "gecmis", f"{secim}_{period_transformer(period_secim)}_gecmis.csv"
)

if not os.path.exists(gecmis_yolu):
    st.caption(
        "Bu kombinasyon icin henuz gecmis kaydi yok. Otomatik rapor birkac kez "
        "calistiktan sonra burada gecmis sinyalleri gorebileceksin."
    )
else:
    df_gecmis = pd.read_csv(gecmis_yolu)

    varliklar = sorted(df_gecmis["Varlık"].dropna().unique().tolist())
    secili_varlik = st.selectbox("Bir varlik sec", varliklar)

    df_varlik_gecmis = df_gecmis[df_gecmis["Varlık"] == secili_varlik].sort_values("Tarih")

    st.caption(f"{secili_varlik} icin kayitli gecmis ({len(df_varlik_gecmis)} kayit)")
    st.dataframe(
        df_varlik_gecmis.set_index("Tarih"),
        use_container_width=True,
    )

    grafik_sutunlari = [c for c in ["Fiyat", "RSI"] if c in df_varlik_gecmis.columns]
    if len(df_varlik_gecmis) > 1 and grafik_sutunlari:
        st.line_chart(
            df_varlik_gecmis.set_index("Tarih")[grafik_sutunlari],
            use_container_width=True,
        )
