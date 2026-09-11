# app.py
# SmartRouteAI - Demo phần mềm minh họa cho đề tài NCKH
# "Ứng dụng AI để tối ưu hóa tuyến đường trong vận tải quốc nội"
#
# Lưu ý quan trọng: toàn bộ số liệu trong app này được TÍNH TRỰC TIẾP từ
# thuật toán (Haversine + Nearest-Neighbor có ràng buộc tải trọng), không
# có bước ép kết quả khớp với bất kỳ con số định trước nào. Vì vậy đây là
# công cụ minh họa PHƯƠNG PHÁP, không phải bằng chứng số liệu thay thế cho
# một nghiên cứu thực nghiệm thật.

import time
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import folium
from streamlit_folium import st_folium

from data import DEPOT, generate_orders, generate_fleet, save_sample_csv, load_orders_from_upload
from optimizer import traditional_routes, ai_routes, evaluate_solution
from utils import osrm_route_coords

_AI_COLORS = ["green", "blue", "purple", "darkgreen", "cadetblue", "black",
              "darkblue", "darkpurple", "pink", "gray", "beige", "lightgreen"]
_TT_COLORS = ["red", "orange", "darkred", "lightred"]


@st.cache_data(show_spinner=False, ttl=3600)
def _cached_osrm(coords_tuple):
    return osrm_route_coords(list(coords_tuple))

st.set_page_config(page_title="SmartRouteAI - Demo NCKH", layout="wide")

# ---------------------------------------------------------------------------
# Giao diện: theme gọn, tối giản
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&display=swap');

:root {
  --accent: #6D74E6;        /* 1 tông duy nhất cho toàn bộ giao diện */
  --accent-dark: #5459C9;
  --accent-tint: #F1F1FC;   /* nền nhạt dùng chung cho mọi khối */
  --accent-tint-2: #E9E9FB;
  --ink: #33314A;
  --ink-soft: #6E6B85;
  --line: #E7E5F2;
  --good: #16A34A;
  --good-tint: #E7F6EC;
  --bad: #DC2626;
  --bad-tint: #FCE9E9;
}

html, body, [class*="css"] { font-family: 'Be Vietnam Pro', sans-serif; color: var(--ink); }

[data-testid="stAppViewContainer"] { background: #FDFDFE; }
[data-testid="stHeader"] { background: transparent; }

.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1120px; }

#MainMenu, footer, header [data-testid="stToolbar"] { visibility: hidden; }

/* Tabs điều hướng — gọn, 1 tông duy nhất, không icon rực rỡ */
div[data-baseweb="tab-list"] {
    gap: 0.3rem; border-bottom: 1px solid var(--line); margin-bottom: 1.8rem; padding-bottom: 0;
}
button[data-baseweb="tab"] {
    font-weight: 600; font-size: 0.93rem; padding: 0.6rem 0.2rem; margin-right: 1.6rem;
    color: var(--ink-soft) !important; background: transparent !important;
}
button[data-baseweb="tab"][aria-selected="true"] { color: var(--accent) !important; }
button[data-baseweb="tab"] p { color: inherit !important; }
div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {
    background-color: var(--accent) !important; height: 2px !important;
}

/* Thẻ số liệu (metric) — nền trắng, viền mảnh, 1 tông */
div[data-testid="stMetric"] {
    background: #FFFFFF; border: 1px solid var(--line); border-radius: 14px;
    padding: 1rem 1.1rem; box-shadow: none;
}
div[data-testid="stMetricLabel"] { font-size: 0.8rem; color: var(--ink-soft); }
div[data-testid="stMetricValue"] { font-size: 1.3rem; font-weight: 700; color: var(--ink); }

/* Nút bấm — 1 tông duy nhất */
.stButton>button {
    border-radius: 10px; font-weight: 600; padding: 0.5rem 1.1rem; border: 1px solid var(--line);
    background: #FFFFFF; color: var(--ink); transition: all 0.15s ease; box-shadow: none;
}
.stButton>button:hover { border-color: var(--accent); color: var(--accent); }
.stButton>button:focus:not(:active) { border-color: var(--accent) !important; color: var(--accent) !important; }
.stButton>button[kind="primary"] {
    background: var(--accent) !important; color: #FFFFFF !important; border: none !important; box-shadow: none;
}
.stButton>button[kind="primary"]:hover { background: var(--accent-dark) !important; }

/* Card cho khối input / expander */
div[data-testid="stExpander"] {
    border: 1px solid var(--line); border-radius: 12px; box-shadow: none; background: #FFFFFF;
}
div[data-testid="stFileUploader"], div[data-testid="stDataFrame"] {
    border-radius: 12px; overflow: hidden; border: 1px solid var(--line);
}
div[data-testid="stFileUploader"] { background: #FFFFFF; padding: 0.4rem; }
div[data-testid="stFileUploader"] button { background: #FFFFFF; border-color: var(--line); }

/* Ép toàn bộ widget tương tác về đúng 1 tông (ghi đè màu đỏ mặc định của Streamlit) */
div[data-baseweb="slider"] div[role="slider"] { background-color: var(--accent) !important; border-color: var(--accent) !important; }
div[data-baseweb="slider"] > div > div:nth-child(2) { background: var(--accent) !important; }
div[data-testid="stSliderTickBarMin"], div[data-testid="stSliderTickBarMax"] { color: var(--ink-soft); }
input:focus, textarea:focus, select:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 1px var(--accent) !important; }
div[data-baseweb="checkbox"] span[aria-checked="true"] { background-color: var(--accent) !important; border-color: var(--accent) !important; }
div[data-baseweb="radio"] div[aria-checked="true"] > div:first-child { border-color: var(--accent) !important; }
div[data-baseweb="radio"] div[aria-checked="true"] > div:first-child > div { background-color: var(--accent) !important; }
span[data-baseweb="tag"] { background-color: var(--accent-tint-2) !important; color: var(--accent-dark) !important; }
div[data-baseweb="select"] > div:focus-within { border-color: var(--accent) !important; box-shadow: 0 0 0 1px var(--accent) !important; }

/* Sidebar 1 tông */
section[data-testid="stSidebar"] { background: var(--accent-tint); border-right: 1px solid var(--line); }

div[data-testid="stAlert"] { border-radius: 12px; }

h1, h2, h3 { font-weight: 700; color: var(--ink); }
p, span, label { color: var(--ink); }
.stCaption, [data-testid="stCaptionContainer"] { color: var(--ink-soft) !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Khởi tạo session state
# ---------------------------------------------------------------------------
for key, default in [
    ("orders", None), ("fleet", None), ("fuel_price", 21000),
    ("w_cost", 1.0), ("w_time", 1.0), ("w_co2", 1.0),
    ("sol_truyen_thong", None), ("sol_ai", None), ("ai_time_s", None), ("max_trips", 4),
]:
    if key not in st.session_state:
        st.session_state[key] = default

components.html("""
<div style="font-family:'Be Vietnam Pro', sans-serif; margin: 0 0 0.5rem 0;">
  <style>
    .hero {
      background: #F1F1FC;
      border: 1px solid #E7E5F2;
      border-radius: 16px;
      padding: 1.5rem 1.8rem;
    }
    .hero h1 {
      margin: 0 0 0.4rem 0;
      font-size: 1.4rem;
      font-weight: 700;
      color: #33314A;
      letter-spacing: -0.01em;
    }
    .hero p {
      margin: 0;
      color: #6E6B85;
      font-size: 0.92rem;
      max-width: 640px;
      line-height: 1.55;
    }
  </style>
  <div class="hero">
    <h1>SmartRouteAI</h1>
    <p>Demo tối ưu hóa tuyến đường vận tải quốc nội — so sánh phương pháp Nearest-Neighbor
    có ràng buộc tải trọng với cách điều vận thủ công truyền thống.</p>
  </div>
</div>
""", height=115)

tab1, tab2, tab3 = st.tabs([
    "Nhập dữ liệu",
    "Tối ưu tuyến",
    "Báo cáo KPI",
])

# ===========================================================================
# TAB 1: NHẬP DỮ LIỆU
# ===========================================================================
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Đơn hàng")
        if st.button("Tải dữ liệu mẫu (100 đơn hàng)"):
            st.session_state.orders = generate_orders(n=100, seed=42)
            st.success(f"Đã nạp {len(st.session_state.orders)} đơn hàng mẫu (TP.HCM - Bình Dương - Đồng Nai).")

        uploaded = st.file_uploader("Hoặc tải file Excel/CSV riêng (cùng cấu trúc cột)", type=["csv", "xlsx"])
        if uploaded is not None:
            try:
                st.session_state.orders = load_orders_from_upload(uploaded)
                st.success(f"Đã nạp {len(st.session_state.orders)} đơn hàng từ file tải lên.")
            except Exception as e:
                st.error(f"Lỗi đọc file: {e}")

        if st.session_state.orders is not None:
            st.dataframe(st.session_state.orders, height=260, use_container_width=True)

    with col2:
        st.subheader("Đội xe")
        n_veh = st.slider("Số lượng xe", 4, 12, 9)
        if st.button("Sinh đội xe mẫu"):
            fleet = generate_fleet(seed=7, min_veh=n_veh, max_veh=n_veh)
            st.session_state.fleet = fleet
            st.success(f"Đã sinh đội xe gồm {len(fleet)} xe.")
        if st.session_state.fleet is not None:
            st.dataframe(st.session_state.fleet, height=260, use_container_width=True)

        st.subheader("Cấu hình chung")
        st.session_state.fuel_price = st.number_input("Giá dầu diesel (VNĐ/lít)", value=21000, step=500)
        st.session_state.max_trips = st.slider("Số chuyến tối đa mỗi xe/ngày", 1, 6, 4,
                                                help="Mỗi xe có thể quay về kho lấy hàng và chạy thêm chuyến trong ngày.")

        st.markdown("**Trọng số ưu tiên khi ghép đơn (ảnh hưởng đến AI Engine)**")
        st.session_state.w_cost = st.slider("Ưu tiên Chi phí", 0.0, 2.0, 1.0, 0.1)
        st.session_state.w_time = st.slider("Ưu tiên Thời gian / khung giờ", 0.0, 2.0, 1.0, 0.1)
        st.session_state.w_co2 = st.slider("Ưu tiên giảm Phát thải CO₂", 0.0, 2.0, 1.0, 0.1)

    st.info("Sau khi có dữ liệu đơn hàng và đội xe, chuyển sang tab **Tối ưu tuyến** để chạy so sánh.")

# ===========================================================================
# TAB 2: TỐI ƯU TUYẾN
# ===========================================================================
with tab2:
    if st.session_state.orders is None or st.session_state.fleet is None:
        st.warning("Vui lòng nạp dữ liệu đơn hàng và đội xe ở tab **Nhập dữ liệu** trước.")
    else:
        if st.button("Bắt đầu tối ưu hóa", type="primary"):
            # Phương pháp truyền thống: ghi nhận thời gian cố định 180 phút (giả lập điều vận thủ công)
            routes_tt, unassigned_tt = traditional_routes(st.session_state.orders, st.session_state.fleet,
                                                           max_trips=st.session_state.max_trips)
            st.session_state.sol_truyen_thong = evaluate_solution(routes_tt, unassigned_tt, DEPOT, st.session_state.fuel_price)

            # AI Engine: đo thời gian chạy thật
            t0 = time.perf_counter()
            weights = (st.session_state.w_cost, st.session_state.w_time, st.session_state.w_co2)
            routes_ai, unassigned_ai = ai_routes(st.session_state.orders, st.session_state.fleet, DEPOT, weights,
                                                  max_trips=st.session_state.max_trips)
            st.session_state.sol_ai = evaluate_solution(routes_ai, unassigned_ai, DEPOT, st.session_state.fuel_price)
            st.session_state.ai_time_s = time.perf_counter() - t0

            st.success("Đã tối ưu xong. Xem bản đồ và lịch trình bên dưới, hoặc sang tab **Báo cáo KPI** để xem chi tiết.")

        if st.session_state.sol_ai is not None:
            colA, colB = st.columns([1, 1])
            with colA:
                layers = st.multiselect("Hiển thị trên bản đồ", ["Truyền thống", "AI"], default=["Truyền thống", "AI"])
            with colB:
                use_osrm = st.checkbox("Vẽ theo đường thực tế (OSRM)", value=False,
                                        help="Gọi OSRM demo server để bám theo mạng lưới đường bộ thay vì nối thẳng "
                                             "giữa các điểm. Chỉ ảnh hưởng hình vẽ, không đổi số liệu KPI (KPI vẫn "
                                             "tính bằng Haversine). Cần có internet; nếu gọi API lỗi sẽ tự động vẽ "
                                             "đường thẳng.")

            m = folium.Map(location=[DEPOT["lat"], DEPOT["lon"]], zoom_start=10)
            folium.Marker([DEPOT["lat"], DEPOT["lon"]], popup="Kho trung tâm",
                          icon=folium.Icon(color="cadetblue", icon="warehouse", prefix="fa")).add_to(m)

            osrm_ok, osrm_fail, last_err = 0, 0, None

            def draw_layer(sol, label, color_list, dash):
                global osrm_ok, osrm_fail, last_err
                fg = folium.FeatureGroup(name=label, show=True)
                for i, d in enumerate(sol["chi_tiet"]):
                    coords = d["coords"]
                    if use_osrm:
                        coords, ok, err = _cached_osrm(tuple(coords))
                        if ok:
                            osrm_ok += 1
                        else:
                            osrm_fail += 1
                            last_err = err
                    c = color_list[i % len(color_list)]
                    folium.PolyLine(
                        coords, color=c, weight=3, dash_array="8" if dash else None,
                        tooltip=f"[{label}] {d['xe']['ma_xe']} ({d['xe']['loai_xe']}) - {d['so_don']} đơn, "
                                f"{d['quang_duong_km']:.1f} km",
                    ).add_to(fg)
                fg.add_to(m)

            if "Truyền thống" in layers:
                draw_layer(st.session_state.sol_truyen_thong, "Truyền thống", _TT_COLORS, dash=True)
            if "AI" in layers:
                draw_layer(st.session_state.sol_ai, "AI", _AI_COLORS, dash=False)

            folium.LayerControl(collapsed=False).add_to(m)
            # returned_objects giới hạn: chỉ rerun khi click vào tuyến/marker,
            # KHÔNG rerun khi chỉ zoom/kéo bản đồ -> tránh hiện lại spinner mỗi lần thao tác bản đồ
            st_folium(m, width=None, height=560, key=f"map_{layers}_{use_osrm}",
                      returned_objects=["last_object_clicked"])

            if use_osrm:
                if osrm_fail == 0 and osrm_ok > 0:
                    st.success(f"Đã vẽ theo đường thực tế cho {osrm_ok}/{osrm_ok+osrm_fail} tuyến.")
                elif osrm_ok > 0:
                    st.warning(f"Chỉ {osrm_ok}/{osrm_ok+osrm_fail} tuyến vẽ được theo đường thực tế, "
                               f"{osrm_fail} tuyến rơi về đường thẳng do lỗi gọi OSRM (VD: {last_err}). "
                               f"Thường do OSRM demo server quá tải/giới hạn — thử tick lại hoặc thử lại sau.")
                elif osrm_fail > 0:
                    st.error(f"Không gọi được OSRM cho bất kỳ tuyến nào (lỗi: {last_err}). "
                             f"Kiểm tra: đã push `requests` trong requirements.txt và reboot app trên Streamlit Cloud chưa? "
                             f"Server có chặn kết nối ra ngoài tới router.project-osrm.org không?")

            st.caption("Nét đứt = tuyến truyền thống, nét liền = tuyến AI. Tick/bỏ tick ở góc bản đồ để bật/tắt từng lớp.")

            st.subheader("Lịch trình chi tiết từng xe")
            tab_tt, tab_ai = st.tabs(["Truyền thống", "AI"])
            for tab, sol in [(tab_tt, st.session_state.sol_truyen_thong), (tab_ai, st.session_state.sol_ai)]:
                with tab:
                    for d in sol["chi_tiet"]:
                        with st.expander(f"{d['xe']['ma_xe']} — {d['xe']['loai_xe']} — {d['so_don']} đơn, "
                                          f"{d['tai']:.2f}/{d['xe']['tai_trong_tan']} tấn"):
                            st.dataframe(pd.DataFrame(d["stops"]), use_container_width=True)
        else:
            st.info("Bấm nút phía trên để chạy tối ưu.")

# ===========================================================================
# TAB 3: BÁO CÁO KPI
# ===========================================================================
with tab3:
    if st.session_state.sol_ai is None:
        st.warning("Chưa có kết quả. Vui lòng chạy tối ưu ở tab **Tối ưu tuyến** trước.")
    else:
        tt, ai = st.session_state.sol_truyen_thong, st.session_state.sol_ai
        planning_time_tt_min = 180.0  # thời gian lập kế hoạch thủ công (giả lập, không bắt người dùng chờ)
        planning_time_ai_min = st.session_state.ai_time_s / 60.0

        def delta_pct(old, new):
            if old == 0:
                return 0.0
            return (new - old) / old * 100

        rows = [
            ("Tổng quãng đường", tt["tong_quang_duong_km"], ai["tong_quang_duong_km"], "km"),
            ("Tỷ lệ xe chạy rỗng", tt["ty_le_chay_rong_pct"], ai["ty_le_chay_rong_pct"], "%"),
            ("OTIF - giao đúng hạn", tt["otif_pct"], ai["otif_pct"], "%"),
            ("Nhiên liệu tiêu thụ", tt["nhien_lieu_lit"], ai["nhien_lieu_lit"], "lít"),
            ("Phát thải CO₂", tt["co2_kg"], ai["co2_kg"], "kg"),
            ("Chi phí nhiên liệu", tt["chi_phi_vnd"], ai["chi_phi_vnd"], "VNĐ"),
            ("Số xe sử dụng", tt["so_xe_su_dung"], ai["so_xe_su_dung"], "xe"),
        ]

        cards_html = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.75rem;font-family:\'Be Vietnam Pro\',sans-serif;">'
        for label, old, new, unit in rows:
            pct = delta_pct(old, new)
            higher_is_better = "OTIF" in label
            is_good = (pct >= 0) if higher_is_better else (pct <= 0)
            arrow = "▲" if pct >= 0 else "▼"
            pill_color = "#16A34A" if is_good else "#DC2626"
            pill_bg = "#E7F6EC" if is_good else "#FCE9E9"
            cards_html += f"""
            <div style="background:#FFFFFF;border:1px solid #E7E5F2;border-radius:14px;padding:1rem 1.1rem;min-height:108px;
                        display:flex;flex-direction:column;justify-content:space-between;">
              <div style="font-size:0.8rem;font-weight:600;color:#6E6B85;">{label}</div>
              <div>
                <div style="font-size:1.25rem;font-weight:700;color:#33314A;line-height:1.2;">
                    {new:,.1f} <span style="font-size:0.7rem;font-weight:600;color:#6E6B85;">{unit}</span>
                </div>
                <span style="display:inline-block;margin-top:0.3rem;background:{pill_bg};color:{pill_color};
                             font-size:0.72rem;font-weight:700;padding:0.15rem 0.5rem;border-radius:999px;">
                    {arrow} {abs(pct):.1f}%
                </span>
              </div>
            </div>"""
        cards_html += '</div>'
        st.markdown(cards_html, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="margin-top:0.85rem;background:#FFFFFF;border:1px solid #E7E5F2;border-radius:14px;
                    padding:1rem 1.2rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.6rem;">
          <div style="font-weight:700;color:#33314A;">Thời gian lập kế hoạch</div>
          <div style="display:flex;gap:1.5rem;flex-wrap:wrap;">
            <div><span style="color:#6E6B85;font-size:0.82rem;">AI&nbsp;</span>
                 <span style="font-weight:700;color:#6D74E6;">{planning_time_ai_min*60:.2f} giây</span></div>
            <div><span style="color:#6E6B85;font-size:0.82rem;">Thủ công (giả lập)&nbsp;</span>
                 <span style="font-weight:700;color:#33314A;">{planning_time_tt_min:.0f} phút</span></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("Biểu đồ mức cải thiện tổng hợp")
        chart_df = pd.DataFrame({
            "Chỉ tiêu": [r[0] for r in rows],
            "Mức thay đổi (%)": [
                (r[2] - r[1]) / r[1] * 100 if r[1] else 0 for r in rows
            ],
        }).set_index("Chỉ tiêu")
        st.bar_chart(chart_df, horizontal=True)

        st.subheader("Bảng so sánh chi tiết")
        table = pd.DataFrame([
            {"Chỉ tiêu": r[0], "Truyền thống": round(r[1], 2), "AI": round(r[2], 2),
             "Mức thay đổi": f"{'+' if delta_pct(r[1], r[2]) >= 0 else ''}{delta_pct(r[1], r[2]):.1f}%"}
            for r in rows
        ])
        st.dataframe(table, use_container_width=True, hide_index=True)

        if tt["so_don_khong_gan_duoc"] or ai["so_don_khong_gan_duoc"]:
            st.warning(f"Đơn hàng không gán được xe — Truyền thống: {tt['so_don_khong_gan_duoc']}, "
                       f"AI: {ai['so_don_khong_gan_duoc']} (đội xe hiện có không đủ tải trọng tổng).")