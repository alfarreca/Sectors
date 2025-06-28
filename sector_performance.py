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

# Cache sector data to avoid repeated API calls
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
    except:
        return {'sector': 'Unknown', 'industry': 'Unknown', 'company': ticker}

# Function to calculate returns
def calculate_returns(ticker, days):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    
    try:
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if len(data) > 0:
            start_price = data['Close'].iloc[0]
            end_price = data['Close'].iloc[-1]
            return (end_price - start_price) / start_price * 100
        return None
    except:
        return None

# Main analysis function
def analyze_sectors(tickers, timeframes):
    if not tickers:
        st.warning("Please provide at least one valid ticker")
        return None
    
    # Convert timeframe labels to days
    timeframe_days = {tf: int(tf.split()[0]) for tf in timeframes}
    
    # Initialize progress bar
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
            if ret is not None:
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

# Process inputs and display results
if analyze_button:
    # Get tickers from the selected input method
    if upload_option == "Upload Excel File" and uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            # Try to find a column with tickers
            ticker_columns = [col for col in df.columns if 'ticker' in col.lower() or 'symbol' in col.lower()]
            if ticker_columns:
                tickers = df[ticker_columns[0]].dropna().astype(str).unique().tolist()
            else:
                # Assume first column contains tickers
                tickers = df.iloc[:, 0].dropna().astype(str).unique().tolist()
        except Exception as e:
            st.error(f"Error reading file: {e}")
            tickers = []
    elif upload_option == "Enter Manually" and manual_tickers:
        # Parse manually entered tickers
        if "," in manual_tickers:
            tickers = [t.strip().upper() for t in manual_tickers.split(",")]
        else:
            tickers = [t.strip().upper() for t in manual_tickers.split("\n") if t.strip()]
    else:
        tickers = []
    
    # Clean tickers
    tickers = [t for t in tickers if t and not t.isspace()]
    
    if not tickers:
        st.warning("Please provide valid ticker symbols")
    elif not timeframes:
        st.warning("Please select at least one timeframe")
    else:
        with st.spinner("Analyzing sector performance..."):
            results_df = analyze_sectors(tickers, timeframes)
            
            if results_df is not None:
                st.success("Analysis complete!")
                
                # Display raw data
                st.subheader("Raw Data")
                st.dataframe(results_df.style.format(subset=timeframes, formatter="{:.2f}%"))
                
                # Calculate sector averages
                sector_avg = results_df.groupby('Sector')[timeframes].mean().reset_index()
                sector_avg = sector_avg.sort_values(by=timeframes[0], ascending=False)
                
                # Display sector performance
                st.subheader("Sector Performance Averages")
                
                # Plot for each timeframe
                for tf in timeframes:
                    fig = px.bar(
                        sector_avg,
                        x='Sector',
                        y=tf,
                        title=f'Sector Performance ({tf})',
                        labels={tf: 'Return (%)'},
                        color=tf,
                        color_continuous_scale=px.colors.diverging.RdYlGn,
                        height=500
                    )
                    fig.update_layout(
                        xaxis_title="Sector",
                        yaxis_title="Return (%)",
                        hovermode="x"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Show best/worst performing sectors
                st.subheader("Performance Highlights")
                
                cols = st.columns(len(timeframes))
                for idx, tf in enumerate(timeframes):
                    with cols[idx]:
                        st.metric(
                            label=f"Best Sector ({tf})",
                            value=sector_avg.iloc[0]['Sector'],
                            delta=f"{sector_avg.iloc[0][tf]:.2f}%"
                        )
                        
                        st.metric(
                            label=f"Worst Sector ({tf})",
                            value=sector_avg.iloc[-1]['Sector'],
                            delta=f"{sector_avg.iloc[-1][tf]:.2f}%"
                        )
                
                # Download button for results
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    results_df.to_excel(writer, sheet_name='Stock Performance', index=False)
                    sector_avg.to_excel(writer, sheet_name='Sector Averages', index=False)
                output.seek(0)
                
                st.download_button(
                    label="Download Full Results",
                    data=output,
                    file_name="sector_performance_analysis.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
else:
    # Show example when the app first loads
    st.info("""
    **How to use this app:**
    1. Upload an Excel/CSV file with tickers or enter them manually
    2. Select the timeframes you want to analyze
    3. Click "Analyze Sector Performance"
    
    **Example Tickers:** AAPL, MSFT, GOOGL, AMZN, TSLA, JPM, WMT, XOM
    """)

# Add some footer information
st.markdown("---")
st.markdown("""
**Data Source:** Yahoo Finance (free API)  
**Note:** Rate limits may apply with many tickers. Analysis may take time for large lists.
""")
