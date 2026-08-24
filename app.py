import streamlit as st
import yfinance as yf
import pandas as pd
import os

st.set_page_config(page_title="מעקב תיק מניות אוטומטי", page_icon="📈", layout="centered")

st.title("📈 מעקב תיק מניות ישראלי")

DB_FILE = "portfolio.csv"

def load_portfolio():
    if os.path.exists(DB_FILE):
        try:
            return pd.read_csv(DB_FILE)
        except Exception:
            pass
    return pd.DataFrame(columns=["מניה", "סימול", "שער קניה", "כמות"])

def save_portfolio(df):
    df.to_csv(DB_FILE, index=False)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()

st.subheader("הוספת מניה חדשה לתיק")

with st.form("add_stock_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        stock_name = st.text_input("שם המניה בעברית (למשל: הבורסה)")
    with col2:
        # כאן רושמים את הסימול מגלובס, למשל TASE.TA או TSEM.TA
        stock_ticker = st.text_input("סימול בגלובס באנגלית (למשל: TASE.TA)")
    
    col3, col4 = st.columns(2)
    with col3:
        buy_price = st.number_input("שער קנייה", min_value=0.0, format="%.2f")
    with col4:
        quantity = st.number_input("כמות מניות", min_value=1, value=1)
    
    submit_button = st.form_submit_button("הוסף לתיק")

    if submit_button:
        if stock_name and stock_ticker:
            clean_name = stock_name.strip()
            clean_ticker = stock_ticker.strip().upper()
            
            # הוספת סיומת .TA אוטומטית אם שכחו לשים למניות ת"א
            if not clean_ticker.endswith(".TA") and len(clean_ticker) <= 5 and clean_ticker.isalpha():
                clean_ticker += ".TA"

            new_row = pd.DataFrame({
                "מניה": [clean_name],
                "סימול": [clean_ticker],
                "שער קניה": [buy_price],
                "כמות": [quantity]
            })
            
            st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_row], ignore_index=True)
            save_portfolio(st.session_state.portfolio)
            st.success(f"המניה '{clean_name}' נוספה בהצלחה ונשמרה!")
        else:
            st.warning("נא להזין גם שם מניה וגם סימול באנגלית.")

st.markdown("---")
st.subheader("התיק שלי")

if not st.session_state.portfolio.empty:
    current_prices = []
    profits_losses = []

    for index, row in st.session_state.portfolio.iterrows():
        ticker = row["סימול"]
        buy = float(row["שער קניה"])
        current_price = buy
        
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5d")
            if not hist.empty:
                current_price = float(hist['Close'].iloc[-1])
            else:
                todays_info = stock.fast_info
                if hasattr(todays_info, 'last_price') and todays_info.last_price:
                    current_price = float(todays_info.last_price)
        except Exception:
            pass

        current_prices.append(current_price)
        
        if buy > 0:
            pl_pct = ((current_price - buy) / buy) * 100
        else:
            pl_pct = 0.0
        profits_losses.append(f"{pl_pct:+.2f}%")

    display_df = st.session_state.portfolio.copy()
    display_df["שער נוכחי"] = [f"{p:.2f}" for p in current_prices]
    display_df["רווח/הפסד"] = profits_losses

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
    st.info("התיק שלך ריק כרגע. הוסף מניות למעלה.")