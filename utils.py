# utils.py
# Các hàm tính toán dùng chung: khoảng cách, chi phí, phát thải, thời gian.

import math

EMISSION_FACTOR = 0.82  # kg CO2 / km, xe tải nhẹ (tham chiếu khung GLEC)
AVG_SPEED_KMH = 40       # vận tốc trung bình mặc định


def haversine_km(lat1, lon1, lat2, lon2):
    """Khoảng cách đường chim bay giữa 2 tọa độ (km) theo công thức Haversine."""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def route_distance_km(coords):
    """Tổng khoảng cách của 1 tuyến (list tọa độ (lat, lon) đi qua liên tiếp)."""
    d = 0.0
    for i in range(len(coords) - 1):
        lat1, lon1 = coords[i]
        lat2, lon2 = coords[i + 1]
        d += haversine_km(lat1, lon1, lat2, lon2)
    return d


def fuel_cost(distance_km, fuel_rate_l_per_km, fuel_price_vnd):
    """Chi phí nhiên liệu: C = D x định_mức_tiêu_hao(lít/km) x giá_dầu(VNĐ/lít)."""
    liters = distance_km * fuel_rate_l_per_km
    return liters, liters * fuel_price_vnd


def co2_emission(distance_km, factor=EMISSION_FACTOR):
    """Phát thải CO2: E = D x hệ_số_phát_thải (kg CO2/km)."""
    return distance_km * factor


def travel_time_hours(distance_km, avg_speed=AVG_SPEED_KMH, loading_time_h=0.0):
    """Thời gian: T = D / vận_tốc_trung_bình + thời_gian_bốc_xếp."""
    return distance_km / avg_speed + loading_time_h


def osrm_route_coords(coords, timeout=5):
    """Trả tọa độ đi theo đường thực tế (bám mạng lưới đường bộ) bằng OSRM
    demo server (miễn phí, không cần API key, chỉ dùng để VẼ bản đồ minh
    họa — không dùng để tính khoảng cách/KPI, KPI vẫn tính bằng Haversine
    như mô tả gốc). Nếu gọi API lỗi (mất mạng, quá giới hạn demo server),
    tự động rơi về vẽ đường thẳng giữa các điểm.
    coords: list các tuple (lat, lon) theo đúng thứ tự đi qua."""
    import requests
    if len(coords) < 2:
        return coords
    coord_str = ";".join(f"{lon},{lat}" for lat, lon in coords)
    url = f"http://router.project-osrm.org/route/v1/driving/{coord_str}?overview=full&geometries=geojson"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        geom = resp.json()["routes"][0]["geometry"]["coordinates"]  # [[lon,lat], ...]
        return [(lat, lon) for lon, lat in geom]
    except Exception:
        return coords  # fallback: giữ nguyên đường thẳng nếu không gọi được OSRM


def fmt_hms(hours):
    """Đổi số giờ (float) sang chuỗi HH:MM tính từ 06:00 xuất phát."""
    total_min = int(round(360 + hours * 60))
    h = (total_min // 60) % 24
    m = total_min % 60
    return f"{h:02d}:{m:02d}"