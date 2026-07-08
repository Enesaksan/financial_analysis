import yfinance as yf
import pandas as pd
import pandas_ta_classic as ta
import warnings
import numpy as np
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings('ignore')
# yfinance'in "possibly delisted" / "no timezone found" gibi gürültülü konsol
# çıktılarını sustur — bu hatalar zaten aşağıda kontrollü şekilde ele alınıyor.
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# =====================================================================
# 0. HİSSE / FON LİSTELERİ
# =====================================================================

FON_TICKERS = {
    # ── Teknoloji / Yarı İletken ──────────────────────
    "Nasdaq 100": "QQQ",
    "Yarı İletken (SOX)": "SOXX",
    "Yapay Zeka (AIQ)": "AIQ",

    # ── Sağlık / Biyoteknoloji ────────────────────────
    "Sağlık Genel (XLV)": "XLV",
    "Biyoteknoloji (XBI)": "XBI",
    "Biyoteknoloji Büyük (IBB)": "IBB",

    # ── Nükleer / Enerji ──────────────────────────────
    "Uranyum ETF (URA)": "URA",
    "Cameco": "CCJ",
    "Uranyum Spot (vadeli yok — CCJ proxy)": "CCJ",
    "Temiz Enerji (ICLN)": "ICLN",

    # ── Su ───────────────────────────────────────────
    "Su (PHO)": "PHO",
    "Su (CGW)": "CGW",

    # ── Emtia Genel ───────────────────────────────────
    "Emtia Sepeti (DJP)": "DJP",
    "Emtia Sepeti (PDBC)": "PDBC",

    # ── Kıymetli Madenler ─────────────────────────────
    "Altın Spot": "GC=F",
    "Altın ETF (GLD)": "GLD",
    "Gümüş Spot": "SI=F",
    "Gümüş ETF (SLV)": "SLV",
    "Platin": "PL=F",
    "Paladyum": "PA=F",

    # ── Endüstriyel Metaller ──────────────────────────
    "Bakır Spot": "HG=F",
    "Bakır ETF (COPA)": "COPA",
    "Alüminyum (ALUM — London)": "ALUM.L",
    "Nikel Vadeli": "NI=F",

    # ── Tarım / Gıda ──────────────────────────────────
    "Tarım Sepeti (DBA)": "DBA",
    "Agribusiness (MOO)": "MOO",
    "Buğday Vadeli": "ZW=F",
    "Mısır Vadeli": "ZC=F",
    "Soya Vadeli": "ZS=F",
    "Kakao Vadeli": "CC=F",
    "Kahve Vadeli": "KC=F",
    "Şeker Vadeli": "SB=F",

    # ── Petrol / Doğal Gaz ────────────────────────────
    "Brent Ham Petrol": "BZ=F",
    "WTI Ham Petrol": "CL=F",
    "Doğal Gaz": "NG=F",

    # ── Geniş Pazar / GEP ─────────────────────────────
    "S&P 500": "SPY",
    "Russell 2000": "IWM",
    "Gelişmekte Olan Ülkeler (EEM)": "EEM",
    "Hindistan (INDA)": "INDA",

    # ── BIST ──────────────────────────────────────────
    "BIST 100": "XU100.IS",
    "BIST 30": "XU030.IS",

    # ── Döviz ─────────────────────────────────────────
    "USD/TRY": "USDTRY=X",
    "EUR/TRY": "EURTRY=X",
}


def bist_hisseleri_excel(dosya_adi="data/hisse_senetleri.xlsx"):
    """
    BIST hisse kodlarını içeren Excel dosyasını okur.
    Bu dosyanın repo içinde 'data/hisse_senetleri.xlsx' yolunda bulunması gerekir.
    """
    print(f"'{dosya_adi}' dosyasından hisseler okunuyor...\n")
    gecici_liste = []

    try:
        df = pd.read_excel(dosya_adi)
    except FileNotFoundError:
        print(f"HATA: Dosya bulunamadı. Yolu kontrol edin: {dosya_adi}")
        return {}

    kod_sutunu = 'Sirket' if 'Sirket' in df.columns else df.columns[0]

    for kod in df[kod_sutunu]:
        if pd.notna(kod):
            kod = str(kod).strip().upper()
            gecici_liste.append(kod)

    unique_keys = set(gecici_liste)
    sirali_kodlar = sorted(unique_keys)
    bist_tickers = {kod: f"{kod}.IS" for kod in sirali_kodlar}

    print(f"İşlem Başarılı! Toplam {len(bist_tickers)} adet benzersiz hisse analize hazır.\n")
    return bist_tickers


def get_tickers(secim: str, hisse_dosyasi: str = "data/hisse_senetleri.xlsx"):
    """
    secim: "BIST" ya da "FON"
    return: (tickers_dict, auto_adjust_bool)
    """
    secim = secim.upper().strip()
    if secim == "BIST":
        return bist_hisseleri_excel(hisse_dosyasi), True
    elif secim == "FON":
        return FON_TICKERS, False
    else:
        raise ValueError("Seçim 'BIST' ya da 'FON' olmalı.")


def period_transformer(period_selection):
    match period_selection:
        case "1d":
            return "Daily"
        case "1wk":
            return "Weekly"
        case "1mo":
            return "Montly"
        case "1h":
            return "1_hour"
        case "2h":
            return "2_hour"
        case "4h":
            return "4_hour"
        case _:
            return "Special_selection"


# =====================================================================
# 1. ÖZEL İNDİKATÖR FONKSİYONLARI
# =====================================================================
def hesapla_orijinal_smi(df, n=10, n_ema1=3, n_ema2=3, n_signal=3):
    try:
        hh = df['High'].rolling(window=n).max()
        ll = df['Low'].rolling(window=n).min()
        midpoint = (hh + ll) / 2
        D = df['Close'] - midpoint
        HL = hh - ll

        D_ema1 = D.ewm(span=n_ema1, adjust=False).mean()
        D_ema2 = D_ema1.ewm(span=n_ema2, adjust=False).mean()
        HL_ema1 = HL.ewm(span=n_ema1, adjust=False).mean()
        HL_ema2 = HL_ema1.ewm(span=n_ema2, adjust=False).mean()

        smi_degeri = 100 * (D_ema2 / (HL_ema2 / 2))
        smi_sinyal = smi_degeri.ewm(span=n_signal, adjust=False).mean()

        df['SMI'] = smi_degeri
        df['SMIs'] = smi_sinyal
    except Exception:
        pass
    return df


def hesapla_tilson_t3(df, length=4, b=0.7):
    try:
        c1 = -(b**3)
        c2 = 3*(b**2) + 3*(b**3)
        c3 = -6*(b**2) - 3*b - 3*(b**3)
        c4 = 1 + 3*b + (b**3) + 3*(b**2)

        def ema(seri, periyot):
            return seri.ewm(span=periyot, adjust=False).mean()

        e1 = ema(df['Close'], length); e2 = ema(e1, length); e3 = ema(e2, length)
        e4 = ema(e3, length); e5 = ema(e4, length); e6 = ema(e5, length)
        df['TILSON_T3'] = c1 * e6 + c2 * e5 + c3 * e4 + c4 * e3
    except Exception:
        pass
    return df


def hesapla_trend_strength_index(df, length=14):
    try:
        bar_index = pd.Series(np.arange(len(df)), index=df.index)
        trend_strength = df['Close'].rolling(window=length).corr(bar_index)
        df['TSI'] = trend_strength
    except Exception:
        pass
    return df


def hesapla_ssl_hybrid(df, base_len=60, exit_len=15):
    try:
        # ---------------------------------------------
        # 1. BASELINE HESAPLAMASI (Ana Trend - HMA 60)
        # ---------------------------------------------
        baseline = ta.hma(df['Close'], length=base_len)
        tr = ta.true_range(df['High'], df['Low'], df['Close'])
        rangema = ta.ema(tr, length=base_len)

        upperk = baseline + rangema * 0.2
        lowerk = baseline - rangema * 0.2

        base_trend = pd.Series(np.nan, index=df.index)
        base_trend.loc[df['Close'] > upperk] = 1
        base_trend.loc[df['Close'] < lowerk] = -1
        base_trend = base_trend.ffill().fillna(0)

        df['SSL_BASE_TREND'] = base_trend
        df['SSL_BASELINE'] = baseline

        # ---------------------------------------------
        # 2. EXIT ARROWS HESAPLAMASI (SSL3 - HMA 15)
        # ---------------------------------------------
        exit_high = ta.hma(df['High'], length=exit_len)
        exit_low = ta.hma(df['Low'], length=exit_len)

        hlv3 = pd.Series(np.nan, index=df.index)
        hlv3.loc[df['Close'] > exit_high] = 1
        hlv3.loc[df['Close'] < exit_low] = -1
        hlv3 = hlv3.ffill().fillna(1)

        ssl_exit = np.where(hlv3 < 0, exit_high, exit_low)
        df['SSL_EXIT_LINE'] = pd.Series(ssl_exit, index=df.index)

        onceki_kapanis = df['Close'].shift(1)
        onceki_exit = df['SSL_EXIT_LINE'].shift(1)

        cross_up = (onceki_kapanis <= onceki_exit) & (df['Close'] > df['SSL_EXIT_LINE'])
        cross_down = (onceki_kapanis >= onceki_exit) & (df['Close'] < df['SSL_EXIT_LINE'])

        exit_signal = pd.Series(0, index=df.index)
        exit_signal.loc[cross_up] = 1
        exit_signal.loc[cross_down] = -1

        df['SSL_EXIT_SIGNAL'] = exit_signal

    except Exception:
        pass

    return df


# =====================================================================
# 2. VERİ İNDİRME VE İNDİKATÖR MOTORU
# =====================================================================
def _indikatorler_ekle(df):
    """Ham OHLCV verisine tüm teknik indikatörleri ekler (indirme işleminden bağımsız)."""
    if df is None or df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    df['RSI'] = ta.rsi(df['Close'], length=14)

    bbands = ta.bbands(df['Close'], length=20, std=2)

    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['EMA_100'] = ta.ema(df['Close'], length=100)
    df['EMA_150'] = ta.ema(df['Close'], length=150)

    if bbands is not None and not bbands.empty:
        df['BB_ALT'] = bbands.iloc[:, 0]
        df['BB_UST'] = bbands.iloc[:, 2]

    stoch = ta.stochrsi(df['Close'], length=14)
    if stoch is not None and not stoch.empty:
        df['STOCH_RSI'] = stoch.iloc[:, 0]

    df['ALMA'] = ta.alma(df['Close'], length=9)

    fisher = ta.fisher(high=df['High'], low=df['Low'], length=9)
    if fisher is not None and not fisher.empty:
        df['FISHER'] = fisher.iloc[:, 0]
        df['FISHER_SINYAL'] = fisher.iloc[:, 1]

    st = ta.supertrend(df['High'], df['Low'], df['Close'], length=7, multiplier=3.0)
    if st is not None and not st.empty:
        yon_sutunu = [col for col in st.columns if 'SUPERTd' in col][0]
        cizgi_sutunu = [col for col in st.columns if 'SUPERT_' in col][0]
        df['ST_YON'] = st[yon_sutunu]
        df['ST_DEGER'] = st[cizgi_sutunu]

    df = hesapla_orijinal_smi(df, n=10, n_ema1=3, n_ema2=3, n_signal=3)
    df = hesapla_tilson_t3(df, length=4, b=0.7)
    df = hesapla_ssl_hybrid(df, base_len=60, exit_len=15)
    df = hesapla_trend_strength_index(df, length=14)
    df['Vol_SMA_20'] = df['Volume'].rolling(window=20).mean()

    return df


def _period_hesapla(interval):
    """
    'max' yerine, indikatörler için yeterli ama gereksiz büyük olmayan bir
    period değeri döndürür. En uzun indikatör (EMA_150) için 150 periyot
    yeterliyken, kat kat fazla veri (bazı BIST hisselerinde 20-30 yıl) indirmek
    hem yavaşlatıyor hem gereksiz.
    Not: Aylık (1mo) periyotta 5 yıl sadece ~60 bar eder — 150 periyotluk EMA
    için yetersiz kalır, o yüzden 1mo ve saatlik periyotlarda 'max' korunuyor
    (saatlik veride zaten Yahoo kendi üst sınırını uyguluyor, veri miktarı az).
    """
    if interval == "1d":
        return "1y"       # Günlük: ~1250 bar, Haftalık: ~260 bar — ikisi de 150 periyotluk EMA için yeterli
    elif interval == "1wk":
        return "3y"
    else:
        return "max"      # 1mo, 1h, 2h, 4h


def verileri_hazirla(ticker_symbol, interval="1d", auto_adjust=True, deneme_sayisi=2, bekleme_sn=2):
    """
    Tek bir sembolü indirir ve indikatörleri ekler. Toplu indirmede eksik kalan
    ya da tekil kullanım gereken durumlar için (fallback) kullanılır.
    Hisse gerçekten delisted/bulunamıyorsa None döner.
    """
    df = None
    for deneme in range(1, deneme_sayisi + 1):
        try:
            df = yf.download(
                ticker_symbol, period=_period_hesapla(interval), interval=interval,
                progress=False, auto_adjust=auto_adjust, timeout=15,
            )
        except Exception:
            df = None

        if df is not None and not df.empty:
            break

        if deneme < deneme_sayisi:
            time.sleep(bekleme_sn)

    return _indikatorler_ekle(df)


def _ticker_ayikla(ham, sembol, tek_sembol_mu):
    """Toplu (çoklu ticker) indirilen veriden tek bir sembolün OHLCV verisini çıkarır."""
    if ham is None or ham.empty:
        return None
    try:
        if tek_sembol_mu:
            df = ham.copy()
        elif isinstance(ham.columns, pd.MultiIndex):
            ust_seviye = ham.columns.get_level_values(0)
            if sembol not in ust_seviye:
                return None
            df = ham[sembol].copy()
        else:
            df = ham.copy()

        df = df.dropna(how="all")
        return df if not df.empty else None
    except Exception:
        return None


def _toplu_indir_ve_hazirla(tickers: dict, interval, auto_adjust, parca_boyutu=50, max_worker=10):
    """
    Hisseleri gruplar halinde TEK istekte indirir (yfinance'in kendi paralel
    indirme mekanizmasını kullanarak — tekil tekil indirmekten çok daha hızlı).
    Toplu indirmede eksik/boş kalan semboller için tekil (fallback) indirme dener.
    """
    sonuc = {}
    isim_sembol_liste = list(tickers.items())
    toplam_parca = (len(isim_sembol_liste) + parca_boyutu - 1) // parca_boyutu

    for parca_no in range(toplam_parca):
        parca = isim_sembol_liste[parca_no * parca_boyutu: (parca_no + 1) * parca_boyutu]
        semboller = [sembol for _, sembol in parca]
        tek_sembol_mu = len(semboller) == 1

        print(f"Grup {parca_no + 1}/{toplam_parca} indiriliyor ({len(semboller)} varlık)...", flush=True)

        ham = None
        for deneme in range(1, 3):
            try:
                ham = yf.download(
                    semboller, period=_period_hesapla(interval), interval=interval, group_by="ticker",
                    auto_adjust=auto_adjust, threads=max_worker, progress=False, timeout=30,
                )
            except Exception:
                ham = None
            if ham is not None and not ham.empty:
                break
            if deneme < 2:
                time.sleep(3)

        for isim, sembol in parca:
            df_ham = _ticker_ayikla(ham, sembol, tek_sembol_mu)
            df = _indikatorler_ekle(df_ham) if df_ham is not None else None
            if df is not None:
                sonuc[isim] = df

    # Toplu indirmede eksik kalanlar için tekil (paralel) fallback dene
    eksikler = [(isim, sembol) for isim, sembol in tickers.items() if isim not in sonuc]
    if eksikler:
        print(f"Toplu indirmede {len(eksikler)} varlık eksik kaldı, tekil olarak tekrar deneniyor...", flush=True)
        with ThreadPoolExecutor(max_workers=max_worker) as havuz:
            gelecekler = {
                havuz.submit(verileri_hazirla, sembol, interval, auto_adjust): isim
                for isim, sembol in eksikler
            }
            for gelecek in as_completed(gelecekler):
                isim = gelecekler[gelecek]
                df = gelecek.result()
                if df is not None:
                    sonuc[isim] = df

    return sonuc


# =====================================================================
# 3. BAĞIMSIZ ANALİZ FONKSİYONLARI
# =====================================================================
def analiz_supertrend(df):
    if len(df) < 2:
        return "-"
    bugun_yon = df.iloc[-1].get('ST_YON')
    dun_yon = df.iloc[-2].get('ST_YON')

    if pd.isna(bugun_yon) or pd.isna(dun_yon):
        return "-"

    if dun_yon == -1 and bugun_yon == 1:
        return "🔥 AL (Taze Kırılım)"
    elif dun_yon == 1 and bugun_yon == -1:
        return "🩸 SAT (Trend Kırıldı)"
    elif bugun_yon == 1:
        return "🟢 Yükseliş Trendinde"
    elif bugun_yon == -1:
        return "🔴 Düşüş Trendinde"

    return "-"


def analiz_tilson_alma_fisher(df):
    if len(df) < 3:
        return "-"
    bugun, dun = df.iloc[-1], df.iloc[-2]

    fiyat, alma = bugun.get('Close'), bugun.get('ALMA')
    bugun_t3, dun_t3 = bugun.get('TILSON_T3'), dun.get('TILSON_T3')
    fisher, fisher_sinyal = bugun.get('FISHER'), bugun.get('FISHER_SINYAL')

    if pd.isna(fiyat) or pd.isna(alma) or pd.isna(bugun_t3) or pd.isna(fisher):
        return "-"

    sart1_tilson_yesil = bugun_t3 > dun_t3
    sart2_fiyat_alma_ustunde = fiyat > alma
    sart3_fisher_al = fisher > fisher_sinyal

    if sart1_tilson_yesil and sart2_fiyat_alma_ustunde and sart3_fisher_al:
        yeni_krilim = (dun.get('Close', 0) <= dun.get('ALMA', 0)) or (dun_t3 <= df.iloc[-3].get('TILSON_T3', dun_t3))
        if yeni_krilim:
            return "🔥 GÜÇLÜ AL (Taze Kırılım)"
        return "🟢 AL (Trend Onaylı)"
    elif not sart1_tilson_yesil and fiyat < alma and fisher < fisher_sinyal:
        return "🔴 SAT"

    return "⏳ BEKLE"


def analiz_kombine_dip(df):
    if len(df) < 2:
        return "-"
    bugun, dun = df.iloc[-1], df.iloc[-2]

    fiyat, rsi = bugun.get('Close'), bugun.get('RSI')
    bb_alt, bb_ust = bugun.get('BB_ALT'), bugun.get('BB_UST')
    smi, smi_sinyal = bugun.get('SMI'), bugun.get('SMIs')

    if pd.isna(fiyat) or pd.isna(bb_alt) or pd.isna(smi):
        return "-"

    kural_bb = fiyat <= (bb_alt * 1.015)
    kural_rsi = rsi < 35
    kural_smi = (smi < 0) and (smi_sinyal < 0) and (dun.get('SMI', 0) <= dun.get('SMIs', 0)) and (smi > smi_sinyal)

    if kural_bb and kural_rsi and kural_smi:
        return "🚀 KUSURSUZ DİP"
    elif kural_bb and kural_rsi:
        return "🟢 POTANSİYEL DİP"
    elif fiyat >= (bb_ust * 0.985) and rsi > 70:
        return "🔴 ZİRVEDE"
    return "-"


def analiz_hacim_smi(df):
    if len(df) < 2:
        return "-"
    bugun, dun = df.iloc[-1], df.iloc[-2]

    smi_b, smis_b = bugun.get('SMI'), bugun.get('SMIs')
    smi_d, smis_d = dun.get('SMI'), dun.get('SMIs')
    vol, vol_sma = bugun.get('Volume'), bugun.get('Vol_SMA_20')

    if pd.isna(smi_b) or pd.isna(vol) or pd.isna(vol_sma):
        return "-"

    smi_yukari_kesti = (smi_d <= smis_d) and (smi_b > smis_b)
    smi_asagi_kesti = (smi_d >= smis_d) and (smi_b < smis_b)

    hacim_onayli = vol > vol_sma

    if smi_yukari_kesti:
        if smi_b < 0:
            if hacim_onayli:
                return "🚀 KUSURSUZ DÖNÜŞ (0 Altı + Hacim)"
            else:
                return "🟢 POTANSİYEL DİP (0 Altı - Hacimsiz)"
        else:
            if hacim_onayli:
                return "📈 TREND DEVAMI (0 Üstü + Hacim)"
            else:
                return "🟡 RİSKLİ AL (0 Üstü - Hacimsiz)"

    elif smi_asagi_kesti:
        if smi_b > 0:
            return "🩸 SAT (Zirveden Dönüş)"
        else:
            return "🔴 ZAYIFLAMA (Zaten Dipte)"

    return "-"


def analiz_ema_ssl_kombine(df):
    if len(df) < 150:
        return "-"

    bugun = df.iloc[-1]

    ema50 = bugun.get('EMA_50')
    ema100 = bugun.get('EMA_100')
    ema150 = bugun.get('EMA_150')

    ssl_trend = bugun.get('SSL_BASE_TREND')
    ssl_ok = bugun.get('SSL_EXIT_SIGNAL')
    if pd.isna(ema150) or pd.isna(ssl_trend) or pd.isna(ssl_ok):
        return "-"

    ema_yukselis_duzeni = (ema50 > ema100) and (ema50 > ema150)
    ema_dusus_duzeni = (ema50 < ema100) and (ema50 < ema150)
    ema_yukari_hazirlik = (ema50 > ema100) and (ema50 <= ema150)
    ema_asagi_hazirlik = (ema50 < ema100) and (ema50 >= ema150)

    if ema_yukselis_duzeni and ssl_trend == 1 and ssl_ok == 1:
        return "🚀 ASIL SİNYAL: GÜÇLÜ AL (EMA Sıralı + SSL Onay)"
    elif ema_dusus_duzeni and ssl_trend == -1 and ssl_ok == -1:
        return "🩸 ASIL SİNYAL: GÜÇLÜ SAT (EMA Çöktü + SSL Onay)"
    elif ema_yukselis_duzeni and ssl_trend == 1 and ssl_ok == 0:
        return "🟢 EMA Yükselişte (SSL Ok Bekleniyor)"
    elif ema_yukselis_duzeni and ssl_trend == -1:
        return "⚠️ Yükseliş Trendinde Düzeltme (SSL Negatif)"
    elif ema_yukari_hazirlik:
        return "⚡ Yükseliş Hazırlığı (50>100 Kesti, 150 Bekleniyor)"
    elif ema_asagi_hazirlik:
        return "📉 Düşüş Hazırlığı (50<100 Kesti, 150 Bekleniyor)"
    elif ema_dusus_duzeni:
        return "🔴 Ayı Piyasası (EMA 50 En Altta)"

    return "⚪ Karışık / Testere Piyasası"


def analiz_ema_sikisma(df, esik_orani=1.5):
    if len(df) < 150:
        return "-"

    bugun = df.iloc[-1]
    fiyat = bugun.get('Close')
    ema50 = bugun.get('EMA_50')
    ema100 = bugun.get('EMA_100')
    ema150 = bugun.get('EMA_150')
    if pd.isna(ema150) or pd.isna(fiyat) or fiyat == 0:
        return "-"

    en_yuksek_ema = max(ema50, ema100, ema150)
    en_dusuk_ema = min(ema50, ema100, ema150)

    ema_farki = en_yuksek_ema - en_dusuk_ema
    daralma_orani = (ema_farki / fiyat) * 100

    if daralma_orani < esik_orani:
        return f"🚨 SERT SIKIŞMA (Bant: %{daralma_orani:.2f})"
    elif daralma_orani < (esik_orani * 2):
        return f"🟡 Daralıyor (Bant: %{daralma_orani:.2f})"
    else:
        return f"⚪ Yelpaze Açık (Bant: %{daralma_orani:.2f})"


# =====================================================================
# 4. ANA BİRLEŞTİRİCİ MOTOR
# =====================================================================
def rapor_olustur(secim: str, period_selection: str = "1d", hisse_dosyasi: str = "data/hisse_senetleri.xlsx",
                   parca_boyutu: int = 50, max_worker: int = 20):
    """
    secim: "BIST" ya da "FON"
    period_selection: "1d", "1wk", "1mo", "1h", "2h", "4h" vb.
    parca_boyutu: Her toplu indirme isteğinde kaç varlığın birlikte indirileceği.
    max_worker: Hem toplu indirmede hem de eksik kalan varlıkların tekil fallback'inde
                kaç tanesinin aynı anda (paralel) indirileceği.
    """
    tickers, auto_adjust = get_tickers(secim, hisse_dosyasi)
    if not tickers:
        return None

    toplam = len(tickers)
    print(f"Modüler Analiz Motoru Çalışıyor... {toplam} varlık gruplar halinde indiriliyor.\n", flush=True)

    veri_sozlugu = _toplu_indir_ve_hazirla(tickers, period_selection, auto_adjust, parca_boyutu, max_worker)

    def sr(val):
        return round(val, 2) if pd.notna(val) else None

    satirlar = []
    basarisiz_tickerlar = []

    for isim, sembol in tickers.items():
        df = veri_sozlugu.get(isim)

        if df is not None and not df.empty:
            son = df.iloc[-1]

            satir_verisi = {
                "Varlık": isim,
                "Fiyat": sr(son.get('Close')),

                "Supertrend_Sinyal": analiz_supertrend(df),
                "Tilson_Sinyal": analiz_tilson_alma_fisher(df),
                "Hacim_SMI": analiz_hacim_smi(df),
                "Kombine_Dip": analiz_kombine_dip(df),
                "SSL&EMA_Sinyal": analiz_ema_ssl_kombine(df),
                "EMA_Sikisma": analiz_ema_sikisma(df),

                "RSI": sr(son.get('RSI')),
                "StochRSI": sr(son.get('STOCH_RSI')),
                "TSI": sr(son.get('TSI')),
                "ema50": sr(son.get('EMA_50')),
                "ema100": sr(son.get('EMA_100')),
                "ema150": sr(son.get('EMA_150')),
            }
            satirlar.append(satir_verisi)
        else:
            basarisiz_tickerlar.append(f"{isim} ({sembol})")

    if basarisiz_tickerlar:
        print(f"\n⚠️  {len(basarisiz_tickerlar)} varlık için veri alınamadı (delisted/hatalı kod/geçici bağlantı sorunu):", flush=True)
        print("   " + ", ".join(basarisiz_tickerlar), flush=True)

    if not satirlar:
        return None

    sonuc_df = pd.DataFrame(satirlar).set_index("Varlık")
    return sonuc_df
