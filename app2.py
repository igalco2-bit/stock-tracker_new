import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="מעקב תיק מניות אוטומטי", page_icon="📈", layout="centered")

st.title("📈 מעקב תיק מניות אוטומטי")

# מילון עזר חכם לתרגום שמות בעברית לסימולים של Yahoo Finance
hebrew_to_ticker = {
    "עין שלישית": "THES.TA",
    "שופרסל": "SAE.TA",
    "בנק הפועלים": "POLI.TA",
    "בנק לאומי": "LUMI.TA",
    "איילון": "AYAL.TA",
    "טבע": "TEVA"
}

# אתחול התיק ב-Session State
if "portfolio" not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=["מניה", "סימול", "שער קניה", "כמות"])

st.subheader("הוספת מניה חדשה")

with st.form("add_stock_form"):
    col1, col2 = st.columns(2)
    with col1:
        stock_name_input = st.text_input("שם המניה (למשל: עין שלישית, שופרסל)")
    with col2:
        buy_price = st.number_input("שער קנייה", min_value=0.0, format="%.2f")
    
    quantity = st.number_input("כמות מניות", min_value=1, value=1)
    
    submit_button = st.form_submit_button("הוסף לתיק")

    if submit_button:
        if stock_name_input:
            # בדיקה האם הקלידו שם בעברית שקיים במילון שלנו
            clean_name = stock_name_input.strip()
            if clean_name in hebrew_to_ticker:
                ticker_symbol = hebrew_to_ticker[clean_name]
                display_name = clean_name
            else:
                # אם לא נמצא במילון, נניח שהקלידו סימול באנגלית (למשל AAPL או THES.TA)
                ticker_symbol = clean_name.upper()
                if not ticker_symbol.endswith(".TA") and len(ticker_symbol) <= 5 and ticker_symbol.isalpha():
                    # אפשרות להוסיף אוטומטית .TA אם נראה כמו מניה ישראלית קצרה, או להשאיר כפי שהוא
                    pass
                display_name = clean_name

            # הוספה לטבלה
            new_row = pd.DataFrame({
                "מניה": [display_name],
                "סימול": [ticker_symbol],
                "שער קניה": [buy_price],
                "כמות": [quantity]
            })
            
            st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_row], ignore_index=True)
            st.success(f"המניה {display_name} נוספה בהצלחה!")
        else:
            st.warning("נא להזין שם מניה.")

st.markdown("---")
st.subheader("התיק שלי")

if not st.session_state.portfolio.empty:
    # שליפת נתונים מעודכנים מ-Yahoo Finance
    current_prices = []
    profits_losses = []

    for index, row in st.session_state.portfolio.iterrows():
        ticker = row["סימול"]
        buy = row["שער קניה"]
        try:
            stock_data = yf.Ticker(ticker)
            # ניסיון לקבל את המחיר הנוכחי
            todays_data = stock_data.history(period="1d")
            if not todays_data.empty:
                current_price = todays_data['Close'].iloc[-1]
            else:
                current_price = buy # גיבוי אם אין נתון
        except Exception:
            current_price = buy

        current_prices.append(current_price)
        
        # חישוב אחוז רווח/הפסד
        if buy > 0:
            pl_pct = ((current_price - buy) / buy) * 100
        else:
            pl_pct = 0.0
        profits_losses.append(f"{pl_pct:+.2f}%")

    display_df = st.session_state.portfolio.copy()
    display_df["שער נוכחי"] = [f"{p:.2f}" for p in current_prices]
    display_df["רווח/הפסד"] = profits_losses

    st.dataframe(display_df, use_container_width=True)

    # מחיקת שורה
    st.subheader("מחיקת מניה מהתיק")
    row_to_delete = st.number_input("הכנס מספר שורה למחיקה", min_value=0, max_value=max(0, len(st.session_state.portfolio)-1), step=1)
    if st.button("מחק שורה נבחרת"):
        if not st.session_state.portfolio.empty:
            st.session_state.portfolio = st.session_state.portfolio.drop(row_to_delete).reset_index(drop=True)
            st.success("השורה נמחקה!")
            st.rerun()
else:
    st.info("התיק שלך ריק כרגע. הוסף מניות למעלה.")
