import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="מעקב תיק מניות אוטומטי", page_icon="📈", layout="centered")

st.title("📈 מעקב תיק מניות אוטומטי")

# מילון הממיר את מספרי נייר הערך הישראליים לסימולים של Yahoo Finance
tase_id_to_ticker = {
    "397018": "THES.TA",  # עין שלישית
    # תוכל להוסיף כאן בקלות עוד מספרי נייר ערך בעתיד לפי הצורך:
    # "מספר_נייר": "סימול.TA"
}

if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=["מניה", "מספר נייר", "סימול", "שער קניה", "כמות"])

st.subheader("הוספת מניה חדשה")

with st.form("add_stock_form"):
    col1, col2 = st.columns(2)
    with col1:
        stock_name_input = st.text_input("שם המניה בעברית (למשל: עין שלישית)")
    with col2:
        stock_id_input = st.text_input("מספר נייר ערך מגלובס (למשל: 397018)")
    
    col3, col4 = st.columns(2)
    with col3:
        buy_price = st.number_input("שער קנייה", min_value=0.0, format="%.2f")
    with col4:
        quantity = st.number_input("כמות מניות", min_value=1, value=1)
    
    submit_button = st.form_submit_button("הוסף לתיק")

    if submit_button:
        if stock_name_input and stock_id_input:
            clean_id = stock_id_input.strip()
            display_name = stock_name_input.strip()
            
            # בדיקה האם מספר הנייר קיים במילון שלנו
            if clean_id in tase_id_to_ticker:
                ticker_symbol = tase_id_to_ticker[clean_id]
            else:
                # גיבוי אוטומטי אם המספר לא רשום במילון
                ticker_symbol = f"{clean_id}.TA"

            new_row = pd.DataFrame({
                "מניה": [display_name],
                "מספר נייר": [clean_id],
                "סימול": [ticker_symbol],
                "שער קניה": [buy_price],
                "כמות": [quantity]
            })
            
            st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_row], ignore_index=True)
            st.success(f"המניה {display_name} (מספר {clean_id}) נוספה בהצלחה!")
        else:
            st.warning("נא להזין גם שם מניה וגם מספר נייר ערך.")

st.markdown("---")
st.subheader("התיק שלי")

if not st.session_state.portfolio.empty:
    current_prices = []
    profits_losses = []

    for index, row in st.session_state.portfolio.iterrows():
        ticker = row["סימול"]
        buy = row["שער קניה"]
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
    row_to_delete = st.number_input("הכנס מספר שורה למחיקה", min_value=0, max_value=max(0, len(st.session_state.portfolio)-1), step=1)
    if st.button("מחק שורה נבחרת"):
        if not st.session_state.portfolio.empty:
            st.session_state.portfolio = st.session_state.portfolio.drop(row_to_delete).reset_index(drop=True)
            st.success("השורה נמחקה!")
            st.rerun()
else:
    st.info("התיק שלך ריק כרגע. הוסף מניות למעלה.")