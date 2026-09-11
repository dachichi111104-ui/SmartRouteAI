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
# Khởi tạo session state
# ---------------------------------------------------------------------------
for key, default in [
    ("orders", None), ("fleet", None), ("fuel_price", 21000),
    ("w_cost", 1.0), ("w_time", 1.0), ("w_co2", 1.0),
    ("sol_truyen_thong", None), ("sol_ai", None), ("ai_time_s", None), ("max_trips", 4),
]:
    if key not in st.session_state:
        st.session_state[key] = default

st.title("🚚 SmartRouteAI — Demo tối ưu hóa tuyến đường vận tải quốc nội")
st.caption("Minh họa phương pháp: Nearest-Neighbor có ràng buộc tải trọng, so sánh với cách điều vận thủ công.")

screen = st.sidebar.radio("Màn hình", [
    "1. Nhập dữ liệu (Data Input)",
    "2. Tối ưu tuyến (Optimization Dashboard)",
    "3. Báo cáo KPI (KPIs & Analytics)",
])

# ===========================================================================
# MÀN HÌNH 1: NHẬP DỮ LIỆU
# ===========================================================================
if screen.startswith("1"):
    st.header("Nhập dữ liệu")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Đơn hàng")
        if st.button("📥 Tải dữ liệu mẫu (100 đơn hàng)"):
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
        if st.button("🚛 Sinh đội xe mẫu"):
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

    st.info("Sau khi có dữ liệu đơn hàng và đội xe, chuyển sang màn hình **2. Tối ưu tuyến** để chạy so sánh.")

# ===========================================================================
# MÀN HÌNH 2: TỐI ƯU TUYẾN
# ===========================================================================
elif screen.startswith("2"):
    st.header("Bảng điều khiển & Tối ưu tuyến")

    if st.session_state.orders is None or st.session_state.fleet is None:
        st.warning("Vui lòng nạp dữ liệu đơn hàng và đội xe ở màn hình 1 trước.")
    else:
        if st.button("▶ BẮT ĐẦU TỐI ƯU HÓA (RUN AI ROUTE)", type="primary"):
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

            st.success("Đã tối ưu xong. Xem bản đồ và lịch trình bên dưới, hoặc sang màn hình 3 để xem KPI.")

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
# MÀN HÌNH 3: BÁO CÁO KPI
# ===========================================================================
else:
    st.header("Báo cáo KPI & So sánh")

    if st.session_state.sol_ai is None:
        st.warning("Chưa có kết quả. Vui lòng chạy tối ưu ở màn hình 2 trước.")
    else:
        tt, ai = st.session_state.sol_truyen_thong, st.session_state.sol_ai
        planning_time_tt_min = 180.0  # thời gian lập kế hoạch thủ công (giả lập, không bắt người dùng chờ)
        planning_time_ai_min = st.session_state.ai_time_s / 60.0

        def delta_pct(old, new, higher_is_better=False):
            if old == 0:
                return "0%"
            p = (new - old) / old * 100
            sign = "+" if p >= 0 else ""
            return f"{sign}{p:.1f}%"

        rows = [
            ("Tổng quãng đường (km)", tt["tong_quang_duong_km"], ai["tong_quang_duong_km"]),
            ("Tỷ lệ xe chạy rỗng (%)", tt["ty_le_chay_rong_pct"], ai["ty_le_chay_rong_pct"]),
            ("OTIF - giao đúng hạn (%)", tt["otif_pct"], ai["otif_pct"]),
            ("Nhiên liệu tiêu thụ (lít)", tt["nhien_lieu_lit"], ai["nhien_lieu_lit"]),
            ("Phát thải CO₂ (kg)", tt["co2_kg"], ai["co2_kg"]),
            ("Chi phí nhiên liệu (VNĐ)", tt["chi_phi_vnd"], ai["chi_phi_vnd"]),
            ("Số xe sử dụng", tt["so_xe_su_dung"], ai["so_xe_su_dung"]),
        ]

        cols = st.columns(4)
        for i, (label, old, new) in enumerate(rows):
            with cols[i % 4]:
                st.metric(label, f"{new:,.1f}", delta_pct(old, new), delta_color="inverse" if "OTIF" not in label else "normal")

        st.metric("Thời gian lập kế hoạch",
                   f"AI: {planning_time_ai_min*60:.2f} giây",
                   f"Thủ công (giả lập): {planning_time_tt_min:.0f} phút")

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
             "Mức thay đổi": delta_pct(r[1], r[2])}
            for r in rows
        ])
        st.dataframe(table, use_container_width=True, hide_index=True)

        if tt["so_don_khong_gan_duoc"] or ai["so_don_khong_gan_duoc"]:
            st.warning(f"Đơn hàng không gán được xe — Truyền thống: {tt['so_don_khong_gan_duoc']}, "
                       f"AI: {ai['so_don_khong_gan_duoc']} (đội xe hiện có không đủ tải trọng tổng).")