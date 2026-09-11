# optimizer.py
# Hai kịch bản ghép đơn:
#  - traditional_routes: mô phỏng cách điều vận viên làm thủ công (tuần tự
#    theo danh sách gốc, không tối ưu tải trọng, không né ùn tắc).
#  - ai_routes: "AI Engine" = Nearest-Neighbor có ràng buộc tải trọng,
#    lấp đầy xe trước khi mở xe mới, sau đó sắp lại theo khung giờ giao.
#
# Toàn bộ số liệu (quãng đường, chi phí, CO2, OTIF...) được TÍNH THẬT từ dữ
# liệu và thuật toán bên dưới, không có bước "ép" kết quả khớp con số định
# trước — vì vậy kết quả có thể khác giữa các lần chạy nếu đổi dữ liệu/seed.

from utils import haversine_km, route_distance_km, fuel_cost, co2_emission, AVG_SPEED_KMH

LOADING_TIME_H = 0.25  # 15 phút bốc/xếp mỗi điểm dừng


def _depot_coord(depot):
    return depot["lat"], depot["lon"]


def _expand_fleet(fleet, max_trips):
    """Mỗi xe có thể chạy nhiều chuyến trong ngày (quay về kho lấy hàng tiếp).
    Trả về danh sách 'chuyến xe' theo từng đợt: chuyến 1 của mọi xe trước,
    rồi mới đến chuyến 2... để ưu tiên dùng ít xe nhất trước khi cần thêm chuyến."""
    expanded = []
    for t in range(1, max_trips + 1):
        for v in fleet:
            vv = dict(v)
            vv["chuyen"] = t
            vv["ma_xe"] = f"{v['ma_xe']}-C{t}"
            expanded.append(vv)
    return expanded


# ---------------------------------------------------------------------------
# Phương pháp truyền thống: ghép tuần tự theo thứ tự đơn hàng gốc,
# xe đầy tải mới chuyển sang xe kế tiếp trong danh sách đội xe.
# ---------------------------------------------------------------------------
def traditional_routes(orders_df, fleet_df, max_trips=4):
    orders = orders_df.to_dict("records")
    fleet = _expand_fleet(fleet_df.to_dict("records"), max_trips)
    routes, unassigned = [], []
    if not fleet:
        return routes, orders

    fi = 0
    current = {"xe": fleet[0], "don_hang": [], "tai": 0.0}

    for o in orders:
        # đơn hàng không vừa xe hiện tại -> đóng tuyến, chuyển sang xe kế tiếp
        # trong danh sách đội xe (không xét khoảng cách, đúng bản chất "thủ công")
        while current is not None and current["tai"] + o["khoi_luong_tan"] > current["xe"]["tai_trong_tan"]:
            if current["don_hang"]:
                routes.append(current)
            fi += 1
            current = {"xe": fleet[fi], "don_hang": [], "tai": 0.0} if fi < len(fleet) else None

        if current is None:
            unassigned.append(o)  # hết xe trong đội -> đơn không được phục vụ
            continue

        current["don_hang"].append(o)
        current["tai"] += o["khoi_luong_tan"]

    if current is not None and current["don_hang"]:
        routes.append(current)

    return routes, unassigned


# ---------------------------------------------------------------------------
# AI Engine: Nearest-Neighbor có ràng buộc tải trọng, ưu tiên lấp đầy xe
# tải trọng lớn trước, sau đó sắp lại thứ tự giao theo khung giờ.
# weights = (w_cost, w_time, w_co2) ảnh hưởng nhẹ đến thứ tự chọn đơn kế tiếp.
# ---------------------------------------------------------------------------
def ai_routes(orders_df, fleet_df, depot, weights=(1.0, 1.0, 1.0), max_trips=4):
    orders = orders_df.to_dict("records")
    fleet = sorted(_expand_fleet(fleet_df.to_dict("records"), max_trips), key=lambda v: -v["tai_trong_tan"])
    unassigned = orders.copy()
    routes = []
    w_cost, w_time, w_co2 = weights

    for vehicle in fleet:
        if not unassigned:
            break
        route_orders, load = [], 0.0
        cur = _depot_coord(depot)
        while True:
            candidates = [o for o in unassigned if load + o["khoi_luong_tan"] <= vehicle["tai_trong_tan"]]
            if not candidates:
                break

            def score(o):
                d = haversine_km(cur[0], cur[1], o["giao_lat"], o["giao_lon"])
                # đơn có hạn giao gấp hơn được ưu tiên nhẹ theo w_time
                urgency_bonus = (10 - min(o["khung_gio_ket_thuc_h"], 10)) * 0.03 * w_time
                # đơn nặng hơn (chở nhiều hơn/ chuyến) được ưu tiên nhẹ theo w_cost (giảm số chuyến)
                load_bonus = o["khoi_luong_tan"] * 0.02 * w_cost
                # w_co2 hiện ảnh hưởng gián tiếp qua việc ưu tiên khoảng cách ngắn
                return d * (1.0 + 0.1 * w_co2) - urgency_bonus - load_bonus

            best = min(candidates, key=score)
            route_orders.append(best)
            load += best["khoi_luong_tan"]
            cur = (best["giao_lat"], best["giao_lon"])
            unassigned.remove(best)

        if route_orders:
            route_orders.sort(key=lambda o: o["khung_gio_bat_dau_h"])  # sắp theo khung giờ giao
            routes.append({"xe": vehicle, "don_hang": route_orders, "tai": load})

    return routes, unassigned


# ---------------------------------------------------------------------------
# Tính KPI cho một tuyến / một phương án (nhiều tuyến)
# ---------------------------------------------------------------------------
def compute_route_metrics(route, depot, fuel_price):
    depot_c = _depot_coord(depot)
    coords = [depot_c] + [(o["giao_lat"], o["giao_lon"]) for o in route["don_hang"]] + [depot_c]
    distance = route_distance_km(coords)

    liters, cost = fuel_cost(distance, route["xe"]["dinh_muc_tieu_hao_l_km"], fuel_price)
    co2 = co2_emission(distance)

    # mô phỏng thời gian tích lũy để tính OTIF và quãng đường chạy rỗng
    t, cur = 0.0, depot_c
    stops = []
    for o in route["don_hang"]:
        d = haversine_km(cur[0], cur[1], o["giao_lat"], o["giao_lon"])
        t += d / AVG_SPEED_KMH
        on_time = t <= o["khung_gio_ket_thuc_h"]
        stops.append({"ma_don": o["ma_don"], "khoi_luong_tan": o["khoi_luong_tan"],
                       "gio_du_kien_h": round(t, 2), "dung_han": on_time})
        t += LOADING_TIME_H
        cur = (o["giao_lat"], o["giao_lon"])
    empty_km = haversine_km(cur[0], cur[1], depot_c[0], depot_c[1])  # chặng cuối về kho luôn chạy rỗng

    return {
        "xe": route["xe"], "so_don": len(route["don_hang"]), "tai": route["tai"],
        "quang_duong_km": distance, "quang_duong_rong_km": empty_km,
        "nhien_lieu_lit": liters, "chi_phi_vnd": cost, "co2_kg": co2,
        "stops": stops, "coords": coords,
    }


def evaluate_solution(routes, unassigned, depot, fuel_price):
    details = [compute_route_metrics(r, depot, fuel_price) for r in routes]
    total_distance = sum(d["quang_duong_km"] for d in details)
    total_empty = sum(d["quang_duong_rong_km"] for d in details)
    total_fuel = sum(d["nhien_lieu_lit"] for d in details)
    total_cost = sum(d["chi_phi_vnd"] for d in details)
    total_co2 = sum(d["co2_kg"] for d in details)
    served = sum(d["so_don"] for d in details)
    on_time = sum(1 for d in details for s in d["stops"] if s["dung_han"])

    return {
        "chi_tiet": details,
        "tong_quang_duong_km": total_distance,
        "quang_duong_rong_km": total_empty,
        "ty_le_chay_rong_pct": (total_empty / total_distance * 100) if total_distance else 0,
        "nhien_lieu_lit": total_fuel,
        "chi_phi_vnd": total_cost,
        "co2_kg": total_co2,
        "so_don_phuc_vu": served,
        "so_don_khong_gan_duoc": len(unassigned),
        "otif_pct": (on_time / served * 100) if served else 0,
        "so_xe_su_dung": len(details),
    }