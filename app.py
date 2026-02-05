import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import engine

# --- Configuration ---
st.set_page_config(page_title="Strock Board", layout="wide")

# Custom CSS for Premium Look
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .stApp {
        background-color: #f8f9fa;
    }
    .market-card {
        border-radius: 12px;
        padding: 20px;
        background-color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border: 1px solid #eee;
        margin-bottom: 20px;
        transition: transform 0.2s ease-in-out;
    }
    .market-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 15px rgba(0, 0, 0, 0.1);
    }
    .phase-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 8px;
    }
    .price-text {
        font-size: 1.5em;
        font-weight: 700;
        color: #1a1a1a;
    }
    .change-text {
        font-size: 0.9em;
        margin-left: 8px;
    }
    .buy-signal {
        background-color: rgba(46, 204, 113, 0.1);
        border: 1px solid #2ecc71;
        border-radius: 8px;
        padding: 12px;
        margin: 15px 0;
        text-align: center;
        color: #27ae60;
        font-weight: 700;
    }
    .mdd-container {
        display: flex;
        justify-content: space-between;
        margin-top: 15px;
        padding-top: 15px;
        border-top: 1px solid #f0f0f0;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# --- Portfolio Data ---
DOMESTIC_PORTFOLIO = [
    {"ticker": "005930.KS", "buy_price": 77800.0, "quantity": 2, "name": "삼성전자"},
    {"ticker": "015760.KS", "buy_price": 44600.0, "quantity": 6, "name": "한국전력"},
]

OVERSEAS_PORTFOLIO = [
    {"ticker": "AMZN", "buy_price": 216.20, "quantity": 1, "name": "아마존닷컴"},
    {"ticker": "GOOGL", "buy_price": 265.11, "quantity": 2, "name": "알파벳 A"},
]

# DCA (적립식) Portfolio Data
DCA_PORTFOLIO = [
    {"ticker": "133690.KS", "buy_price": 108900, "quantity": 3, "name": "TIGER 미국나스닥100"},
    {"ticker": "360750.KS", "buy_price": 18125.78, "quantity": 32, "name": "TIGER 미국S&P500"},
    {"ticker": "453870.KS", "buy_price": 13439.32, "quantity": 125, "name": "TIGER 인도니프티50"},
    {"ticker": "102110.KS", "buy_price": 31460, "quantity": 16, "name": "TIGER 200"},
    {"ticker": "GC=F", "buy_price": 181778.91, "quantity": 11, "name": "금 99.99K"},
]
DCA_CASH = 2073504.0 + 294975.0 # 이전에 있던 예수금 + 금 계좌의 예수금

# Dividend (배당주) Portfolio Data
DIVIDEND_PORTFOLIO = [
    {"ticker": "JEPI", "buy_price_usd": 54.4955, "quantity": 29, "name": "JP Morgan Equity Premium Income"},
    {"ticker": "SCHD", "buy_price_usd": 25.5364, "quantity": 305, "name": "Schwab US Dividend Equity"},
    {"ticker": "SCHG", "buy_price_usd": 22.59, "quantity": 33, "name": "Schwab US Large-Cap Growth"},
    {"ticker": "SPYM", "buy_price_usd": 58.9975, "quantity": 16, "name": "SPDR Portfolio S&P 500 ETF"},
]

# --- Helper Functions ---
# --- Helper Functions (Existing) ---
def render_market_card(key, data):
    """지수별 정보를 카드로 렌더링"""
    phase = data['phase']
    recovery = data['mdd_info'].get('recovery_rate', 0)
    df = data.get('data')
    
    color, icon, desc = get_phase_info(phase)
    
    # 이름 변환
    names = {
        "KOSPI": "코스피 (KOSPI)", "KOSDAQ": "코스닥 (KOSDAQ)",
        "US_SP500": "미국 S&P 500", "US_NASDAQ": "미국 나스닥",
        "GOLD": "금 (Gold)", "BITCOIN": "비트코인"
    }
    korean_name = names.get(key, key)

    current_price = 0
    current_dd = 0
    change_html = ""
    
    if df is not None and len(df) >= 2:
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        current_price = last_row['Close']
        prev_price = prev_row['Close']
        change_point = current_price - prev_price
        change_pct = (change_point / prev_price) * 100
        current_dd = last_row['Drawdown']
        
        if change_point > 0:
            change_html = f"<span class='change-text' style='color: #ff4b4b;'>▲{change_point:,.2f} (+{change_pct:.2f}%)</span>"
        elif change_point < 0:
            change_html = f"<span class='change-text' style='color: #4b4bff;'>▼{abs(change_point):,.2f} ({change_pct:.2f}%)</span>"
        else:
            change_html = f"<span class='change-text' style='color: gray;'>0.00 (0.00%)</span>"

    # 상태 및 알림
    is_safe_mode = current_dd > -0.05
    buy_signal_html = ""
    if recovery >= 0.8:
        buy_signal_html = f'<div class="buy-signal">✨ 강력 매수 기회 (회복률 {recovery:.0%})</div>'

    if is_safe_mode:
        stats_html = '<div style="margin-top: 15px; color: #2ecc71; font-weight: bold; text-align: center; border-top: 1px solid #f0f0f0; padding-top: 15px;">🚀 신고가 경신 / 고점 부근 (안정)</div>'
    else:
        stats_html = f'''
<div class="mdd-container">
    <span>📉 현재 MDD: <span style="font-weight:bold; color:#ff4b4b;">{current_dd:.2%}</span></span>
    <span>💪 회복률: <span style="font-weight:bold; color:#1a1a1a;">{recovery:.2%}</span></span>
</div>'''

    # 카드 HTML 렌더링
    st.markdown(f"""
<div class="market-card" style="border-top: 4px solid {color};">
<div style="display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 10px;">
<h3 style="margin:0; font-size: 1.2em;">{icon} {korean_name}</h3>
</div>
<div class="phase-badge" style="background-color: {color}20; color: {color}; border: 1px solid {color}40;">
{phase}국면: {desc}
</div>
<div style="margin: 10px 0;">
<span class="price-text">{current_price:,.2f}</span>
{change_html}
</div>
{buy_signal_html}
{stats_html}
</div>
""", unsafe_allow_html=True)

def get_phase_info(phase):
    """국면별 색상, 아이콘, 설명을 반환"""
    if phase == 1:
        return "green", "📈", "강세(상승) - 공격적 매수 구간"
    elif phase == 2:
        return "orange", "⚠️", "조정 - 분할 매수/관망"
    elif phase == 3:
        return "orange", "⚠️", "전환 - 보수적 접근"
    elif phase == 4:
        return "red", "📉", "약세(하락) - 보수적 관망 구간"
    elif phase == 5:
        return "red", "📉", "반등 - 기술적 반등 주의"
    elif phase == 6:
        return "gray", "➖", "회복 - 정찰병 진입"
    else:
        return "gray", "➖", "알 수 없음"

def check_dca_status():
    today = datetime.date.today()
    if 15 <= today.day <= 20:
        return "BUY"
    return "WAIT"

# --- Page Functions ---

def show_market_board():
    st.header("🌍 Market Board")
    
    if st.sidebar.button("데이터 새로고침"):
        st.cache_data.clear()
        
    days_to_show = st.sidebar.slider("차트 조회 기간 (일)", 30, 365, 100)
        
    # 데이터 로드
    with st.spinner("시장 데이터 분석 중..."):
        results = engine.run_analysis()

    # 카드 형태로 표시
    cols = st.columns(3)
    keys = list(results.keys())

    for i, key in enumerate(keys):
        col = cols[i % 3]
        with col:
            render_market_card(key, results[key])
            
            # 차트 렌더링
            df = results[key].get('data')
            if df is not None and not df.empty:
                chart_data = df.tail(days_to_show)
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=chart_data.index, open=chart_data['Open'], high=chart_data['High'],
                    low=chart_data['Low'], close=chart_data['Close'], name='Price'
                ))
                if 'MA5' in chart_data.columns:
                    fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['MA5'], line=dict(color='green', width=1), name='MA5'))
                if 'MA20' in chart_data.columns:
                    fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['MA20'], line=dict(color='#ff4b4b', width=1), name='MA20'))
                if 'MA40' in chart_data.columns:
                    fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['MA40'], line=dict(color='orange', width=1), name='MA40'))
                
                fig.update_layout(
                    height=350, margin=dict(l=0, r=0, t=10, b=0),
                    xaxis_rangeslider_visible=False, showlegend=False,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(size=11)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("차트 데이터 없음")

def render_portfolio_table(portfolio, title, is_overseas=False):
    st.subheader(title)
    
    # 환율 정보 (미장의 경우)
    exchange_rate = 1.0
    if is_overseas:
        try:
            ex_data = engine.fetch_data("USDKRW=X", period="5d")
            if ex_data is not None and not ex_data.empty:
                exchange_rate = ex_data['Close'].iloc[-1]
            else:
                exchange_rate = 1450.0 # 기본값
        except:
            exchange_rate = 1450.0

    portfolio_data_mgt = []
    portfolio_data_pnl = []
    
    with st.spinner(f"{title} 분석 중..."):
        for item in portfolio:
            ticker = item['ticker']
            buy_price = item['buy_price']
            qty = item['quantity']
            name = item.get('name', ticker)
            
            df_ticker = engine.fetch_data(ticker)
            if df_ticker is None or df_ticker.empty: continue
                
            last_close = df_ticker['Close'].iloc[-1]
            prev_close = df_ticker['Close'].iloc[-2] if len(df_ticker) >= 2 else last_close
            change_1d = ((last_close - prev_close) / prev_close) * 100
            n_val = engine.calculate_atr(df_ticker)
            if n_val is None: continue
            
            # --- 1. 터틀 자금 관리 및 손절 데이터 ---
            n_pct = (n_val / prev_close) * 100 if prev_close > 0 else 0
            n2_val = 2 * n_val
            stop_loss = buy_price - n2_val
            loss_at_stop = n2_val * qty
            
            total_cost = buy_price * qty
            total_cost_krw = total_cost * exchange_rate if is_overseas else total_cost
            
            portfolio_data_mgt.append({
                "종목": name,
                "현재가": last_close,
                "매수가": buy_price,
                "1N": round(n_val, 2),
                "N(%)": f"{n_pct:.2f}%",
                "2N": round(n2_val, 2),
                "손절가": round(stop_loss, 2),
                "손절시 손해": round(loss_at_stop, 2),
                "보유수량": qty,
                "매수금액": total_cost,
                "원화금액": total_cost_krw
            })
            
            # --- 2. 수익 현황 및 불타기/익절 데이터 ---
            market_value = last_close * qty
            total_pl = market_value - total_cost
            pl_pct = (total_pl / total_cost) * 100 if total_cost > 0 else 0
            
            target_2n = buy_price + (2 * n_val)
            pyramid_status = "가능" if last_close >= target_2n else "미달"
            
            target_4n = buy_price + (4 * n_val)
            exit_status = "도달" if last_close >= target_4n else "미도달"
            
            portfolio_data_pnl.append({
                "종목": name,
                "티커": ticker,
                "현재가": last_close,
                "전일대비": f"{change_1d:+.2f}%",
                "평균단가": buy_price,
                "보유수량": qty,
                "총투자금": total_cost,
                "평가금액": market_value,
                "평가손익": total_pl,
                "수익률": f"{pl_pct:+.2f}%",
                "불타기(+2N)": round(target_2n, 2),
                "불타기여부": pyramid_status,
                "목표가(+4N)": round(target_4n, 2),
                "익절여부": exit_status
            })

    if portfolio_data_mgt:
        # 1. 자금 관리 표
        st.write("📋 **터틀 자금 관리 및 시뮬레이션 (ATR 기준)**")
        df_mgt = pd.DataFrame(portfolio_data_mgt)
        st.dataframe(
            df_mgt.style.format({
                "현재가": "{:,.2f}", "매수가": "{:,.2f}", "1N": "{:,.2f}", 
                "2N": "{:,.2f}", "손절가": "{:,.2f}", "손절시 손해": "{:,.2f}",
                "매수금액": "{:,.2f}", "원화금액": "{:,.0f}"
            }).applymap(lambda x: 'color: #ff4b4b; font-weight: bold;', subset=['손절가']),
            use_container_width=True
        )
        
        # 2. 수익 현황 및 불타기 표
        st.write("🎯 **수익 현황 및 불타기/익절 트래킹**")
        df_pnl = pd.DataFrame(portfolio_data_pnl)
        
        def style_status(val):
            if val in ["가능", "도달"]:
                return 'background-color: #e8f5e9; color: green; font-weight: bold;'
            return 'color: gray;'

        def style_pl_text(val):
            try:
                num = float(val.replace('%', '').replace('+', ''))
                return f'color: {"red" if num > 0 else "blue" if num < 0 else "black"};'
            except: return ''

        st.dataframe(
            df_pnl.style.format({
                "현재가": "{:,.2f}", "평균단가": "{:,.2f}", "총투자금": "{:,.2f}",
                "평가금액": "{:,.2f}", "평가손익": "{:+,.2f}", "불타기(+2N)": "{:,.2f}", "목표가(+4N)": "{:,.2f}"
            }).applymap(style_status, subset=['불타기여부', '익절여부'])
              .applymap(style_pl_text, subset=['전일대비', '수익률']),
            use_container_width=True
        )
        
        if is_overseas:
            st.caption(f"💡 현재 적용 환율: 1 USD = {exchange_rate:,.2f} KRW")
    else:
        st.write(f"{title} 데이터가 없습니다.")

def show_turtle_portfolio():
    st.header("🐢 터틀 보유 종목")
    st.markdown("""
    <div style="background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #eee; margin-bottom: 20px;">
    보유 항목들의 **터틀 대응 기준(N값, 손절가)** 및 자산 현황을 트래킹합니다.
    </div>
    """, unsafe_allow_html=True)
    
    render_portfolio_table(DOMESTIC_PORTFOLIO, "🇰🇷 국내 주식 (국장)", is_overseas=False)
    st.markdown("---")
    render_portfolio_table(OVERSEAS_PORTFOLIO, "🇺🇸 해외 주식 (미장)", is_overseas=True)

def show_turtle_search():
    st.header("🔍 터틀 종목 검색 & 스캐너")
    
    # 1. 시장 국면 상태 확인 (스캐너 작동 조건)
    st.subheader("🌐 시장 상태 확인")
    market_status = engine.run_analysis()
    
    col_stat1, col_stat2 = st.columns(2)
    with col_stat1:
        # 미장 상태 (나스닥 기준)
        nasdaq_phase = market_status.get("NASDAQ", {}).get("phase", 0)
        color, icon, p1 = get_phase_info(nasdaq_phase)
        is_us_ok = nasdaq_phase in [1, 2]
        status_color = color
        st.markdown(f"""
        <div style="padding:15px; border-radius:10px; border-left:5px solid {status_color}; background-color:white; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <b>🇺🇸 미장 (NASDAQ): Phase {nasdaq_phase} {icon}</b><br>
            조언: {p1}<br>
            스캐너 상태: {"✅ 가동 가능" if is_us_ok else "⚠️ 대기 (1,2국면 아님)"}
        </div>
        """, unsafe_allow_html=True)

    with col_stat2:
        # 국장 상태 (코스피 기준)
        kospi_phase = market_status.get("KOSPI", {}).get("phase", 0)
        color, icon, p1 = get_phase_info(kospi_phase)
        is_kr_ok = kospi_phase in [1, 2]
        status_color = color
        st.markdown(f"""
        <div style="padding:15px; border-radius:10px; border-left:5px solid {status_color}; background-color:white; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <b>🇰🇷 국장 (KOSPI): Phase {kospi_phase} {icon}</b><br>
            조언: {p1}<br>
            스캐너 상태: {"✅ 가동 가능" if is_kr_ok else "⚠️ 대기 (1,2국면 아님)"}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 2. 개별 종목 검색
    st.subheader("🎯 개별 종목 분석")
    ticker_input = st.text_input("종목 티커 입력 (예: TSLA, NVDA, 005930.KS)", "").upper()
    
    if ticker_input:
        with st.spinner(f"{ticker_input} 데이터 분석 중..."):
            df = engine.fetch_data(ticker_input)
            if df is not None and not df.empty:
                current_price = df['Close'].iloc[-1]
                n_val = engine.calculate_atr(df)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("현재가", f"{current_price:,.2f}")
                    st.metric("변동성 (20-day ATR)", f"{n_val:.2f}")
                
                with col2:
                    st.info(f"""
                    **🎯 터틀 대응 가이드:**
                    - **불타기 (+0.5N):** {current_price + (0.5 * n_val):,.2f}
                    - **1차 익절/불타기 (+2N):** {current_price + (2.0 * n_val):,.2f}
                    - **손절 기준 (-2N):** {current_price - (2.0 * n_val):,.2f}
                    """)
                
                # 차트 표시
                st.subheader("최근 차트")
                chart_data = df.tail(100)
                fig = go.Figure(data=[go.Candlestick(x=chart_data.index,
                                        open=chart_data['Open'],
                                        high=chart_data['High'],
                                        low=chart_data['Low'],
                                        close=chart_data['Close'])])
                fig.update_layout(xaxis_rangeslider_visible=False, height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("데이터를 불러올 수 없습니다. 티커를 확인해주세요.")

    st.markdown("---")

    # 3. 실시간 종목 스캐너
    st.subheader("🔥 터틀 종목 스캐너 (20일 신고가 & 추세)")
    col_scan1, col_scan2 = st.columns(2)
    
    with col_scan1:
        if st.button("🇺🇸 미장 종목 스캔", use_container_width=True):
            if not is_us_ok:
                st.warning("미장이 현재 1, 2국면이 아닙니다. (보수적 접근 권장)")
            
            with st.spinner("미장 유니버스 스캔 중 (S&P/Nasdaq)..."):
                results = engine.screen_stocks("US")
                if not results.empty:
                    st.success(f"{len(results)}개의 유망 종목 발견!")
                    render_scan_results(results)
                else:
                    st.info("조건을 충족하는 종목이 현재 없습니다.")

    with col_scan2:
        if st.button("🇰🇷 국장 종목 스캔", use_container_width=True):
            if not is_kr_ok:
                st.warning("국장이 현재 1, 2국면이 아닙니다. (보수적 접근 권장)")
                
            with st.spinner("국장 유니버스 스캔 중 (KOSPI 50)..."):
                results = engine.screen_stocks("KR")
                if not results.empty:
                    st.success(f"{len(results)}개의 유망 종목 발견!")
                    render_scan_results(results)
                else:
                    st.info("조건을 충족하는 종목이 현재 없습니다.")

def render_scan_results(df):
    # 결과 테이블 스타일링
    st.dataframe(
        df.style.format({
            "current_price": "{:,.2f}",
            "1N": "{:,.2f}",
            "market_cap": "{:,.0f}"
        }),
        use_container_width=True,
        column_order=["name", "ticker", "current_price", "1N", "status"]
    )

def show_dca_page():
    st.header("💰 적립식 매수 (DCA)")
    
    # 1. 종합 요약
    st.subheader("📊 계좌 요약")
    
    with st.spinner("적립식 계좌 분석 중..."):
        total_eval_val = 0
        total_buy_val = 0
        dca_results = []
        
        for item in DCA_PORTFOLIO:
            ticker = item['ticker']
            name = item['name']
            buy_price = item['buy_price']
            qty = item['quantity']
            
            last_close = None
            
            if ticker == "GC=F":
                # 국내 금 시세 (네이버/KRX) 직접 크롤링
                last_close = engine.get_domestic_gold_price()
                # 만약 크롤링 실패 시 기존 보정 로직 (임시 방편)
                if last_close is None:
                    df_gold = engine.fetch_data("GC=F")
                    if df_gold is not None:
                        raw_gold = float(df_gold['Close'].iloc[-1])
                        last_close = raw_gold * 47.64
            else:
                df_stock = engine.fetch_data(ticker)
                if df_stock is not None and not df_stock.empty:
                    # yfinance 데이터가 MultiIndex일 경우를 대비해 확실하게 스칼라 값 추출
                    close_val = df_stock['Close']
                    if isinstance(close_val, pd.DataFrame):
                        last_close = float(close_val.iloc[-1, 0])
                    else:
                        last_close = float(close_val.iloc[-1])
            
            if last_close is None:
                continue
                
            buy_val = buy_price * qty
            eval_val = last_close * qty
            
            # 비중 계산을 위해 내부 데이터 보관
            item_res = {
                "eval_val": eval_val,
                "buy_val": buy_val,
                "ticker": ticker,
                "name": name,
                "last_close": last_close,
                "buy_price": buy_price,
                "qty": qty
            }
            pl_val = eval_val - buy_val
            pl_pct = (pl_val / buy_val) * 100 if buy_val > 0 else 0
            
            total_buy_val += buy_val
            total_eval_val += eval_val
            
            dca_results.append({
                "종목명": name,
                "티커": ticker,
                "현재 비중": 0.0, # 나중에 채움
                "수익률": pl_pct,
                "평가금액": f"{eval_val:,.0f}",
                "매수금액": f"{buy_val:,.0f}",
                "보유수량": qty,
                "현재가": f"{last_close:,.0f}",
                "매수가": f"{buy_price:,.0f}",
                "eval_val": eval_val # 계산용 (삭제 시 주의)
            })
        
        # evaluation value 합계 (금 제외)
        etf_eval_total = sum([d['eval_val'] for d in dca_results if d['티커'] != "GC=F"])

        # 비중 계산
        for d in dca_results:
            if d['티커'] != "GC=F" and etf_eval_total > 0:
                d["현재 비중"] = (d['eval_val'] / etf_eval_total) * 100
            else:
                d["현재 비중"] = 0.0

        total_pl_val = total_eval_val - total_buy_val
        total_pl_pct = (total_pl_val / total_buy_val) * 100 if total_buy_val > 0 else 0
        
        # ETF 총 평가금액 (비중 계산용, 금 제외)
        etf_eval_total = sum([d['eval_val'] for d in dca_results if d['티커'] != "GC=F"])
        
        for d in dca_results:
            if d['티커'] != "GC=F" and etf_eval_total > 0:
                d["현재 비중"] = (d['eval_val'] / etf_eval_total) * 100
            else:
                d["현재 비중"] = 0.0
        
        # 요약 카드 표시
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("총 평가금액", f"{total_eval_val:,.0f}원")
        col2.metric("총 매입금액", f"{total_buy_val:,.0f}원")
        col3.metric("평가손익", f"{total_pl_val:,.0f}원", f"{total_pl_pct:+.2f}%")
        col4.metric("예수금", f"{DCA_CASH:,.0f}원")

    st.markdown("---")
    
    # 2. 보유 종목 리스트
    st.subheader("📝 보유 종목 상세")
    if dca_results:
        df_dca = pd.DataFrame(dca_results)
        
        def style_pl(val):
            color = 'red' if val > 0 else 'blue' if val < 0 else 'black'
            return f'color: {color}; font-weight: bold'

        st.dataframe(
            df_dca.style.format({
                "수익률": "{:+.2f}%",
                "현재 비중": "{:.1f}%"
            }).map(style_pl, subset=["수익률"]),
            use_container_width=True,
            column_order=["종목명", "현재 비중", "수익률", "평가금액", "매수금액", "보유수량", "현재가", "매수가"]
        )
    else:
        st.info("보유 중인 적립식 종목이 없습니다.")

    # 3. 매수 가이드
    st.markdown("---")
    st.subheader("📢 다음 달 매수 가이드")
    
    # 설정: 투자 예산 (ETF용) 및 목표 비중
    monthly_budget = 500000
    target_plan = [
        {"name": "ACE 미국나스닥100", "ticker": "368590.KS", "weight": 0.30},
        {"name": "TIGER 미국S&P500", "ticker": "360750.KS", "weight": 0.30},
        {"name": "TIGER 인도니프티50", "ticker": "453870.KS", "weight": 0.20},
        {"name": "TIGER 200", "ticker": "102110.KS", "weight": 0.20},
    ]

    guide_data = []
    with st.spinner("매수 계획 계산 중..."):
        # 1. ETF 매수 계획
        for p in target_plan:
            ticker = p['ticker']
            df = engine.fetch_data(ticker, period="5d")
            if df is not None and not df.empty:
                close_val = df['Close']
                if isinstance(close_val, pd.DataFrame): current_price = float(close_val.iloc[-1, 0])
                else: current_price = float(close_val.iloc[-1])
            else:
                current_price = 0
            
            target_amount = monthly_budget * p['weight']
            final_qty = int(target_amount / current_price) if current_price > 0 else 0
            final_buy_amount = final_qty * current_price
                
            guide_data.append({
                "종목명": p['name'],
                "현재가": f"{current_price:,.0f}원",
                "목표비중": f"{p['weight']*100:.0f}%",
                "배정금액": f"{target_amount:,.0f}원",
                "매수 수량": f"{final_qty}주",
                "최종 매수액": f"{final_buy_amount:,.0f}원"
            })
        
        # 2. 금 (고정 1주)
        gold_price = engine.get_domestic_gold_price()
        if gold_price is None: gold_price = 0
        
        guide_data.append({
            "종목명": "금 99.99K (고정 매수)",
            "현재가": f"{gold_price:,.0f}원",
            "목표비중": "-",
            "배정금액": "-",
            "매수 수량": "1주",
            "최종 매수액": f"{gold_price:,.0f}원"
        })

    if guide_data:
        st.markdown(f"""
        <div style="background-color: #f0f4f8; padding: 15px; border-radius: 10px; border-left: 5px solid #2196f3; margin-bottom: 20px;">
        신규 계획: <b>ETF 예산 500,000원</b> (30/30/20/20) + <b>금 1주 고정 매수</b>
        </div>
        """, unsafe_allow_html=True)
        
        st.table(pd.DataFrame(guide_data))
        
        total_planned = sum([float(d['최종 매수액'].replace('원','').replace(',','')) for d in guide_data])
        st.info(f"💡 전체 실행 시 약 **{total_planned:,.0f}원**이 소요됩니다.")

    # 기존 날짜 알림
    dca_status = check_dca_status()
    if dca_status == "BUY":
        st.success("📢 **현재 적립식 매수 기간입니다!** (매월 15일 ~ 20일)", icon="💰")
    else:
        st.warning("⏳ 현재는 정기 매수 기간이 아닙니다. (매월 15~20일 권장)", icon="⏰")

def show_dividends_page():
    st.header("🏦 배당주 관리")
    st.markdown("""
    <div style="background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #eee; margin-bottom: 20px; color: #333;">
    안정적인 현금 흐름을 위한 <b>배당주 및 배당 ETF</b> 관리 화면입니다. 실시간 환율을 반영하여 총 자산을 추적합니다.
    </div>
    """, unsafe_allow_html=True)
    
    # 1. 환율 및 기본 정보
    with st.spinner("배당주 및 환율 정보 분석 중..."):
        ex_data = engine.fetch_data("USDKRW=X", period="5d")
        exchange_rate = ex_data['Close'].iloc[-1] if ex_data is not None else 1450.0
        
        total_eval_krw = 0
        total_buy_krw = 0
        div_results = []
        
        for item in DIVIDEND_PORTFOLIO:
            ticker = item['ticker']
            curr_price_usd = 0.0
            change_1d = 0.0
            
            df = engine.fetch_data(ticker, period="5d")
            
            if df is not None and not df.empty:
                curr_price_usd = float(df['Close'].iloc[-1])
                prev_close_val = float(df['Close'].iloc[-2]) if len(df) >= 2 else curr_price_usd
                change_1d = ((curr_price_usd - prev_close_val) / prev_close_val) * 100
            else:
                curr_price_usd = 0
                change_1d = 0
                
            buy_price_usd = item['buy_price_usd']
            qty = item['quantity']
            
            buy_val_usd = buy_price_usd * qty
            eval_val_usd = curr_price_usd * qty
            pl_usd = eval_val_usd - buy_val_usd
            pl_pct = (pl_usd / buy_val_usd) * 100 if buy_val_usd > 0 else 0
            
            # 배당금 정보 (최근 1회 지급액 * 수량으로 추정)
            div_history = engine.get_dividend_history(ticker, count=1)
            last_div_payout = div_history[0]['Amount'] * qty if div_history else 0
            
            # "실제" (평가금 + 배당금 합산) 지표
            real_eval_usd = eval_val_usd + last_div_payout
            real_pl_usd = real_eval_usd - buy_val_usd
            real_pl_pct = (real_pl_usd / buy_val_usd) * 100 if buy_val_usd > 0 else 0
            
            total_buy_krw += (buy_val_usd * exchange_rate)
            total_eval_krw += (eval_val_usd * exchange_rate)
            
            div_results.append({
                "구분": "해외",
                "종목": item['name'].split()[-1] if ' ' in item['name'] else item['name'], # 짧은 이름
                "티커": ticker,
                "현재가": curr_price_usd,
                "전일대비": change_1d,
                "평균단가": buy_price_usd,
                "보유수량": qty,
                "총투자자금": buy_val_usd,
                "평가금액": eval_val_usd,
                "평가손익": pl_usd,
                "평가수익률": pl_pct,
                "배당금": last_div_payout,
                "실제 평가금액": real_eval_usd,
                "실제 평가손익": real_pl_usd,
                "실제평가수익률": real_pl_pct
            })

        total_pl_krw = total_eval_krw - total_buy_krw
        total_pl_pct = (total_pl_krw / total_buy_krw) * 100 if total_buy_krw > 0 else 0

        # 요약 메트릭
        col1, col2, col3 = st.columns(3)
        col1.metric("총 평가금액", f"{total_eval_krw:,.0f}원")
        col2.metric("총 매입금액", f"{total_buy_krw:,.0f}원")
        col3.metric("평가손익", f"{total_pl_krw:,.0f}원", f"{total_pl_pct:+.2f}%")

    st.markdown("---")
    
    # 2. 상세 리스트
    st.subheader("📝 보유 배당주 리스트")
    if div_results:
        df_div = pd.DataFrame(div_results)
        
        def highlight_pl(val):
            if isinstance(val, (int, float)):
                color = 'red' if val > 0 else 'blue' if val < 0 else 'black'
                return f'color: {color}; font-weight: bold'
            return ''

        st.dataframe(
            df_div.style.format({
                "현재가": "${:,.2f}",
                "전일대비": "{:+.2f}%",
                "평균단가": "${:,.4f}",
                "보유수량": "{:,}",
                "총투자자금": "${:,.2f}",
                "평가금액": "${:,.2f}",
                "평가손익": "${:+.2f}",
                "평가수익률": "{:+.2f}%",
                "배당금": "${:,.2f}",
                "실제 평가금액": "${:,.2f}",
                "실제 평가손익": "${:+.2f}",
                "실제평가수익률": "{:+.2f}%"
            }).map(highlight_pl, subset=["전일대비", "평가손익", "평가수익률", "실제 평가손익", "실제평가수익률"]),
            use_container_width=True,
            column_order=[
                "구분", "종목", "티커", "현재가", "전일대비", "평균단가", "보유수량", 
                "총투자자금", "평가금액", "평가손익", "평가수익률", "배당금", 
                "실제 평가금액", "실제 평가손익", "실제평가수익률"
            ]
        )
    else:
        st.info("배당주 포트폴리오 데이터가 없습니다.")

    st.markdown("---")
    
    # 3. 배당금 지급 내역 및 일정
    st.subheader("📅 최근 배당금 지급 내역 (1주당)")
    
    if DIVIDEND_PORTFOLIO:
        div_history_cols = st.columns(len(DIVIDEND_PORTFOLIO))
        
        for i, item in enumerate(DIVIDEND_PORTFOLIO):
            with div_history_cols[i]:
                ticker = item['ticker']
                st.markdown(f"#### {ticker}")
                divs = engine.get_dividend_history(ticker, count=3)
                if divs:
                    for d in divs:
                        st.write(f"- **{d['Date']}**: ${d['Amount']:.4f}")
                    
                    # 예상 배당금 (최근 배당 기준)
                    last_amount = divs[0]['Amount']
                    total_payout = last_amount * item['quantity']
                    st.info(f"💰 예상 수령: **${total_payout:,.2f}**")
                else:
                    st.write("지급 내역이 없습니다.")

def show_index_value_page():
    st.header("📈 지수가치 (Index Valuation)")
    
    st.markdown("""<div style="background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #eee; margin-bottom: 20px; color: #333;">
글로벌 주요 지수의 현재 위치와 <b>52주 변동 범위</b>를 확인하여 시장의 상대적 고저점을 파악합니다.
</div>""", unsafe_allow_html=True)
    
    with st.spinner("지수 데이터 분석 중..."):
        index_data = []
        for name, ticker in engine.TARGET_INDICES.items():
            df = engine.fetch_data(ticker, period="2y")
            if df is not None and not df.empty:
                current_price = float(df['Close'].iloc[-1])
                prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else current_price
                change_pct = ((current_price - prev_close) / prev_close) * 100
                
                # MDD 및 회복율 계산 (Market Board와 동일한 track_mdd 사용)
                mdd, mdd_info = engine.track_mdd(df)
                
                # 52주 고저 (최근 1년 데이터 기반)
                df_1y = df.tail(252)
                high_52w = float(df_1y['Close'].max())
                low_52w = float(df_1y['Close'].min())
                pos_pct = ((current_price - low_52w) / (high_52w - low_52w)) * 100 if high_52w != low_52w else 0
                
                index_data.append({
                    "지수명": name,
                    "티커": ticker,
                    "현재가": current_price,
                    "전일대비": change_pct,
                    "MDD": mdd * 100 if mdd is not None else 0,
                    "회복율": mdd_info.get('recovery_rate', 0) * 100,
                    "현재 위치(%)": pos_pct,
                    "52주 최저": low_52w,
                    "52주 최고": high_52w
                })

    if index_data:
        df_index = pd.DataFrame(index_data)
        
        # 카드 형태로 표시
        cols = st.columns(3)
        for i, row in df_index.iterrows():
            with cols[i % 3]:
                color = "red" if row['전일대비'] > 0 else "blue"
                sign = "+" if row['전일대비'] > 0 else ""
                
                # 매수 신호 (회복율 80% 이상)
                buy_sig = row['회복율'] >= 80
                sig_html = f'<span style="background-color: #d4edda; color: #155724; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; margin-left: 10px; font-weight: bold;">BUY SIGNAL</span>' if buy_sig else ''

                st.markdown(f"""<div class="market-card">
<div style="display: flex; justify-content: space-between; align-items: center;">
<span style="font-size: 1.1em; font-weight: 600; color: #666;">{row['지수명']}</span>
{sig_html}
</div>
<div style="display: flex; align-items: baseline; margin: 10px 0;">
<span style="font-size: 1.8em; font-weight: 700;">{row['현재가']:,.2f}</span>
<span style="color: {color}; margin-left: 10px; font-weight: 600;">{sign}{row['전일대비']:.2f}%</span>
</div>
<div style="font-size: 0.85em; color: #555; margin-bottom: 5px;">
📉 MDD: <b>{row['MDD']:.2f}%</b> | 🔄 회복율: <b>{row['회복율']:.1f}%</b>
</div>
<div style="background-color: #eee; height: 8px; border-radius: 4px; overflow: hidden; margin: 10px 0;">
<div style="background-color: {'#28a745' if buy_sig else '#2196f3'}; width: {row['회복율']}%; height: 100%;"></div>
</div>
<div style="font-size: 0.8em; color: #888; text-align: right;">52주 범위 내 위치: {row['현재 위치(%)']:.1f}%</div>
</div>""", unsafe_allow_html=True)
        
        st.markdown("---")
        st.subheader("📊 지수 상세 데이터")
        
        def color_recovery_val(val):
            color = 'green' if val >= 80 else 'black'
            return f'color: {color}; font-weight: bold'

        st.dataframe(
            df_index.style.format({
                "현재가": "{:,.2f}",
                "전일대비": "{:+.2f}%",
                "MDD": "{:+.2f}%",
                "회복율": "{:.1f}%",
                "현재 위치(%)": "{:.1f}%",
                "52주 최저": "{:,.2f}",
                "52주 최고": "{:,.2f}"
            }).map(color_recovery_val, subset=["회복율"]),
            use_container_width=True,
            column_order=["지수명", "현재가", "전일대비", "MDD", "회복율", "현재 위치(%)", "52주 최저", "52주 최고"]
        )

# --- Main App Logic ---

def main():
    st.sidebar.title("🚀 Strock Board Navigation")
    
    pages = ["Market Board", "터틀 보유 종목", "터틀 불타기", "터틀 종목 검색", "적립식", "배당주", "지수가치"]
    
    # URL에서 현재 페이지 읽기 (새로고침 대응)
    query_params = st.query_params
    default_page = query_params.get("page", "Market Board")
    
    # 인덱스 찾기 (없으면 0)
    try:
        default_index = pages.index(default_page)
    except ValueError:
        default_index = 0

    menu = st.sidebar.radio(
        "이동할 페이지를 선택하세요",
        pages,
        index=default_index
    )
    
    # 페이지 변경 시 URL 업데이트
    if menu != default_page:
        st.query_params["page"] = menu
    
    st.sidebar.markdown("---")
    
    if menu == "Market Board":
        show_market_board()
    elif menu == "터틀 보유 종목":
        show_turtle_portfolio()
    elif menu == "터틀 불타기":
        show_pyramiding_page()
    elif menu == "터틀 종목 검색":
        show_turtle_search()
    elif menu == "적립식":
        show_dca_page()
    elif menu == "배당주":
        show_dividends_page()
    elif menu == "지수가치":
        show_index_value_page()

def show_pyramiding_page():
    st.header("🔥 터틀 불타기 (Pyramiding)")
    st.markdown("""
    <div style="background-color: #fff9c4; padding: 20px; border-radius: 12px; border-left: 5px solid #fbc02d; margin-bottom: 20px; color: #333;">
    현재가가 <b>매수가 + 2N</b> 이상으로 상승하여 <b>불타기(추가 매수)</b>가 가능한 종목들을 보여줍니다. <br>
    로드맵을 통해 향후 추가 매수 지점과 리스크를 미리 확인하세요.
    </div>
    """, unsafe_allow_html=True)

    all_portfolio = DOMESTIC_PORTFOLIO + OVERSEAS_PORTFOLIO
    eligible_stocks = []

    with st.spinner("불타기 가능 종목 분석 중..."):
        for item in all_portfolio:
            ticker = item['ticker']
            df = engine.fetch_data(ticker)
            if df is None or df.empty: continue
            
            last_close = df['Close'].iloc[-1]
            n_val = engine.calculate_atr(df)
            if n_val is None: continue # ATR 계산 불가시 제외
            
            buy_price = item['buy_price']
            
            target_2n = buy_price + (2 * n_val)
            if last_close >= target_2n:
                item['n_val'] = n_val
                item['last_close'] = last_close
                eligible_stocks.append(item)

    if not eligible_stocks:
        st.info("현재 불타기 조건(+2N 돌파)을 충족하는 종목이 없습니다.")
        return

    for item in eligible_stocks:
        with st.expander(f"✨ {item.get('name', item['ticker'])} (+2N 돌파 완료)", expanded=True):
            render_pyramiding_roadmap(item)

def render_pyramiding_roadmap(item):
    ticker = item['ticker']
    buy_price = item['buy_price']
    n_val = item['n_val']
    qty_unit = item['quantity'] # 기본 단위 (1차 매수 수량 기준)
    
    roadmap = []
    total_qty = 0
    total_cost = 0
    
    for i in range(1, 6): # 1차 ~ 5차
        # 불타기 간격은 2N (사용자 요청 기준)
        entry_price = buy_price + (i-1) * (2 * n_val)
        
        # 추가 수량 (사용자 스크린샷 참고: 1차=6, 2차~5차=3 등으로 절반씩 하는 경향이 있으나 여기선 동일 수량 가상 시뮬레이션)
        # 만약 실제 추가 매수가 이루어진다면 이 로직을 고도화할 수 있습니다.
        add_qty = qty_unit if i == 1 else round(qty_unit / 2) if qty_unit > 1 else 1
        
        total_qty += add_qty
        total_cost += entry_price * add_qty
        avg_price = total_cost / total_qty
        
        # 손절가는 해당 회차 매수가 - 2N
        stop_loss = entry_price - (2 * n_val)
        # 손절 시 손실 = (평균단가 - 손절가) * 총 수량
        loss_at_stop = (avg_price - stop_loss) * total_qty
        
        roadmap.append({
            "매수 횟수": f"{i}차",
            "매수 가격": entry_price,
            "매수 수량": add_qty,
            "총 매수 금액": total_cost,
            "총 매수 수량": total_qty,
            "평균 단가": avg_price,
            "손절 가격": stop_loss,
            "손절 시 손실": -abs(loss_at_stop) # 손실이므로 음수로 표시
        })
    
    df_roadmap = pd.DataFrame(roadmap)
    
    # 현재 단계 표시 (어디까지 왔나)
    current_price = item['last_close']
    def highlight_row(row):
        if current_price >= row['매수 가격']:
            return ['background-color: #fff9c4'] * len(row)
        return [''] * len(row)

    st.dataframe(
        df_roadmap.style.format({
            "매수 가격": "{:,.2f}", "총 매수 금액": "{:,.2f}", 
            "평균 단가": "{:,.2f}", "손절 가격": "{:,.2f}", "손절 시 손실": "{:,.2f}"
        }).apply(highlight_row, axis=1),
        use_container_width=True
    )
    st.caption(f"📍 현재가: **{current_price:,.2f}** | 1N(ATR20): **{n_val:,.2f}**")

    st.markdown("---")
    st.caption(f"마지막 업데이트: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    main()
