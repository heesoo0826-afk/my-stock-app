import streamlit as st
import pandas as pd
import datetime
import plotly.graph_objects as go
import engine

# --- Configuration ---
st.set_page_config(page_title="고도 트레이딩 대시보드", layout="wide")

# Mock Portfolio for Turtle Strategy (Ticker, Avg Buy Price)
# 실제 앱에서는 DB나 파일에서 불러와야 함
MY_PORTFOLIO = [
    {"ticker": "AAPL", "buy_price": 185.0},
    {"ticker": "TSLA", "buy_price": 200.0},
    {"ticker": "NVDA", "buy_price": 450.0},
    {"ticker": "BTC-USD", "buy_price": 40000.0},
]

# --- Helper Functions ---
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
    # 15일 ~ 20일 사이인지 확인
    if 15 <= today.day <= 20:
        return "BUY"
    return "WAIT"

# --- Main Dashboard ---
st.title("📈 고도 트레이딩 대시보드")

# 사이드바 설정
st.sidebar.header("설정")
days_to_show = st.sidebar.slider("차트 조회 기간 (일)", 30, 365, 100)

# 1. 적립식 매수 알림 (DCA)
dca_status = check_dca_status()
if dca_status == "BUY":
    st.success("📢 **오늘은 적립식 매수 기간입니다! (대상: S&P500, 나스닥100)**", icon="💰")
else:
    st.info("💡 **체계적인 자산 배분을 위해 다음 매수일을 기다리세요.** (매월 15일 ~ 20일)", icon="⏳")

# 2. 시장 국면 현황 (Market Status)
st.header("🌍 시장 국면 (6단계)")

if st.button("시장 데이터 새로고침"):
    st.cache_data.clear()
    
# 데이터 로드
with st.spinner("시장 데이터 분석 중..."):
    results = engine.run_analysis()

# 카드 형태로 표시
cols = st.columns(3) # 그리드 레이아웃
keys = list(results.keys())

for i, key in enumerate(keys):
    data = results[key]
    phase = data['phase']
    mdd = data['mdd']
    recovery = data['mdd_info'].get('recovery_rate', 0)
    df = data.get('data') # Engine에서 받아온 DataFrame
    
    col = cols[i % 3]
    color, icon, desc = get_phase_info(phase)
    
    # 한국어 종목명 매핑
    korean_name = key
    if key == "KOSPI": korean_name = "코스피 (KOSPI)"
    elif key == "KOSDAQ": korean_name = "코스닥 (KOSDAQ)"
    elif key == "US_SP500": korean_name = "미국 S&P 500"
    elif key == "US_NASDAQ": korean_name = "미국 나스닥"
    elif key == "GOLD": korean_name = "금 (Gold)"
    elif key == "BITCOIN": korean_name = "비트코인"

    with col:
        # 1. 정보 카드 & MDD 알림
        # 현재 하락률 및 회복 필요 수익률
        current_dd = 0
        current_recovery_needed = 0
        
        if df is not None and not df.empty:
            current_dd = df['Drawdown'].iloc[-1]
            current_recovery_needed = df['Recovery_Needed'].iloc[-1]
            
        # 알림 메시지 설정
        alert_messages = []
        is_safe_mode = False
        
        # 1. 매수 적기 신호 (회복률 80% 이상 AND MDD -10% 이하)
        # 상승장(MDD 거의 없음)에서는 매수 신호 뜨지 않도록 MDD 조건 추가
        if recovery >= 0.8 and current_dd <= -0.10:
            alert_messages.append("✨ <span style='color:green; font-weight:bold;'>현재 매수 적기 (회복률 80% 돌파)</span>")
            
        # 2. 하락장 경고 (MDD 기준)
        if current_dd <= -0.35:
            alert_messages.append("🚨 <span style='color:red; font-weight:bold;'>강력 매수 기회 (MDD -35% 이하)</span>")
        elif current_dd <= -0.20:
            alert_messages.append("🟠 <span style='color:orange; font-weight:bold;'>기회 구간 (MDD -20% 이하)</span>")
        elif current_dd <= -0.15:
            alert_messages.append("🟡 <span style='color:gold; font-weight:bold;'>주의 구간 (MDD -15% 이하)</span>")
            
        # 3. 안정 구간 확인 (MDD -5% 이내)
        if current_dd > -0.05:
            is_safe_mode = True
            
        alerts_html = "".join([f"<p style='margin: 5px 0;'>{msg}</p>" for msg in alert_messages])
        
        # 하단 지표 텍스트 구성
        if is_safe_mode:
            stats_html = """<div style="margin-top: 10px; color: green; font-weight: bold; text-align: center;">🚀 신고가 경신 / 고점 부근 (안정)</div>"""
        else:
            stats_html = f"""<div style="display: flex; justify-content: space-between; margin-top: 10px;">
                <span>📉 현재 MDD: <span style="font-weight:bold; color:red;">{current_dd:.2%}</span></span>
                <span>💪 회복률: <span style="font-weight:bold;">{recovery:.2%}</span></span>
            </div>"""
            
        st.markdown(f"""
<div style="border: 2px solid {color}; border-radius: 10px; padding: 15px; margin-bottom: 10px; background-color: rgba(255,255,255,0.05);">
<h3 style="color: {color}; margin:0;">{icon} {korean_name}</h3>
<p style="font-size: 1.1em; font-weight: bold; margin: 5px 0;">{phase}국면: {desc}</p>
{alerts_html}
<hr style="margin: 10px 0; opacity: 0.3;">
{stats_html}
</div>
""", unsafe_allow_html=True)
        
        # 2. 차트 (Plotly) - 일봉 차트만 표시 (MDD 차트 제거)
        if df is not None and not df.empty:
            # 설정한 기간만큼 데이터 슬라이싱
            chart_data = df.tail(days_to_show)
            
            fig = go.Figure()
            
            # 캔들 차트
            fig.add_trace(go.Candlestick(
                x=chart_data.index,
                open=chart_data['Open'],
                high=chart_data['High'],
                low=chart_data['Low'],
                close=chart_data['Close'],
                name='Price'
            ))
            
            # 이동평균선
            if 'MA5' in chart_data.columns:
                fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['MA5'], line=dict(color='green', width=1), name='MA5'))
            if 'MA20' in chart_data.columns:
                fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['MA20'], line=dict(color='#ff4b4b', width=1), name='MA20'))
            if 'MA40' in chart_data.columns:
                fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['MA40'], line=dict(color='orange', width=1), name='MA40'))
            
            # 차트 레이아웃 설정
            fig.update_layout(
                height=350,
                margin=dict(l=0, r=0, t=20, b=0),
                xaxis_rangeslider_visible=False,
                showlegend=False,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(size=11)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.warning("차트 데이터 없음")

# 3. 터틀 전략 (보유 포트폴리오)
st.header("🐢 터틀 전략 (보유 포트폴리오)")
st.markdown("현재가가 **매수가 + 2N (불타기/이익실현)** 혹은 **매수가 - 2N (손절)** 기준에 도달했는지 확인합니다.")

portfolio_data = []

with st.spinner("포트폴리오 분석 중..."):
    for item in MY_PORTFOLIO:
        ticker = item['ticker']
        buy_price = item['buy_price']
        
        # 데이터 가져오기
        df = engine.fetch_data(ticker)
        if df is None:
            continue
            
        current_price = df['Close'].iloc[-1]
        n_val = engine.calculate_atr(df)
        
        # 로직 계산
        diff = current_price - buy_price
        if n_val > 0:
            n_multiple = diff / n_val
        else:
            n_multiple = 0
        
        status = "보유 (HOLD)"
        
        if diff >= 2 * n_val:
            status = "🚀 이익실현 / 불타기 (+2N 이상)"
        elif diff <= -2 * n_val:
            status = "🛑 손절 (-2N 이하)"
            
        portfolio_data.append({
            "종목코드": ticker,
            "매수가": buy_price,
            "현재가": f"{current_price:.2f}",
            "N (변동성)": f"{n_val:.2f}",
            "수익폭 (N배)": f"{n_multiple:.2f}N",
            "상태": status
        })

# 포트폴리오 테이블 표시
if portfolio_data:
    df_port = pd.DataFrame(portfolio_data)
    
    # 상태 컬럼 스타일링
    def style_status(val):
        color = 'gray'
        if '이익실현' in val: color = 'green'
        if '손절' in val: color = 'red'
        return f'color: {color}; font-weight: bold;'
    
    st.dataframe(df_port.style.map(style_status, subset=['상태']), use_container_width=True)
else:
    st.write("포트폴리오 데이터가 없습니다.")

st.markdown("---")
st.caption(f"마지막 업데이트: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
