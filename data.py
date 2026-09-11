# data.py
# Sinh dữ liệu mẫu: 100 đơn hàng (khu vực TP.HCM - Bình Dương - Đồng Nai)
# và đội xe mẫu (8-10 xe, nhiều loại tải trọng).

import random
import pandas as pd

# Bounding box gần đúng khu vực TP.HCM - Bình Dương - Đồng Nai
LAT_MIN, LAT_MAX = 10.55, 11.15
LON_MIN, LON_MAX = 106.45, 107.05

# Kho trung tâm đặt tại khu vực trung tâm TP.HCM (giả định)
DEPOT = {"name": "Kho trung tâm", "lat": 10.7769, "lon": 106.7009}

# Đội xe mẫu: loại xe -> (tải trọng tấn, định mức tiêu hao lít/km)
VEHICLE_TYPES = [
    {"loai": "Xe tải 2.5 tấn", "tai_trong": 2.5, "dinh_muc_l_km": 0.12},
    {"loai": "Xe tải 5 tấn",   "tai_trong": 5.0, "dinh_muc_l_km": 0.18},
    {"loai": "Xe tải 8 tấn",   "tai_trong": 8.0, "dinh_muc_l_km": 0.24},
    {"loai": "Xe container",  "tai_trong": 20.0, "dinh_muc_l_km": 0.35},
]

FUEL_TYPES = ["Dầu diesel"]


def generate_orders(n=100, seed=42):
    """Sinh n đơn hàng ngẫu nhiên trong khu vực, có mã đơn, tọa độ giao,
    khối lượng (tấn) và khung giờ giao hàng."""
    rng = random.Random(seed)
    rows = []
    for i in range(1, n + 1):
        lat = rng.uniform(LAT_MIN, LAT_MAX)
        lon = rng.uniform(LON_MIN, LON_MAX)
        weight = round(rng.uniform(0.3, 3.0), 2)
        # khung giờ giao hàng trong ca làm việc 06:00-18:00 (tính bằng giờ lệch so với 06:00)
        start = round(rng.uniform(0, 9), 1)
        end = round(start + rng.uniform(1.5, 4.0), 1)
        rows.append({
            "ma_don": f"DH{i:03d}",
            "lay_lat": round(DEPOT["lat"] + rng.uniform(-0.01, 0.01), 6),
            "lay_lon": round(DEPOT["lon"] + rng.uniform(-0.01, 0.01), 6),
            "giao_lat": round(lat, 6),
            "giao_lon": round(lon, 6),
            "khoi_luong_tan": weight,
            "khung_gio_bat_dau_h": start,
            "khung_gio_ket_thuc_h": end,
        })
    return pd.DataFrame(rows)


def generate_fleet(seed=7, min_veh=8, max_veh=10):
    """Sinh đội xe mẫu 8-10 xe, các loại tải trọng khác nhau."""
    rng = random.Random(seed)
    n = rng.randint(min_veh, max_veh)
    fleet = []
    for i in range(1, n + 1):
        vt = rng.choice(VEHICLE_TYPES)
        fleet.append({
            "ma_xe": f"XE{i:02d}",
            "loai_xe": vt["loai"],
            "tai_trong_tan": vt["tai_trong"],
            "dinh_muc_tieu_hao_l_km": vt["dinh_muc_l_km"],
            "loai_nhien_lieu": "Dầu diesel",
        })
    return pd.DataFrame(fleet)


def save_sample_csv(path="sample_orders.csv", n=100, seed=42):
    df = generate_orders(n=n, seed=seed)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def load_orders_from_upload(uploaded_file):
    """Đọc file Excel/CSV do người dùng tải lên, kỳ vọng cùng cấu trúc cột
    với dữ liệu mẫu."""
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    return pd.read_excel(uploaded_file)


if __name__ == "__main__":
    save_sample_csv()
    print("Đã sinh sample_orders.csv")