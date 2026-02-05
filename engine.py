import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import re

def get_domestic_gold_price():
    """
    Fetches the domestic gold price (KRX Gold Spot) from Naver Finance.
    URL: https://m.stock.naver.com/marketindex/metals/M04020000
    """
    url = "https://m.stock.naver.com/marketindex/metals/M04020000"
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1'
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        # Search for "closePrice":"235,440" or similar
        match = re.search(r'\"closePrice\":\"([\d,]+)\"', r.text)
        if match:
            price_str = match.group(1).replace(',', '')
            return float(price_str)
        
        # Fallback: search for "nv":235440
        match = re.search(r'\"nv\":(\d+)', r.text)
        if match:
            return float(match.group(1))
            
    except Exception as e:
        print(f"Error fetching domestic gold price: {e}")
    
    return None

# Target Indices
TARGET_INDICES = {
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "S&P500": "^GSPC",
    "NASDAQ": "^IXIC",
    "GOLD": "GC=F",
    "BITCOIN": "BTC-USD",
    "NIKKEI225": "^N225",
    "SHANGHAI": "000001.SS",
    "HANGSENG": "^HSI",
    "UK_FTSE": "^FTSE"
}

# Stock Universes (Subset for Performance)
US_UNIVERSE = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "GOOG", "META", "TSLA", "BRK-B", "UNH",
    "JNJ", "XOM", "V", "PG", "MA", "AVGO", "HD", "CVX", "LLY", "ABBV",
    "COST", "PEP", "ADBE", "CSCO", "AMD", "QCOM", "TXN", "INTC", "AMGN", "HON",
    "INTU", "SBUX", "MDLZ", "ISRG", "GILD", "BKNG", "AMAT", "ADP", "VRTX", "MU"
]

KR_UNIVERSE = [
    "005930.KS", "000660.KS", "373220.KS", "207940.KS", "005380.KS", "005935.KS", "000270.KS", "068270.KS", "005490.KS", "105560.KS",
    "051910.KS", "035420.KS", "000810.KS", "055550.KS", "012330.KS", "028260.KS", "032830.KS", "006400.KS", "035720.KS", "086790.KS",
    "003550.KS", "066570.KS", "011200.KS", "009150.KS", "015760.KS", "003670.KS", "034730.KS", "017670.KS", "128940.KS", "010130.KS",
    "011070.KS", "011170.KS", "000720.KS", "005070.KS", "004020.KS", "000100.KS", "011780.KS", "030240.KS", "001040.KS", "003470.KS"
]

def fetch_data(ticker, period="2y"):
    """
    Fetches OHLCV data from yfinance usando Ticker().history for better reliability.
    """
    try:
        tk = yf.Ticker(ticker)
        df = tk.history(period=period)
        if df.empty:
            return None
        return df
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None


def analyze_market_phase(df):
    """
    Analyzes the 'High Altitude' 6-Phase Market Cycle.
    
    Logic:
    Calculates 20-day and 60-day SMAs.
    
    Phases:
    1. Bull Market Start: Price > 20MA > 60MA
    2. Adjustment in Bull: 20MA > Price > 60MA
    3. Bull Trap / Top Reversal warning: 20MA > 60MA > Price (Short term dip below long term) 
       *Correction*: Usually standard logic is Price relationship.
       Let's stick to a robust standard definition often used in this context:
       
       Phase 1 (Bullish): Price > 20 > 60
       Phase 2 (Correction in Uptrend): 20 > Price > 60
       Phase 3 (Box/Transition): 20 > 60 > Price
       Phase 4 (Bearish): 60 > 20 > Price (Death Cross confirmed, full bear)
       Phase 5 (Rebound in Downtrend): 60 > Price > 20
       Phase 6 (Bottom/Transition): Price > 60 > 20 (Golden Cross forming)
       
    Returns:
        int: Phase number (1-6)
        dict: Details including MA values
    """
    if df is None or len(df) < 60:
        return None, {}

    # Calculate MAs
    # Ensure we use Close price
    close = df['Close']
    ma20 = ta.sma(close, length=20)
    ma60 = ta.sma(close, length=60)
    
    # Get latest values
    current_price = close.iloc[-1]
    curr_ma20 = ma20.iloc[-1]
    curr_ma60 = ma60.iloc[-1]
    
    # Determine Phase
    phase = 0
    
    if curr_ma20 > curr_ma60:
        if current_price > curr_ma20:
            phase = 1
        elif current_price > curr_ma60:
            phase = 2
        else:
            phase = 3
    else: # ma60 >= ma20
        if current_price < curr_ma20:
            phase = 4
        elif current_price < curr_ma60:
            phase = 5
        else:
            phase = 6
            
    return phase, {
        "price": current_price,
        "ma20": curr_ma20,
        "ma60": curr_ma60
    }

def track_mdd(df):
    """
    Calculates MDD based on 1-year rolling max.
    Determines if recovery rate is >= 80%.
    """
    if df is None or len(df) < 252: # Approx 1 year trading days
        return None, {}

    # Focus on last 1 year (approx 252 days) for the calculation window, 
    # but we can just take the whole series if we want "recent 1 year MDD"
    recent_df = df.tail(252).copy()
    
    # Roll max
    # We want the max since the start of this 1 year window? 
    # Or strict "Recent 1 year high" as the reference for MDD? 
    # Usually MDD is (Price - RollingMax) / RollingMax.
    # We will find the global Max in the last 1 year and calculate Drop from that Max.
    
    period_max = recent_df['Close'].max()
    current_price = recent_df['Close'].iloc[-1]
    
    mdd = (current_price - period_max) / period_max
    
    # Recovery Rate
    # Often defined as: (Current - Low) / (High - Low)
    # where High is the 1-year High, and Low is the Lowest point AFTER that High.
    # Let's find the Low after the Date of period_max.
    
    # Find index of max
    period_max_idx = recent_df['Close'].idxmax()
    
    # Slice from max to end
    after_peak = recent_df.loc[period_max_idx:]
    period_low_after_peak = after_peak['Close'].min()
    
    if period_max == period_low_after_peak:
        recovery_rate = 1.0 # No drop
    else:
        recovery_rate = (current_price - period_low_after_peak) / (period_max - period_low_after_peak)
        
    is_recovered = recovery_rate >= 0.8
    
    return mdd, {
        "high_1y": period_max,
        "low_since_high": period_low_after_peak,
        "recovery_rate": recovery_rate,
        "is_recovered": is_recovered
    }

def calculate_atr(df, length=20):
    """
    Calculates ATR (N-value) with length 20 using EMA smoothing.
    Uses the latest available data point (iloc[-1]) for real-time tracking.
    """
    if df is None or len(df) < length:
        return None
    
    # Using mamode='ema' to match popular trading platform calculations (e.g. Kiwoom, TradingView EMA)
    atr_series = ta.atr(df['High'], df['Low'], df['Close'], length=length, mamode='ema')
    
    return atr_series.iloc[-1]

def get_dividend_history(ticker, count=5):
    """
    Fetches historical dividend data for a ticker.
    """
    try:
        tk = yf.Ticker(ticker)
        divs = tk.dividends
        if divs.empty:
            return None
        
        # Sort by date descending and take top N
        latest_divs = divs.sort_index(ascending=False).head(count)
        
        results = []
        for date, value in latest_divs.items():
            results.append({
                "Date": date.strftime("%Y-%m-%d"),
                "Amount": value
            })
        return results
    except Exception as e:
        print(f"Error fetching dividends for {ticker}: {e}")
        return None

def screen_stocks(market_type="US"):
    """
    Screens stocks from the universe based on Turtle Strategy criteria.
    
    Criteria (US):
    - 20-day High breakout
    - SMA5 rising for 2+ days
    - SMA200 rising for 2+ days
    - Market Cap >= 100,000M
    
    Criteria (KR):
    - 20-day High breakout
    - Strength/Volume confirmation (Proxy for Supply)
    """
    universe = US_UNIVERSE if market_type == "US" else KR_UNIVERSE
    results = []
    
    for ticker in universe:
        try:
            df = yf.download(ticker, period="1y", progress=False, multi_level_index=False)
            if df is None or len(df) < 200: continue
            
            # 1. 20-day High Breakout
            # Today's high must be the highest in the last 20 days
            high_20 = df['High'].tail(20)
            is_20d_high = high_20.iloc[-1] >= high_20.max()
            
            if not is_20d_high: continue
            
            # 2. SMA Trends (US)
            sma5 = ta.sma(df['Close'], length=5)
            sma200 = ta.sma(df['Close'], length=200)
            
            sma5_rising = sma5.iloc[-1] > sma5.iloc[-2] > sma5.iloc[-3]
            sma200_rising = sma200.iloc[-1] > sma200.iloc[-2]
            
            # 3. Market Cap / Supply Filters
            info = yf.Ticker(ticker).info
            market_cap = info.get('marketCap', 0)
            
            if market_type == "US":
                # Market Cap >= 100,000M (100 Billion)
                # Note: yfinance cap is in absolute units (USD)
                if market_cap < 100_000_000_000: continue
                if not (sma5_rising and sma200_rising): continue
            else: # KR
                # Supply Proxy: Volume > 20d Avg Volume + Positive Price Action
                avg_vol = df['Volume'].tail(20).mean()
                curr_vol = df['Volume'].iloc[-1]
                vol_strong = curr_vol > avg_vol
                if not vol_strong: continue
                
            # If all passed, calculate Turtle metrics
            n_val = calculate_atr(df)
            
            results.append({
                "ticker": ticker,
                "name": info.get('shortName', ticker),
                "current_price": df['Close'].iloc[-1],
                "1N": n_val,
                "market_cap": market_cap,
                "status": "Breakout"
            })
        except Exception as e:
            print(f"Error screening {ticker}: {e}")
            continue
            
    return pd.DataFrame(results)

def run_analysis():
    results = {}
    print(f"Starting Analysis for: {', '.join(TARGET_INDICES.keys())}")
    
    for name, ticker in TARGET_INDICES.items():
        print(f"Fetching {name} ({ticker})...")
        df = fetch_data(ticker)
        
        if df is None:
            print(f"Failed to fetch data for {name}")
            continue
            
        # Add MAs for Charting
        if len(df) >= 60:
            df['MA5'] = ta.sma(df['Close'], length=5)
            df['MA20'] = ta.sma(df['Close'], length=20)
            df['MA40'] = ta.sma(df['Close'], length=40)
            df['MA60'] = ta.sma(df['Close'], length=60)
            
        # Add MDD & Recovery Calculation (Time Series)
        # Using cumulative max as 'Peak' (High Water Mark) for the fetched period (2y)
        df['Peak'] = df['Close'].cummax()
        df['Drawdown'] = (df['Close'] - df['Peak']) / df['Peak']
        # Required Gain to recover to Peak: (Peak - Close) / Close
        df['Recovery_Needed'] = (df['Peak'] - df['Close']) / df['Close']
            
        phase, phase_info = analyze_market_phase(df)
        mdd, mdd_info = track_mdd(df)
        n_val = calculate_atr(df)
        
        results[name] = {
            "phase": phase,
            "phase_info": phase_info,
            "mdd": mdd,
            "mdd_info": mdd_info,
            "n_value": n_val,
            "data": df  # Return DataFrame for charting
        }
        
    return results

if __name__ == "__main__":
    # If run directly, perform a quick test
    data = run_analysis()
    for name, res in data.items():
        print(f"\n[{name}]")
        print(f"  Phase: {res['phase']} ({res['phase_info']})")
        print(f"  MDD: {res['mdd']:.2%} (Recovery: {res['mdd_info'].get('recovery_rate', 0):.2%}, Recovered: {res['mdd_info'].get('is_recovered')})")
        print(f"  N-Value (ATR): {res['n_value']:.4f}")
        
