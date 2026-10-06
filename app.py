import os
import re
from datetime import datetime
from html import unescape

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="מעקב תיק מניות ישראלי",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

DB_FILE = "portfolio.csv"
COLUMNS = ["מניה", "סימול", "שער קניה"]
ERROR_TEXT = "❌ תקלה"

KNOWN_TICKER_FIXES = {"AURON.TA": "ORON.TA", "RIMON.TA": "RMON.TA"}

DEFAULT_PORTFOLIO = {
    "מניה": ["ארית תעשיות", "שופרסל", "הבורסה לניירות ערך", "אירודרום", "טאואר", "אורון", "רימון", "Soxx"],
    "סימול": ["ARYT.TA", "SAE.TA", "TASE.TA", "ARDM.TA", "TSEM.TA", "ORON.TA", "RMON.TA", "SOXX"],
    "שער קניה": [5958.0, 4513.0, 14700.0, 425.0, 64827.0, 3418.0, 12871.0, 650.0],
}

def load_portfolio():
    if not os.path.exists(DB_FILE):
