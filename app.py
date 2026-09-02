
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
        "מניה": ["שופרסל", "הבורסה לניירות ערך", "אירודרום", "העין שלישית", "ארית", "טאואר", "אירודרום", "אורון", "רימון", "Soxx"],
        "סימול": ["SAE.TA", "TASE.TA", "ARDM.TA", "THES.TA", "587014", "TSEM.TA", "ARDM.TA", "AURON.TA", "RIMON.TA", "SOXX"],
        "שער קניה": [4513.0, 14700.0, 425.0, 1147.0, 5958.0, 64827.0, 222.0, 3418.0, 12871.0, 1961.0]
    }
    df_default = pd.DataFrame(default_data)
    df_default.to_csv(DB_FILE, index=False)
    return df_default

def save_portfolio(df):
    df.to_csv(DB_FILE, index=False)

def get_tase_price_from_api(security_id):
    """שליפת שער ישירות מה-API של הבורסה לפי מספר נייר נקי מספרות"""
    try:
        clean_id = ''.join(filter(str.isdigit, str(security_id)))
        url = f"https://www.tase.co.il/api/data/security/securitydata?securityId={clean_id}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            price = data.get('security', {}).get('lastTradePrice')
            if price:
                return float(price)
    except Exception:
        pass
    return None

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()

st.subheader("הוספת מניה חדשה לתיק")

with st.form("add_stock_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        stock_name = st.text_input("שם המניה בעברית (למשל: ארית)")
    with col2:
        stock_ticker = st.text_input("סימול או מספר נייר (למשל: 587014)")
    
    buy_price = st.number_input("שער קנייה", min_value=0.0, format="%.2f")
    
    submit_button = st.form_submit_button("הוסף לתיק")

    if submit_button:
        if stock_name and stock_ticker:
            clean_name = stock_name.strip()
            clean_ticker = stock_ticker.strip().upper()
            
            # אם זה מספר טהור או סימול אמריקאי או שכבר יש .TA, לא מוסיפים כלום
            us_stocks = ["SOXX", "AAPL", "MSFT", "NVDA", "TSLA"]
            if clean_ticker in us_stocks or clean_ticker.endswith(".TA") or clean_ticker.isdigit():
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
            st.warning("נא להזין שם מניה וסימול/מספר נייר.")

st.markdown("---")
st.subheader("התיק שלי")

if not st.session_state.portfolio.empty:
    current_prices = []
    profits_losses = []

    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

    for index, row in st.session_state.portfolio.iterrows():
        ticker = str(row["סימול"]).strip()
        buy = float(row["שער קניה"])
        current_price = buy
        fetched = False

        # בדיקה האם הסימול מורכב מספרות בלבד (מספר נייר ערך)
        if ticker.isdigit():
            api_price = get_tase_price_from_api(ticker)
            if api_price:
                current_price = api_price
                fetched = True

        # אם זה לא מספר נייר, ננסה דרך Yahoo Finance
        if not fetched:
            try:
                yahoo_ticker = ticker if (ticker in ["SOXX", "AAPL", "MSFT", "NVDA", "TSLA"] or ticker.endswith(".TA")) else ticker + ".TA"
                stock = yf.Ticker(yahoo_ticker, session=session)
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
