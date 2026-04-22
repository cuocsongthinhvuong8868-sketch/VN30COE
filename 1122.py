import streamlit as st
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime, timedelta
import altair as alt # Thêm Altair cho biểu đồ

# Cấu hình API VNSTOCK (Giữ nguyên)
os.environ['VNSTOCK_API_KEY'] = 'vnstock_17b56a86b930db526e25e8de447a0bfd'
from vnstock import Quote

# Cấu hình tham số mô hình (Giữ nguyên)
PR_RATIO = 0.30
GROWTH_LOW = 0.03
GROWTH_BASE = 0.05
GROWTH_HIGH = 0.07
CSV_PATH = 'vn30_eps.csv' # Tự động lấy file cùng folder

# Dữ liệu EPS VN30 thực tế để tự động tạo file
EPS_DATA_CSV = """Mã,EPS_TTM
ACB,3041.8033
BCM,3370.4973
BID,4266.5458
BVH,3979.7778
CTG,5320.7133
FPT,5691.4478
GAS,4764.7209
GVR,1382.4376
HDB,3874.8614
HPG,2012.9182
MBB,3585.4272
MSN,2842.7494
MWG,4777.0648
PLX,2121.9807
POW,868.9308
SAB,3448.9861
SHB,2713.3680
SSB,1936.5691
SSI,1815.3559
STB,3150.3615
TCB,3571.4619
TPB,2720.0344
VCB,4210.0913
VHM,10008.0408
VIB,2221.3844
VIC,1473.3541
VJC,3587.7169
VNM,4502.5848
VPB,3023.7158
VRE,2836.7164"""

st.set_page_config(page_title="VN30 Valuation Dashboard", page_icon="📈", layout="wide")

@st.cache_data
def load_eps_data():
    """Đọc dữ liệu EPS từ file CSV nội bộ, tự động tạo nếu thiếu"""
    if not os.path.exists(CSV_PATH):
        # Tự động tạo file CSV mẫu từ dữ liệu cung cấp
        with open(CSV_PATH, 'w', encoding='utf-8') as f:
            f.write(EPS_DATA_CSV)
        st.warning(f"⚠️ Không tìm thấy file `{CSV_PATH}`. Một file mẫu đã được tạo tự động với dữ liệu EPS cung cấp.")
    return pd.read_csv(CSV_PATH)

def fetch_market_data(eps_dict):
    """Lấy giá từ KBS và tính định giá cho từng mã (Giữ nguyên logic sửa lỗi P/E)"""
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    data_valuation = []
    
    progress_text = "Đang tải dữ liệu giá từ API..."
    my_bar = st.progress(0, text=progress_text)
    
    total_symbols = len(eps_dict)
    for i, (symbol, eps) in enumerate(eps_dict.items()):
        if pd.isna(eps) or eps == 0:
            continue
            
        try:
            # Lấy giá từ nguồn KBS
            quote = Quote(symbol=symbol, source='KBS')
            df_price = quote.history(start=start_date, end=end_date, interval='1D')
            
            if df_price is not None and not df_price.empty:
                current_price = df_price['close'].iloc[-1]
                
                # Tính P/E
                pe_current = current_price / eps
                # Logic sửa lỗi P/E thấp (<2) của bạn
                if 0 < pe_current < 2: 
                    current_price = current_price * 1000
                    pe_current = current_price / eps
                    
                data_valuation.append({
                    'Mã': symbol, 
                    'Giá hiện tại': current_price,
                    'EPS': eps,
                    'P/E': float(pe_current)
                })
            time.sleep(0.5) # Nghỉ nhẹ để KBS không block IP
        except Exception as e:
            st.warning(f"Lỗi khi lấy dữ liệu {symbol}: {e}")
            
        my_bar.progress((i + 1) / total_symbols, text=f"Đang xử lý {symbol} ({i+1}/{total_symbols})")
        
    my_bar.empty()
    return pd.DataFrame(data_valuation)

# GIAO DIỆN CHÍNH
st.title("🏦 Dashboard Định Giá VN30 (EPS Yield Models)")
st.markdown("Công cụ theo dõi lợi suất kỳ vọng VN30 dựa trên P/E Harmonic Mean, Payout Ratio (30%) và các kịch bản tăng trưởng dài hạn.")

# 1. Đọc dữ liệu EPS
df_eps = load_eps_data()
eps_dict = dict(zip(df_eps['Mã'], df_eps['EPS_TTM']))

# 2. Xử lý dữ liệu khi bấm nút cập nhật
if st.button("🔄 Cập nhật dữ liệu thị trường (Real-time)", type="primary"):
    with st.spinner("Đang tổng hợp số liệu..."):
        df_val = fetch_market_data(eps_dict)
        
        if not df_val.empty:
            df_valid = df_val.dropna(subset=['P/E'])
            
            # Tính Harmonic Mean của P/E toàn rổ VN30
            # Chuẩn bị dữ liệu để tính Harmonic Mean (1 / mean of 1/PE)
            df_valid['Base_Yield (1/PE)'] = 1 / df_valid['P/E']
            avg_base_yield = df_valid['Base_Yield (1/PE)'].mean()
            index_pe = 1 / avg_base_yield if avg_base_yield > 0 else np.nan
            
            # Tính toán 3 kịch bản EPS Yield theo công thức yêu cầu
            # Expected Return = (Harmonic Mean 1/PE * PR) + g
            yield_low = (avg_base_yield * PR_RATIO) + GROWTH_LOW
            yield_base = (avg_base_yield * PR_RATIO) + GROWTH_BASE
            yield_high = (avg_base_yield * PR_RATIO) + GROWTH_HIGH
            
            # Lưu vào session_state
            st.session_state['results'] = {
                'index_pe': index_pe,
                'yield_low': yield_low,
                'yield_base': yield_base,
                'yield_high': yield_high,
                'df_detail': df_valid, # Vẫn lưu dataframe chi tiết để vẽ biểu đồ
                'time': datetime.now().strftime('%H:%M:%S %d/%m/%Y')
            }
        else:
            st.error("Không lấy được dữ liệu giá từ thị trường.")

st.divider()

# 3. Hiển thị kết quả
if 'results' in st.session_state:
    res = st.session_state['results']
    
    st.markdown(f"**⏳ Cập nhật lần cuối:** {res['time']}")
    
    # Hiển thị các Metric chính (Giữ nguyên)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("P/E Rổ VN30 (Harmonic)", f"{res['index_pe']:.2f}")
    col2.metric("Kịch bản Low (Growth 3%)", f"{res['yield_low'] * 100:.2f}%")
    col3.metric("Kịch bản Base (Growth 5%)", f"{res['yield_base'] * 100:.2f}%")
    col4.metric("Kịch bản High (Growth 7%)", f"{res['yield_high'] * 100:.2f}%")
    
    st.divider()
    
    # --- THAY THẾ BẢNG BẰNG BIỂU ĐỒ TẠI ĐÂY ---
    # Hiển thị biểu đồ chi tiết định giá P/E
    st.subheader("Chi tiết Định giá P/E các mã VN30")
    st.markdown("*Sắp xếp: Thấp đến Cao*")
    
    # Chuẩn bị dữ liệu cho biểu đồ: Sắp xếp theo P/E tăng dần
    chart_data = res['df_detail'].sort_values(by='P/E')
    
    # Tạo biểu đồ Altair
    # X: Mã cổ phiếu, Y: Hệ số P/E, Màu sắc: Gradient từ xanh đến cam đậm cho giá trị P/E lớn
    chart = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('Mã', sort=None, title='Mã cổ phiếu'), # Altair sẽ sử dụng thứ tự của dataframe đã sắp xếp
        y=alt.Y('P/E', title='Hệ số P/E'),
        color=alt.Color('P/E', scale=alt.Scale(scheme='orangered'), legend=None), # Gradient màu
        tooltip=['Mã', 'P/E', 'EPS', 'Giá hiện tại'] # Chú thích công cụ khi di chuột
    ).properties(
        width='container',
        height=400
    ).interactive() # Cho phép thu phóng, di chuyển
    
    st.altair_chart(chart, use_container_width=True)
    
else:
    st.info("👆 Bấm vào nút Cập nhật ở trên để bắt đầu tính toán mô hình.")
