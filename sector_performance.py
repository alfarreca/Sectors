import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import plotly.express as px
import io

# App title and description
st.set_page_config(page_title="Sector Performance Tracker", layout="wide")
st.title("📊 Sector Performance Tracker")
st.markdown("""
Analyze sector performance across different timeframes using your custom ticker list.
Upload an Excel file with tickers or enter them manually.
""")

# Sidebar for inputs
with st.sidebar:
    st.header("Input Options")
    upload_option = st.radio(
        "How would you like to provide tickers?",
        ("Upload Excel File", "Enter Manually")
    )
    
    if upload_option == "Upload Excel File":
        uploaded_file = st.file_uploader(
            "Upload Excel file with tickers",
            type=["xlsx", "xls", "csv"],
            help="File should contain a column with ticker symbols"
        )
    else:
        manual_tickers = st.text_area(
            "Enter tickers (one per line or comma-separated)",
            help="Example: AAPL, MSFT, GOOGL\nor one per line"
        )

    timeframes = st.multiselect(
        "Select timeframes to analyze",
        ["5 Days", "10 Days", "15 Days", "20 Days"],
        default=["5 Days", "20 Days"]
    )
    
    analyze_button = st.button("Analyze Sector Performance")

@st.cache_data(ttl=3600)
def get_sector_info(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            'sector': info.get('sector', 'Unknown'),
            'industry': info.get('industry', 'Unknown'),
            'company': info.get('longName', ticker)
        }
    except Exception as e:
        st.warning(f"Couldn't fetch info for {ticker}: {str(e)}")
        return {'sector': 'Unknown', 'industry': 'Unknown', 'company': ticker}

def calculate_returns(ticker, days):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    
    try:
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if len(data) > 0:
            start_price = data['Close'].iloc[0]
            end_price = data['Close'].iloc[-1]
            return (end_price - start_price) / start_price * 100
        return np.nan
    except Exception as e:
        st.warning(f"Couldn't fetch data for {ticker}: {str(e)}")
        return np.nan

def analyze_sectors(tickers, timeframes):
    if not tickers:
        st.warning("Please provide at least one valid ticker")
        return None
    
    timeframe_days = {tf: int(tf.split()[0]) for tf in timeframes}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []
    total_tickers = len(tickers)
    
    for i, ticker in enumerate(tickers):
        status_text.text(f"Processing {ticker} ({i+1}/{total_tickers})...")
        progress_bar.progress((i + 1) / total_tickers)
        
        sector_info = get_sector_info(ticker)
        returns = {}
        
        for tf_label, days in timeframe_days.items():
            ret = calculate_returns(ticker, days)
            if not pd.isna(ret):
                returns[tf_label] = ret
        
        if returns:
            results.append({
                'Ticker': ticker,
                'Company': sector_info['company'],
                'Sector': sector_info['sector'],
                'Industry': sector_info['industry'],
                **returns
            })
    
    progress_bar.empty()
    status_text.empty()
    
    if not results:
        st.error("No valid data could be retrieved for the provided tickers.")
        return None
    
    return pd.DataFrame(results)

if analyze_button:
    tickers = []
    if upload_option == "Upload Excel File" and uploaded_file is not None:
        df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(('xls', 'xlsx')) else pd.read_csv(uploaded_file)
        tickers = df.iloc[:, 0].dropna().astype(str).str.upper().unique().tolist()
    elif upload_option == "Enter Manually" and manual_tickers:
        tickers = [t.strip().upper() for t in manual_tickers.replace(',', '\n').split("\n") if t.strip()]

    if tickers and timeframes:
        with st.spinner("Analyzing sector performance..."):
            results_df = analyze_sectors(tickers, timeframes)
            if results_df is not None:
                st.success("Analysis complete!")
                st.dataframe(results_df)

                sector_avg = results_df.groupby('Sector').mean().reset_index()
                if not sector_avg.empty:
                    st.subheader("Sector Performance Averages")
                    for tf in timeframes:
                        sorted_avg = sector_avg.sort_values(by=tf, ascending=False)
                        fig = px.bar(sorted_avg, x='Sector', y=tf, title=f'Sector Performance ({tf})', labels={tf: 'Return (%)'})
                        st.plotly_chart(fig)

                    st.subheader("Performance Highlights")
                    for tf in timeframes:
                        best_sector = sector_avg.loc[sector_avg[tf].idxmax()]
                        worst_sector = sector_avg.loc[sector_avg[tf].idxmin()]
                        st.metric(label=f"Best Sector ({tf})", value=best_sector['Sector'], delta=f"{best_sector[tf]:.2f}%")
                        st.metric(label=f"Worst Sector ({tf})", value=worst_sector['Sector'], delta=f"{worst_sector[tf]:.2f}%")

st.markdown("---")
st.markdown("""
**Data Source:** Yahoo Finance (free API)  
**Note:** Rate limits may apply with many tickers. Analysis may take time for large lists.
""")
