import streamlit as st
import yfinance as yf
import pandas as pd
import os

st.set_page_config(page_title="מעקב תיק מניות ישראלי", page_icon="📈", layout="centered")

st.title("📈 מעקב תיק מניות ישראלי")

DB_FILE = "portfolio.csv"
ERROR_TEXT = "❌ תקלה"

# סימולים ישנים ושגויים שאינם קיימים ב-Yahoo -> הסימול הנכון
KNOWN_TICKER_FIXES = {"AURON.TA": "ORON.TA", "RIMON.TA": "RMON.TA"}

def load_portfolio():
    if os.path.exists(DB_FILE):
        try:
            df = pd.read_csv(DB_FILE)
            if not df.empty:
                return df
        except Exception:
            pass

    default_data = {
        "מניה": ["ארית תעשיות", "שופרסל", "הבורסה לניירות ערך", "אירודרום", "טאואר", "אורון", "רימון", "Soxx"],
        "סימול": ["ARYT.TA", "SAE.TA", "TASE.TA", "ARDM.TA", "TSEM.TA", "ORON.TA", "RMON.TA", "SOXX"],
        "שער קניה": [5958.0, 4513.0, 14700.0, 425.0, 64827.0, 3418.0, 12871.0, 1961.0],
    }
    df_default = pd.DataFrame(default_data)
    df_default.to_csv(DB_FILE, index=False)
    return df_default

def save_portfolio(df):
    df.to_csv(DB_FILE, index=False)

@st.cache_data(ttl=300, show_spinner=False)
def fetch_price(ticker):
    """מחזיר את השער האחרון מ-Yahoo, או None אם לא נמצא."""
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

@st.cache_data(ttl=3600, show_spinner=False)
def search_ticker(query):
    """מחפש ב-Yahoo סימול מתאים, עדיפות לבורסת תל אביב. מחזיר None אם לא נמצא."""
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
    """מוצא סימול תקין שיש לו מחיר ב-Yahoo: כפי שהוזן, עם ‎.TA, ולבסוף חיפוש. None אם לא נמצא."""
    ticker = raw_ticker.strip().upper()
    ticker = KNOWN_TICKER_FIXES.get(ticker, ticker)
    base = ticker.removesuffix(".TA")
    for candidate in dict.fromkeys([ticker, base + ".TA", base]):
        if fetch_price(candidate) is not None:
            return candidate
    return search_ticker(base)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
    st.session_state.portfolio = st.session_state.portfolio.drop(columns=["מחיר ידני לגיבוי"], errors="ignore")

# חלוקה ללשוניות נפרדות (טאבים)
tab1, tab2 = st.tabs(["📊 התיק שלי וניהול", "➕ הוספת מניה חדשה"])

with tab1:
    st.subheader("התיק שלי")
    if not st.session_state.portfolio.empty:
        current_prices = []
        profits_losses = []
        price_sources = []
        portfolio_changed = False

        for index, row in st.session_state.portfolio.iterrows():
            ticker = str(row["סימול"]).strip()
            buy = float(row["שער קניה"])

            current_price = fetch_price(ticker)
            if current_price is None:
                # הסימול לא נמצא - ניסיון לאתר את הסימול הנכון אוטומטית
                resolved = resolve_ticker(ticker)
                if resolved and resolved != ticker:
                    st.session_state.portfolio.loc[index, "סימול"] = resolved
                    portfolio_changed = True
                    current_price = fetch_price(resolved)
                    st.info(f"הסימול של '{row['מניה']}' תוקן אוטומטית מ-{ticker} ל-{resolved}")

            if current_price is None:
                current_prices.append(ERROR_TEXT)
                profits_losses.append("—")
                price_sources.append(f"{ERROR_TEXT}: לא נמצא מחיר ב-Yahoo")
                continue

            current_prices.append(f"{current_price:.2f}")
            price_sources.append("אוטומטי (Yahoo)")
            pl_pct = ((current_price - buy) / buy) * 100 if buy > 0 else 0.0
            profits_losses.append(f"{pl_pct:+.2f}%")

        if portfolio_changed:
            save_portfolio(st.session_state.portfolio)

        display_df = pd.DataFrame({
            "מספר שורה": range(len(st.session_state.portfolio)),
            "מניה": st.session_state.portfolio["מניה"],
            "סימול": st.session_state.portfolio["סימול"],
            "שער קניה": st.session_state.portfolio["שער קניה"],
            "שער נוכחי": current_prices,
            "רווח/הפסד": profits_losses,
            "מקור מחיר": price_sources
        })

        st.dataframe(display_df, width="stretch", hide_index=True)

        failed = [str(s) for s, p in zip(st.session_state.portfolio["סימול"], current_prices) if p == ERROR_TEXT]
        if failed:
            st.error(f"תקלה בשליפת מחיר עבור: {', '.join(failed)}. יש לבדוק את הסימול ולתקן אותו למטה.")

        st.markdown("---")
        st.subheader("⚙️ ניהול התיק (תיקון סימולים ומחיקות)")

        col_update, col_delete = st.columns(2)

        with col_update:
            st.markdown("##### תיקון סימול למניה")
            row_to_update = st.selectbox(
                "בחר מניה לתיקון",
                options=range(len(st.session_state.portfolio)),
                format_func=lambda x: f"שורה {x}: {st.session_state.portfolio.loc[x, 'מניה']} ({st.session_state.portfolio.loc[x, 'סימול']})",
                key="select_update_row"
            )
            new_ticker_input = st.text_input(
                "סימול חדש (למשל: ORON.TA)",
                value=str(st.session_state.portfolio.loc[row_to_update, "סימול"]),
                key=f"input_new_ticker_{row_to_update}"
            )
            if st.button("שמור סימול"):
                resolved = resolve_ticker(new_ticker_input)
                if resolved:
                    st.session_state.portfolio.loc[row_to_update, "סימול"] = resolved
                    save_portfolio(st.session_state.portfolio)
                    st.success(f"הסימול עודכן ל-{resolved} ונשמר!")
                    st.rerun()
                else:
                    st.error(f"{ERROR_TEXT}: הסימול '{new_ticker_input}' לא נמצא ב-Yahoo.")

        with col_delete:
            st.markdown("##### מחיקת מניה מהתיק")
            row_to_delete = st.selectbox(
                "בחר מניה למחיקה",
                options=range(len(st.session_state.portfolio)),
                format_func=lambda x: f"שורה {x}: {st.session_state.portfolio.loc[x, 'מניה']} ({st.session_state.portfolio.loc[x, 'סימול']})",
                key="select_delete_row"
            )
            if st.button("מחק שורה נבחרת", type="primary"):
                st.session_state.portfolio = st.session_state.portfolio.drop(row_to_delete).reset_index(drop=True)
                save_portfolio(st.session_state.portfolio)
                st.success("השורה נמחקה בהצלחה!")
                st.rerun()
    else:
        st.info("התיק שלך ריק כרגע.")

with tab2:
    st.subheader("➕ הוספת מניה חדשה לתיק")
    with st.form("add_stock_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            stock_name = st.text_input("שם המניה בעברית (למשל: אורון)")
        with col2:
            stock_ticker = st.text_input("סימול (למשל: ORON או ORON.TA)")

        buy_price = st.number_input("שער קנייה", min_value=0.0, format="%.2f")

        submit_button = st.form_submit_button("הוסף לתיק")

        if submit_button:
            if stock_name and stock_ticker:
                clean_name = stock_name.strip()
                final_ticker = resolve_ticker(stock_ticker)

                if final_ticker is None:
                    st.error(f"{ERROR_TEXT}: הסימול '{stock_ticker.strip()}' לא נמצא ב-Yahoo. המניה לא נוספה.")
                else:
                    new_row = pd.DataFrame({
                        "מניה": [clean_name],
                        "סימול": [final_ticker],
                        "שער קניה": [buy_price],
                    })

                    st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_row], ignore_index=True)
                    save_portfolio(st.session_state.portfolio)
                    st.success(f"המניה '{clean_name}' נוספה בהצלחה (סימול: {final_ticker})!")
                    st.rerun()
            else:
                st.warning("נא להזין שם מניה וסימול.")
