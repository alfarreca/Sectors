# ----- SIDEBAR -----
with st.sidebar:
    st.header("Input Options")
    upload_option = st.radio(
        "How would you like to provide tickers?",
        ("Upload Excel File", "Enter Manually")
    )
    uploaded_file = None
    manual_tickers = ""
    if upload_option == "Upload Excel File":
        uploaded_file = st.file_uploader(
            "Upload Excel/CSV file with tickers",
            type=["xlsx", "xls", "csv"],
            help="The file should contain a column with ticker symbols."
        )
    else:
        manual_tickers = st.text_area(
            "Enter tickers (one per line or comma-separated):",
            help="Example: AAPL, MSFT, GOOGL or one per line"
        )
    timeframes = st.multiselect(
        "Select timeframes to analyze",
        ["5 Days", "10 Days", "15 Days", "20 Days", "3 Months"],
        default=["5 Days", "20 Days"]
    )
    analyze_button = st.button("Analyze Sector Performance")

# ----- HELPER FUNCTIONS -----
def get_days_from_timeframe(tf_label):
    mapping = {
        "5 Days": 5,
        "10 Days": 10,
        "15 Days": 15,
        "20 Days": 20,
        "3 Months": 90
    }
    return mapping.get(tf_label, 5)

def analyze_sectors(tickers, timeframes):
    if not tickers:
        st.warning("Please provide at least one valid ticker")
        return None
    timeframe_days = {tf: get_days_from_timeframe(tf) for tf in timeframes}
    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []
    total = len(tickers)
    for i, ticker in enumerate(tickers):
        status_text.text(f"Processing {ticker} ({i+1}/{total})...")
        progress_bar.progress((i+1)/total)
        sector_info = get_sector_info(ticker)
        returns = {}
        for tf_label, days in timeframe_days.items():
            ret = calculate_returns(ticker, days)
            if isinstance(ret, pd.Series):
                ret = ret.iloc[0] if not ret.empty else np.nan
            if not pd.isna(ret):
                returns[tf_label] = float(ret)
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
