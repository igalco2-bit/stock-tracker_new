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
        "שער קניה": [5958.0, 4513.0, 14700.0, 425.0, 64827.0, 3418.0, 12871.0, 1961.0],
        "מחיר ידני לגיבוי": [0.0, 0.0, 0.0, 0.0, 0.0, 3418.0, 12871.0, 0.0]
    }
    df_default = pd.DataFrame(default_data)
    df_default.to_csv(DB_FILE, index=False)
    return df_default

def save_portfolio(df):
    df.to_csv(DB_FILE, index=False)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_portfolio()
    if "מחיר ידני לגיבוי" not in st.session_state.portfolio.columns:
        st.session_state.portfolio["מחיר ידני לגיבוי"] = 0.0

# חלוקה ללשוניות נפרדות (טאבים)
tab1, tab2 = st.tabs(["📊 התיק שלי וניהול שערים", "➕ הוספת מניה חדשה"])

with tab1:
    st.subheader("התיק שלי")
    if not st.session_state.portfolio.empty:
        current_prices = []
        profits_losses = []
        price_sources = []

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        for index, row in st.session_state.portfolio.iterrows():
            ticker = str(row["סימול"]).strip()
            buy = float(row["שער קניה"])
            backup_val = float(row.get("מחיר ידני לגיבוי", 0.0))
            current_price = buy
            fetched = False
            price_source = "שער קניה (ברירת מחדל)"

            # ניסיון שליפה אוטומטית מול Yahoo
            try:
                stock = yf.Ticker(ticker, session=session)
                hist = stock.history(period="5d", timeout=5)
                if not hist.empty:
                    current_price = float(hist['Close'].iloc[-1])
                    fetched = True
                    price_source = "אוטומטי (Yahoo)"
                else:
                    todays_info = stock.fast_info
                    if hasattr(todays_info, 'last_price') and todays_info.last_price:
                        current_price = float(todays_info.last_price)
                        fetched = True
                        price_source = "אוטומטי (Yahoo)"
            except Exception:
                pass

            # אם השליפה נכשלה אבל יש גיבוי ידני מוגדר
            if not fetched and backup_val > 0:
                current_price = backup_val
                fetched = True
                price_source = "ידני (גיבוי)"

            current_prices.append(current_price)
            price_sources.append(price_source)
            
            if buy > 0:
                pl_pct = ((current_price - buy) / buy) * 100
            else:
                pl_pct = 0.0
            profits_losses.append(f"{pl_pct:+.2f}%")

        display_df = pd.DataFrame({
            "מספר שורה": range(len(st.session_state.portfolio)),
            "מניה": st.session_state.portfolio["מניה"],
            "סימול": st.session_state.portfolio["סימול"],
            "שער קניה": st.session_state.portfolio["שער קניה"],
            "שער נוכחי": [f"{p:.2f}" for p in current_prices],
            "רווח/הפסד": profits_losses,
            "מקור מחיר": price_sources
        })

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("⚙️ ניהול התיק (עדכון שערים ומחיקות)")

        col_update, col_delete = st.columns(2)

        with col_update:
            st.markdown("##### עדכון שער ידני למניה")
            row_to_update = st.selectbox(
                "בחר מניה לעדכון שער", 
                options=range(len(st.session_state.portfolio)), 
                format_func=lambda x: f"שורה {x}: {st.session_state.portfolio.loc[x, 'מניה']} ({st.session_state.portfolio.loc[x, 'סימול']})",
                key="select_update_row"
            )
            current_backup_val = float(st.session_state.portfolio.loc[row_to_update, "מחיר ידני לגיבוי"])
            new_price_input = st.number_input(
                "הכנס שער נוכחי מעודכן", 
                min_value=0.0, 
                value=current_backup_val, 
                format="%.2f",
                key="input_new_backup_price"
            )
            if st.button("שמור שער מעודכן"):
                st.session_state.portfolio.loc[row_to_update, "מחיר ידני לגיבוי"] = new_price_input
                save_portfolio(st.session_state.portfolio)
                st.success("השער עודכן בהצלחה ונשמר!")
                st.rerun()

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
            stock_ticker = st.text_input("סימול (למשל: AURON.TA)")
        
        buy_price = st.number_input("שער קנייה", min_value=0.0, format="%.2f")
        backup_price = st.number_input("שער נוכחי ידני (לגיבוי במקרה שאין שליפה אוטומטית)", min_value=0.0, format="%.2f", value=0.0)
        
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
                    "שער קניה": [buy_price],
                    "מחיר ידני לגיבוי": [backup_price]
                })
                
                st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_row], ignore_index=True)
                save_portfolio(st.session_state.portfolio)
                st.success(f"המניה '{clean_name}' נוספה בהצלחה!")
                st.rerun()
            else:
                st.warning("נא להזין שם מניה וסימול.")
