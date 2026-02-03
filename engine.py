import yfinance as yf
import pandas as pd
import pandas_ta as ta

# Target Indices
TARGET_INDICES = {
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "S&P500": "^GSPC",
    "NASDAQ": "^IXIC",
    "GOLD": "GC=F",
    "BITCOIN": "BTC-USD"
}

def fetch_data(ticker, period="2y"):
    """
    Fetches OHLCV data from yfinance.
    """
    df = yf.download(ticker, period=period, progress=False, multi_level_index=False)
    if df.empty:
        return None
    # Ensure standard column names if needed, though yfinance usually fits well with pandas_ta
    return df

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
    Calculates ATR (N-value) with length 20.
    """
    if df is None or len(df) < length:
        return None
    
    # pandas_ta requires High, Low, Close
    atr = ta.atr(df['High'], df['Low'], df['Close'], length=length)
    return atr.iloc[-1]

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
        
