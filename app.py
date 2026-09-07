import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests

st.set_page_config(page_title="מעקב תיק מניות ישראלי", page_icon="📈", layout="centered")

st.title("📈 מעקב תיק מניות ישראלי")

DB_FILE = "portfolio.csv"

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
        "סימול": ["ARYT.TA", "SAE.TA", "TASE.TA", "ARDM.TA", "TSEM.TA", "AURON.TA", "RIMON.TA", "SOXX"],
        "שער קניה": [5958.0, 4513.0, 14700.0, 425.0, 64827.0, 3418.0, 12871.0, 1961.0]
    }
    df_default = pd.DataFrame(default_data)
    df_default.to_csv(DB_FILE, index=False)
    return df_default

def save_portfolio(df):
    df.to_csv(DB_FILE, index=False)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()

st.subheader("הוספת מניה חדשה לתיק")

with st.form("add_stock_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        stock_name = st.text_input("שם המניה בעברית (למשל: אורון)")
    with col2:
        stock_ticker = st.text_input("סימול (למשל: AURON.TA)")
    
    buy_price = st.number_input("שער קנייה", min_value=0.0, format="%.2f")
    
    submit_button = st.form_submit_button("הוסף לתיק")

    if submit_button:
        if stock_name and stock_ticker:
            clean_name = stock_name.strip()
            clean_ticker = stock_ticker.strip().upper()
            
            us_stocks = ["SOXX", "AAPL", "MSFT", "NVDA", "TSLA"]
            if clean_ticker in us_stocks or clean_ticker.endswith(".TA"):
                final_ticker = clean_ticker
            else:
                final_ticker = clean_ticker + ".TA"

            new_row = pd.DataFrame({
                "מניה": [clean_name],
                "סימול": [final_ticker],
                "שער קניה": [buy_price]
            })
            
            st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_row], ignore_index=True)
            save_portfolio(st.session_state.portfolio)
            st.success(f"המניה '{clean_name}' נוספה בהצלחה!")
            st.rerun()
        else:
            st.warning("נא להזין שם מניה וסימול.")

st.markdown("---")
st.subheader("התיק שלי")

if not st.session_state.portfolio.empty:
    current_prices = []
    profits_losses = []

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })

    # מילון התאמות לסימולים עקשנים ב-Yahoo Finance (אם הסימול בצד שמאל מופיע, המערכת תמיר אותו אוטומטית לסימול הנכון בצד ימין)
    # ניתן לשנות את הסימולים בצד הימני אם תגלה את הסימול המדויק שלהם ב-Yahoo
    yahoo_ticker_overrides = {
        "AURON.TA": "AURON.TA", # שים כאן סימול חלופי אם תמצא ב-Yahoo, למשל "ORON.TA"
        "RIMON.TA": "RIMON.TA"  # שים כאן סימול חלופי אם תמצא ב-Yahoo
    }

    for index, row in st.session_state.portfolio.iterrows():
        original_ticker = str(row["סימול"]).strip()
        buy = float(row["שער קניה"])
        current_price = buy
        fetched = False

        # שימוש בסימול מתוקן אם קיים במילון
        ticker = yahoo_ticker_overrides.get(original_ticker, original_ticker)

        try:
            stock = yf.Ticker(ticker, session=session)
            hist = stock.history(period="5d", timeout=5)
            if not hist.empty:
                current_price = float(hist['Close'].iloc[-1])
                fetched = True
            else:
                todays_info = stock.fast_info
                if hasattr(todays_info, 'last_price') and todays_info.last_price:
                    current_price = float(todays_info.last_price)
                    fetched = True
        except Exception:
            pass

        # גיבוי למניית ארית שעובדת כעת
        if not fetched and ticker == "ARYT.TA":
            try:
                current_price = float(yf.Ticker("ARYT.TA", session=session).fast_info.last_price)
                fetched = True
            except:
                pass

        if not fetched:
            current_price = buy

        current_prices.append(current_price)
        
        if buy > 0:
            pl_pct = ((current_price - buy) / buy) * 100
        else:
            pl_pct = 0.0
        profits_losses.append(f"{pl_pct:+.2f}%")

    display_df = pd.DataFrame({
        "מניה": st.session_state.portfolio["מניה"],
        "סימול": st.session_state.portfolio["סימול"],
        "שער קניה": st.session_state.portfolio["שער קניה"],
        "שער נוכחי": [f"{p:.2f}" for p in current_prices],
        "רווח/הפסד": profits_losses
    })

    st.dataframe(display_df, use_container_width=True)

    st.subheader("מחיקת מניה מהתיק")
    row_to_delete = st.number_input("הכנס מספר שורה למחיקה", min_value=0, max_value=max(0, len(st.session_state.portfolio)-1), step=1, key="del_input")
    if st.button("מחק שורה נבחרת"):
        if not st.session_state.portfolio.empty:
            st.session_state.portfolio = st.session_state.portfolio.drop(row_to_delete).reset_index(drop=True)
            save_portfolio(st.session_state.portfolio)
            st.success("השורה נמחקה בהצלחה!")
            st.rerun()
else:
    st.info("התיק שלך ריק כרגע.")
