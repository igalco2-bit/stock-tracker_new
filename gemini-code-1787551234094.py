import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="תיק המניות שלי", page_icon="📈", layout="centered")

st.title("📈 מעקב תיק מניות אוטומטי")

# זיכרון מניות התחלתי או שמור
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = [
        {"name": "שופרסל", "ticker": "SAE.TA", "buy_price": 4270.0},
        {"name": "אירודרום", "ticker": "ARDM.TA", "buy_price": 425.0}
    ]

# טופס הוספת מניה חדשה
with st.form("add_stock_form", clear_on_submit=True):
    st.subheader("הוספת מניה חדשה")
    stock_name = st.text_input("שם המניה (למשל: אירודרום)")
    ticker_symbol = st.text_input("סימול ב-Yahoo Finance (למשל: ARDM.TA)")
    buy_price = st.number_input("שער קניה", min_value=0.0, step=0.01)
    
    submitted = st.form_submit_button("הוסף לתיק")
    if submitted and stock_name and ticker_symbol:
        st.session_state.portfolio.append({
            "name": stock_name, 
            "ticker": ticker_symbol.strip(), 
            "buy_price": buy_price
        })
        st.success("נוספה בהצלחה!")
        st.rerun()

st.subheader("התיק שלי")

if st.session_state.portfolio:
    data = []
    for index, item in enumerate(st.session_state.portfolio):
        try:
            ticker_obj = yf.Ticker(item["ticker"])
            hist = ticker_obj.history(period="1d")
            current_price = hist['Close'].iloc[-1] if not hist.empty else item["buy_price"]
        except:
            current_price = item["buy_price"]
            
        profit_loss_pct = ((current_price - item["buy_price"]) / item["buy_price"]) * 100
        
        data.append({
            "מניה": item["name"],
            "שער קניה": f"{item['buy_price']:.2f}",
            "שער נוכחי": f"{current_price:.2f}",
            "רווח/הפסד": f"{profit_loss_pct:+.2f}%",
            "index": index
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df.drop(columns=["index"]), use_container_width=True)
    
    # אפשרות מחיקת מניה
    del_index = st.number_input("הכנס מספר שורה למחיקה", min_value=0, max_value=len(st.session_state.portfolio)-1, step=1, value=0)
    if st.button("מחק מניה נבחרת"):
        st.session_state.portfolio.pop(del_index)
        st.rerun()
else:
    st.info("התיק ריק.")