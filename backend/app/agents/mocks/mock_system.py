# Giả lập Database của hệ thống (Entity Relationship)
MOCK_SYSTEM_DB = {
    # Bảng User -> Stations
    "ff2f26bd-e6e5-4b15-9d89-9f514289f510": [
        {
            "station_id": "TRAM_01",
            "station_name": "Ruộng lúa số 1",
            "location": "Vĩnh Long",
            "crop": "Lúa Hè Thu",
        },
        {
            "station_id": "TRAM_02",
            "station_name": "Vườn Xoài Cát",
            "location": "Cần Thơ",
            "crop": "Xoài",
        },
    ],
    # Bảng Trạm -> Dữ liệu IoT & Giai đoạn sinh trưởng
    "station_data": {
        "TRAM_01": {
            "iot": {"N": "30", "P": "45", "K": "180", "pH": 4.5, "do_am": 40},
            "stage": {"days": 35, "current": "Cuối đẻ nhánh", "next": "Làm đòng"},
        },
        "TRAM_02": {
            "iot": {"N": "200", "P": "80", "K": "250", "pH": 6.0, "do_am": 65},
            "stage": {"days": 60, "current": "Ra hoa", "next": "Tạo trái non"},
        },
    },
}
