import os
from datetime import datetime

import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="מעקב תיק מניות ישראלי",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

DB_FILE = "portfolio.csv"
# portfolio.csv keeps exactly these 3 columns, in this order. Never change.
COLUMNS = ["מניה", "סימול", "שער קניה"]
ERROR_TEXT = "❌ תקלה"

# סימולים ישנים ושגויים שאינם קיימים ב-Yahoo -> הסימול הנכון
KNOWN_TICKER_FIXES = {"AURON.TA": "ORON.TA", "RIMON.TA": "RMON.TA"}

CURRENCY_LABELS = {
    "ILA": "אגורות (TASE)",
    "ILS": "שקלים",
    "USD": "דולר $",
    "EUR": "יורו €",
    "GBP": "פאונד £",
}

# Fallback portfolio, identical to the original defaults.
DEFAULT_PORTFOLIO = {
    "מניה": ["ארית תעשיות", "שופרסל", "הבורסה לניירות ערך", "אירודרום", "טאואר", "אורון", "רימון", "Soxx"],
    "סימול": ["ARYT.TA", "SAE.TA", "TASE.TA", "ARDM.TA", "TSEM.TA", "ORON.TA", "RMON.TA", "SOXX"],
    "שער קניה": [5958.0, 4513.0, 14700.0, 425.0, 64827.0, 3418.0, 12871.0, 650.0],
}

# ---------------------------------------------------------------------------
# Portfolio persistence (structure is fixed: exactly COLUMNS, in this order)
# ---------------------------------------------------------------------------

def load_portfolio():
    """Load portfolio.csv, forcing the exact 3-column structure. Extra legacy
    columns (e.g. 'מחיר ידני לגיבוי') are dropped, never saved back.

    Defaults are written only when the file does not exist. An empty file is an
    empty portfolio (the user deleted everything), and an unreadable file stops
    the app without touching it, so user data is never overwritten."""
    if not os.path.exists(DB_FILE):
        df_default = pd.DataFrame(DEFAULT_PORTFOLIO)
        save_portfolio(df_default)
        return df_default
    try:
        df = pd.read_csv(DB_FILE)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=COLUMNS)
    except Exception as e:
        st.error(f"{ERROR_TEXT}: לא ניתן לקרוא את {DB_FILE} ({e}). הקובץ לא שונה — יש לתקן אותו ולרענן.")
        st.stop()
    df = df.reindex(columns=COLUMNS)  # drop extras, fix order
    df["שער קניה"] = pd.to_numeric(df["שער קניה"], errors="coerce")
    return df

def save_portfolio(df):
    """Save with the enforced column structure — byte-compatible with the old CSV."""
    df[COLUMNS].to_csv(DB_FILE, index=False)

# ---------------------------------------------------------------------------
# Market data (automatic only — no manual price fallback, ever)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def fetch_price(ticker):
    """Single-ticker last close from Yahoo, or None."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d", timeout=5)
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        last_price = stock.fast_info.last_price
        if last_price:
            return float(last_price)
    except Exception:
        pass
    return None

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_currency(ticker):
    """Quote currency from Yahoo fast_info (e.g. 'ILA', 'USD'), or None."""
    try:
        code = yf.Ticker(ticker).fast_info["currency"]
        return code or None
    except Exception:
        return None

@st.cache_data(ttl=300, show_spinner=False)
def fetch_prices_bulk(tickers: tuple):
    """Fetch last close + previous close for all tickers in ONE request.
    Per-ticker failures stay None so one bad ticker never breaks the rest.
    Returns (prices, fetched_at) — fetched_at is cached with the prices, so it
    shows when the data was really fetched, not when the page was drawn."""
    result = {t: {"close": None, "prev_close": None, "currency": fetch_currency(t)} for t in tickers}
    fetched_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    if not tickers:
        return result, fetched_at
    try:
        data = yf.download(list(tickers), period="5d", group_by="ticker",
                           progress=False, threads=True, timeout=10)
    except Exception:
        data = None
    for t in tickers:
        try:
            if data is None or data.empty:
                continue
            df_t = data[t] if isinstance(data.columns, pd.MultiIndex) else data
            closes = df_t["Close"].dropna()
            if len(closes) >= 1:
                result[t]["close"] = float(closes.iloc[-1])
            if len(closes) >= 2:
                result[t]["prev_close"] = float(closes.iloc[-2])
        except Exception:
            continue
    return result, fetched_at

@st.cache_data(ttl=3600, show_spinner=False)
def search_ticker(query):
    """Yahoo search with priority to Tel Aviv tickers. None if nothing valid."""
    try:
        quotes = yf.Search(query, max_results=10).quotes
    except Exception:
        return None
    symbols = [q.get("symbol") for q in quotes if q.get("symbol")]
    tase = [s for s in symbols if s.endswith(".TA")]
    for symbol in tase + [s for s in symbols if s not in tase]:
        if fetch_price(symbol) is not None:
            return symbol
    return None

def resolve_ticker(raw_ticker):
    """Valid Yahoo ticker: as typed, then with .TA, then search. None if not found."""
    ticker = raw_ticker.strip().upper()
    ticker = KNOWN_TICKER_FIXES.get(ticker, ticker)
    base = ticker.removesuffix(".TA")
    for candidate in dict.fromkeys([ticker, base + ".TA", base]):
        if fetch_price(candidate) is not None:
            return candidate
    return search_ticker(base)

def currency_label(code, ticker):
    """Human-readable currency for display only — derived at runtime, never stored."""
    if code:
        return CURRENCY_LABELS.get(code, code)
    if ticker.endswith(".TA"):
        return "אגורות (TASE)"
    return "לא ידוע"

def ltr(text):
    """Wrap numbers/dates in a Unicode LTR isolate so RTL text doesn't reorder
    them (otherwise '-21.72%' renders as '21.72%-')."""
    return f"⁦{text}⁩"

def flash(kind, message):
    """Queue a message that survives st.rerun() (st.success before a rerun is lost)."""
    st.session_state.flash.append((kind, message))

def show_flash():
    for kind, message in st.session_state.flash:
        getattr(st, kind)(message)
    st.session_state.flash = []

# ---------------------------------------------------------------------------
# RTL: Streamlit renders LTR by default; flip the main container to RTL, which
# also reverses st.columns and tabs. The data grid is canvas-rendered and
# can't be RTL, so it stays LTR and its columns are ordered right-to-left.
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
      [data-testid="stMainBlockContainer"] { direction: rtl; text-align: right; }
      [data-testid="stDataFrame"] { direction: ltr; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📈 מעקב תיק מניות ישראלי")

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
if "ticker_preview" not in st.session_state:
    st.session_state.ticker_preview = None
if "flash" not in st.session_state:
    st.session_state.flash = []

show_flash()

# ---------------------------------------------------------------------------
# Tab 1 — portfolio overview + management
# ---------------------------------------------------------------------------

tab1, tab2 = st.tabs(["📊 התיק שלי וניהול", "➕ הוספת מניה חדשה"])

with tab1:
    portfolio = st.session_state.portfolio
    st.subheader("התיק שלי")

    if portfolio.empty:
        st.info("התיק שלך ריק כרגע. הוסף מניה בלשונית '➕ הוספת מניה חדשה'.")
    else:
        tickers = tuple(str(t).strip() for t in portfolio["סימול"])
        with st.spinner("טוען מחירים מ-Yahoo..."):
            prices, fetched_at = fetch_prices_bulk(tickers)

        # Auto-correct tickers whose price could not be fetched (same as before)
        fixes = []
        for index, row in portfolio.iterrows():
            ticker = str(row["סימול"]).strip()
            if prices.get(ticker, {}).get("close") is None:
                resolved = resolve_ticker(ticker)
                if resolved and resolved != ticker:
                    fixes.append((index, ticker, resolved))
        for index, old, new in fixes:
            portfolio.loc[index, "סימול"] = new
            prices[new] = {"close": fetch_price(new), "prev_close": None,
                           "currency": fetch_currency(new)}
            st.info(f"הסימול של '{portfolio.loc[index, 'מניה']}' תוקן אוטומטית מ-{old} ל-{new}")
        if fixes:
            save_portfolio(portfolio)
            st.session_state.portfolio = portfolio

        # Build display rows
        dup_mask = portfolio["סימול"].astype(str).str.strip().duplicated(keep=False)
        records = []
        for index, row in portfolio.iterrows():
            ticker = str(row["סימול"]).strip()
            name = str(row["מניה"])
            buy = float(row["שער קניה"])
            info = prices.get(ticker, {})
            close = info.get("close")
            prev = info.get("prev_close")
            name_out = f"{name} ⚠️ כפילות" if dup_mask.loc[index] else name

            if close is None:
                records.append({
                    "מניה": name_out, "סימול": ticker,
                    "מטבע": currency_label(info.get("currency"), ticker),
                    "שער קניה": buy, "שער נוכחי": None, "שינוי יומי": None,
                    "רווח/הפסד": None, "סטטוס": ERROR_TEXT,
                })
                continue

            pl = ((close - buy) / buy) * 100 if buy > 0 else None
            day = ((close - prev) / prev) * 100 if prev else None
            records.append({
                "מניה": name_out, "סימול": ticker,
                "מטבע": currency_label(info.get("currency"), ticker),
                "שער קניה": buy, "שער נוכחי": close, "שינוי יומי": day,
                "רווח/הפסד": pl, "סטטוס": "תקין",
            })

        # The grid is always LTR, so list columns right-to-left: name ends up rightmost.
        display_df = pd.DataFrame(records)[[
            "סטטוס", "רווח/הפסד", "שינוי יומי", "שער נוכחי", "שער קניה", "מטבע", "סימול", "מניה",
        ]]
        for col in ["שער קניה", "שער נוכחי", "שינוי יומי", "רווח/הפסד"]:
            display_df[col] = pd.to_numeric(display_df[col], errors="coerce")

        # --- Portfolio KPIs (derived at runtime; no quantities exist in the data)
        valid = display_df.dropna(subset=["רווח/הפסד"])
        avg_pl = valid["רווח/הפסד"].mean() if not valid.empty else None
        up_n = int((valid["רווח/הפסד"] > 0).sum())
        down_n = int((valid["רווח/הפסד"] < 0).sum())
        best = valid.loc[valid["רווח/הפסד"].idxmax()] if not valid.empty else None
        worst = valid.loc[valid["רווח/הפסד"].idxmin()] if not valid.empty else None

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("מניות בתיק", len(portfolio))
        k2.metric("ביצוע ממוצע", ltr(f"{avg_pl:+.2f}%") if avg_pl is not None else "—")
        k3.metric("ברווח 🔼", up_n)
        k4.metric("בהפסד 🔽", down_n)
        if best is not None and worst is not None:
            st.caption(
                f"🏆 המובילה: {best['מניה']} ({ltr(format(best['רווח/הפסד'], '+.2f') + '%')})   ·   "
                f"הגרועה: {worst['מניה']} ({ltr(format(worst['רווח/הפסד'], '+.2f') + '%')})"
            )

        col_refresh, col_time = st.columns([1, 3])
        with col_refresh:
            if st.button("🔄 רענן מחירים", width="stretch"):
                fetch_prices_bulk.clear()
                fetch_price.clear()
                fetch_currency.clear()
                st.rerun()
        with col_time:
            st.caption(f"⏱️ מחירים נשלפו לאחרונה: {ltr(fetched_at)} (מתרעננים כל 5 דקות)")

        # --- Holdings table: numeric (sortable) + green/red styling
        def _color_signed(val):
            if pd.isna(val):
                return ""
            if val > 0:
                return "color: #16a34a; font-weight: 700;"
            if val < 0:
                return "color: #dc2626; font-weight: 700;"
            return ""

        styled = (
            display_df.style
            .format(
                {
                    "שער קניה": "{:,.2f}",
                    "שער נוכחי": "{:,.2f}",
                    "שינוי יומי": "{:+.2f}%",
                    "רווח/הפסד": "{:+.2f}%",
                },
                na_rep="—",
            )
            .map(_color_signed, subset=["שינוי יומי", "רווח/הפסד"])
        )
        st.dataframe(styled, width="stretch", hide_index=True)
        if dup_mask.any():
            st.caption("⚠️ כפילות = אותו סימול מופיע ביותר משורה אחת (נשמרות כשורות נפרדות בקובץ).")

        failed_tickers = display_df.loc[display_df["סטטוס"] == ERROR_TEXT, "סימול"].tolist()
        if failed_tickers:
            st.error(f"תקלה בשליפת מחיר עבור: {', '.join(failed_tickers)}. יש לבדוק את הסימול ולתקן אותו למטה.")

        st.markdown("---")
        st.subheader("⚙️ ניהול התיק")

        row_sel = st.selectbox(
            "בחר מניה לניהול",
            options=list(range(len(portfolio))),
            format_func=lambda i: (
                f"{portfolio.loc[i, 'מניה']} ({portfolio.loc[i, 'סימול']}) — "
                f"שער קניה: {portfolio.loc[i, 'שער קניה']:g}"
            ),
            key="manage_row",
        )
        sel_ticker = str(portfolio.loc[row_sel, "סימול"]).strip()
        sel_name = str(portfolio.loc[row_sel, "מניה"])

        col_edit_price, col_fix_ticker, col_delete = st.columns(3)

        with col_edit_price:
            st.markdown("##### ✏️ עריכת שער קנייה")
            new_buy = st.number_input(
                "שער קניה חדש",
                min_value=0.0,
                value=float(portfolio.loc[row_sel, "שער קניה"]),
                format="%.2f",
                key=f"edit_buy_{row_sel}",
            )
            if st.button("שמור שער", key=f"btn_save_buy_{row_sel}"):
                st.session_state.portfolio.loc[row_sel, "שער קניה"] = float(new_buy)
                save_portfolio(st.session_state.portfolio)
                flash("success", f"שער הקניה של '{sel_name}' עודכן ל-{new_buy:g} ונשמר!")
                st.rerun()

        with col_fix_ticker:
            st.markdown("##### 🔧 תיקון סימול")
            new_ticker_input = st.text_input(
                "סימול חדש (למשל: ORON.TA)",
                value=sel_ticker,
                key=f"input_new_ticker_{row_sel}",
            )
            if st.button("שמור סימול", key=f"btn_save_ticker_{row_sel}"):
                resolved = resolve_ticker(new_ticker_input)
                if resolved:
                    st.session_state.portfolio.loc[row_sel, "סימול"] = resolved
                    save_portfolio(st.session_state.portfolio)
                    flash("success", f"הסימול של '{sel_name}' עודכן ל-{resolved} ונשמר!")
                    st.rerun()
                else:
                    st.error(f"{ERROR_TEXT}: הסימול '{new_ticker_input}' לא נמצא ב-Yahoo.")

        with col_delete:
            st.markdown("##### 🗑️ מחיקת מניה")
            st.caption(f"תימחק: {sel_name} ({sel_ticker})")
            confirm = st.checkbox("אני בטוח/ה — פעולה בלתי הפיכה", key=f"confirm_del_{row_sel}")
            if st.button("מחק לצמיתות", type="primary", disabled=not confirm,
                         key=f"btn_del_{row_sel}"):
                st.session_state.portfolio = (
                    st.session_state.portfolio.drop(row_sel).reset_index(drop=True)
                )
                save_portfolio(st.session_state.portfolio)
                flash("success", f"המניה '{sel_name}' ({sel_ticker}) נמחקה מהתיק.")
                st.rerun()

# ---------------------------------------------------------------------------
# Tab 2 — add a stock, with ticker preview before saving
# ---------------------------------------------------------------------------

with tab2:
    st.subheader("➕ הוספת מניה חדשה לתיק")

    stock_name = st.text_input("שם המניה בעברית (למשל: אורון)", key="add_name")
    stock_ticker = st.text_input("סימול (למשל: ORON או ORON.TA)", key="add_ticker")
    buy_price = st.number_input("שער קנייה", min_value=0.0, format="%.2f", key="add_buy")

    col_prev, col_add = st.columns(2)
    with col_prev:
        preview_clicked = st.button("🔍 תצוגה מקדימה", width="stretch")
    with col_add:
        add_clicked = st.button("➕ הוסף לתיק", type="primary", width="stretch")

    if preview_clicked:
        if not stock_ticker.strip():
            st.warning("נא להזין סימול לבדיקה.")
        else:
            resolved = resolve_ticker(stock_ticker)
            if resolved is None:
                st.session_state.ticker_preview = None
                st.error(f"{ERROR_TEXT}: הסימול '{stock_ticker.strip()}' לא נמצא ב-Yahoo.")
            else:
                price = fetch_price(resolved)
                cur = fetch_currency(resolved)
                st.session_state.ticker_preview = {
                    "raw": stock_ticker.strip().upper(),
                    "resolved": resolved,
                }
                st.success(
                    f"סימול זוהה: {resolved} · מטבע: {currency_label(cur, resolved)} · "
                    f"שער נוכחי: {price:,.2f}" if price is not None else
                    f"סימול זוהה: {resolved} (שער עדיין לא זמין)"
                )

    if add_clicked:
        if not stock_name.strip() or not stock_ticker.strip():
            st.warning("נא להזין שם מניה וסימול.")
        else:
            preview = st.session_state.ticker_preview
            if preview and preview["raw"] == stock_ticker.strip().upper():
                final_ticker = preview["resolved"]
            else:
                final_ticker = resolve_ticker(stock_ticker)

            if final_ticker is None:
                st.session_state.ticker_preview = None
                st.error(f"{ERROR_TEXT}: הסימול '{stock_ticker.strip()}' לא נמצא ב-Yahoo. המניה לא נוספה.")
            else:
                if final_ticker in [str(t).strip() for t in st.session_state.portfolio["סימול"]]:
                    flash("warning", f"⚠️ כבר קיימת שורה עם הסימול {final_ticker} — נוספה כשורה נפרדת (כפילות).")
                new_row = pd.DataFrame({
                    "מניה": [stock_name.strip()],
                    "סימול": [final_ticker],
                    "שער קניה": [float(buy_price)],
                })
                st.session_state.portfolio = pd.concat(
                    [st.session_state.portfolio, new_row], ignore_index=True
                )
                save_portfolio(st.session_state.portfolio)
                st.session_state.ticker_preview = None
                flash("success", f"המניה '{stock_name.strip()}' נוספה בהצלחה (סימול: {final_ticker})!")
                st.rerun()
