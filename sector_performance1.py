import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import plotly.express as px
import io

# ----- APP CONFIGURATION -----
st.set_page_config(page_title="Growth vs Value Performance Tracker", layout="wide")
st.title("📊 Growth vs Value Performance Tracker")
st.markdown("""
Track and analyze the performance of Growth vs. Value stocks across multiple timeframes.
Upload an Excel/CSV file (with a 'Symbol' column and a 'Style' column: Growth or Value), or enter tickers manually.
""")

# ----- SIDEBAR -----
with st.sidebar:
    st.header("Input Options")
    upload_option = st.radio(
        "How would you like to provide tickers?",
        ("Upload Excel/CSV File", "Enter Manually")
    )
    uploaded_file = None
    manual_tickers = ""
    if upload_option == "Upload Excel/CSV File":
        uploaded_file = st.file_uploader(
            "Upload Excel/CSV file with symbols and style",
            type=["xlsx", "xls", "csv"],
            help="File must contain columns: 'Symbol' and 'Style' (Growth/Value)."
        )
    else:
        manual_tickers = st.text_area(
            "Enter tickers (one per line, format: SYMBOL,STYLE):",
            help="Example: AAPL,Growth\\nJPM,Value\\nGOOGL,Growth"
        )
    timeframes = st.multiselect(
        "Select timeframes to analyze",
        ["5 Days", "10 Days", "15 Days", "20 Days", "3 Months"],
        default=["5 Days", "20 Days"]
    )
    analyze_button = st.button("Analyze Growth vs Value Performance")

# ----- HELPER FUNCTIONS -----
@st.cache_data(ttl=3600)
def get_company_name(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        return info.get('longName', symbol)
    except Exception:
        return symbol

def calculate_returns(symbol, days):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    try:
        data = yf.download(symbol, start=start_date, end=end_date, progress=False)
        if len(data) > 0:
            start_price = data['Close'].iloc[0]
            end_price = data['Close'].iloc[-1]
            return (end_price - start_price) / start_price * 100
        return np.nan
    except Exception:
        return np.nan

def get_days_from_timeframe(tf_label):
    mapping = {
        "5 Days": 5,
        "10 Days": 10,
        "15 Days": 15,
        "20 Days": 20,
        "3 Months": 90
    }
    return mapping.get(tf_label, 5)

def analyze_styles(symbols_df, timeframes):
    if symbols_df.empty:
        st.warning("Please provide at least one valid symbol")
        return None

    timeframe_days = {tf: get_days_from_timeframe(tf) for tf in timeframes}
    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []
    total = len(symbols_df)
    for i, row in symbols_df.iterrows():
        symbol = row['Symbol']
        style = row['Style']
        status_text.text(f"Processing {symbol} ({i+1}/{total})...")
        progress_bar.progress((i+1)/total)
        company = get_company_name(symbol)
        returns = {}
        for tf_label, days in timeframe_days.items():
            ret = calculate_returns(symbol, days)
            if isinstance(ret, pd.Series):
                ret = ret.iloc[0] if not ret.empty else np.nan
            if not pd.isna(ret):
                returns[tf_label] = float(ret)
        if returns:
            results.append({
                'Symbol': symbol,
                'Company': company,
                'Style': style,
                **returns
            })
    progress_bar.empty()
    status_text.empty()
    if not results:
        st.error("No valid data could be retrieved for the provided symbols.")
        return None
    return pd.DataFrame(results)

# ----- MAIN WORKFLOW -----
if analyze_button:
    try:
        # 1. Get symbols
        symbols_df = pd.DataFrame()
        if upload_option == "Upload Excel/CSV File" and uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                # Require Symbol and Style columns
                if all(col in df.columns for col in ['Symbol', 'Style']):
                    symbols_df = df[['Symbol', 'Style']].dropna()
                    symbols_df['Symbol'] = symbols_df['Symbol'].astype(str).str.upper()
                    symbols_df['Style'] = symbols_df['Style'].str.capitalize()
                    symbols_df = symbols_df[symbols_df['Style'].isin(['Growth', 'Value'])]
                else:
                    st.error("Your file must have columns 'Symbol' and 'Style' (with values Growth or Value).")
            except Exception as e:
                st.error(f"Error reading file: {e}")
        elif upload_option == "Enter Manually" and manual_tickers:
            manual_list = []
            for line in manual_tickers.strip().split('\n'):
                parts = [x.strip() for x in line.split(",")]
                if len(parts) == 2 and parts[1].capitalize() in ["Growth", "Value"]:
                    manual_list.append({'Symbol': parts[0].upper(), 'Style': parts[1].capitalize()})
            if manual_list:
                symbols_df = pd.DataFrame(manual_list)
        # 2. Check input validity
        if symbols_df.empty:
            st.warning("Please provide valid symbols with style (Growth/Value)")
        elif not timeframes:
            st.warning("Please select at least one timeframe")
        else:
            with st.spinner("Analyzing performance..."):
                results_df = analyze_styles(symbols_df, timeframes)
                if results_df is not None:
                    st.success("Analysis complete!")
                    # RAW DATA DISPLAY
                    st.subheader("Raw Data")
                    try:
                        display_df = results_df.copy()
                        for tf in timeframes:
                            if tf in display_df.columns:
                                display_df[tf] = pd.to_numeric(display_df[tf], errors='coerce')
                        format_dict = {tf: "{:.2f}%" for tf in timeframes if tf in display_df.columns}
                        st.dataframe(display_df.style.format(format_dict))
                    except Exception as e:
                        st.error(f"Error formatting data: {e}")
                        st.dataframe(results_df)
                    # STYLE AVERAGES & CHARTS
                    try:
                        numeric_cols = [tf for tf in timeframes if tf in results_df.columns]
                        style_avg = results_df.groupby('Style')[numeric_cols].mean(numeric_only=True).reset_index()
                        if not style_avg.empty:
                            st.subheader("Growth vs Value Averages")
                            for tf in numeric_cols:
                                fig = px.bar(
                                    style_avg.sort_values(by=tf, ascending=False),
                                    x='Style',
                                    y=tf,
                                    title=f'Growth vs Value Performance ({tf})',
                                    labels={tf: 'Return (%)'},
                                    color='Style',
                                    height=500
                                )
                                fig.update_layout(
                                    xaxis_title="Style",
                                    yaxis_title="Return (%)",
                                    hovermode="x"
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            # Highlights: Best/Worst
                            st.subheader("Performance Highlights")
                            cols = st.columns(len(numeric_cols))
                            for idx, tf in enumerate(numeric_cols):
                                with cols[idx]:
                                    best_style = style_avg.loc[style_avg[tf].idxmax()]
                                    worst_style = style_avg.loc[style_avg[tf].idxmin()]
                                    st.metric(
                                        label=f"Best Style ({tf})",
                                        value=best_style['Style'],
                                        delta=f"{float(best_style[tf]):.2f}%"
                                    )
                                    st.metric(
                                        label=f"Worst Style ({tf})",
                                        value=worst_style['Style'],
                                        delta=f"{float(worst_style[tf]):.2f}%"
                                    )
                    except Exception as e:
                        st.error(f"Error calculating group averages: {e}")
                    # DOWNLOAD BUTTON
                    try:
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            results_df.to_excel(writer, sheet_name='Stock Performance', index=False)
                            if 'style_avg' in locals():
                                style_avg.to_excel(writer, sheet_name='Style Averages', index=False)
                        output.seek(0)
                        st.download_button(
                            label="Download Full Results",
                            data=output,
                            file_name="growth_vs_value_performance.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception as e:
                        st.error(f"Error generating download file: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")

# ----- INITIAL HELP -----
if not analyze_button:
    st.info("""
    **How to use this app:**
    1. Upload an Excel/CSV file with columns 'Symbol' and 'Style' (Growth/Value)
       OR enter manually (format: SYMBOL,STYLE per line)
    2. Select the timeframes you want to analyze
    3. Click "Analyze Growth vs Value Performance"

    **Example Symbols (manual entry):**
    AAPL,Growth
    JPM,Value
    GOOGL,Growth
    """)

st.markdown("---")
st.markdown("""
**Data Source:** Yahoo Finance (free API)  
**Note:** Rate limits may apply for large lists. Analysis may take time.
""")
