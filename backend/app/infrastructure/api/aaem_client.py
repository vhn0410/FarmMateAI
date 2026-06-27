import requests
from typing import List, Dict, Any

class AAEMClient:
    BASE_URL = "http://103.221.220.184:8026"

    def _get_headers(self, token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def get_agri_areas(self, token: str) -> List[Dict[str, Any]]:
        """Lấy danh sách khu vực nông nghiệp của người dùng."""
        url = f"{self.BASE_URL}/agri-areas/"
        try:
            response = requests.get(url, headers=self._get_headers(token), timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if e.response is not None and e.response.status_code == 401:
                raise e
            print(f"[AAEM API Error] get_agri_areas: {e}")
            return []

    def get_stations_for_area(self, token: str, area_id: int) -> List[Dict[str, Any]]:
        """Lấy danh sách các trạm trong một khu vực nông nghiệp."""
        url = f"{self.BASE_URL}/stations/agri-area/{area_id}"
        try:
            response = requests.get(url, headers=self._get_headers(token), timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if e.response is not None and e.response.status_code == 401:
                raise e
            print(f"[AAEM API Error] get_stations_for_area (area {area_id}): {e}")
            return []

    def get_latest_observations(self, token: str, datastream_ids: List[int]) -> List[Dict[str, Any]]:
        """Lấy số liệu quan trắc mới nhất dựa trên danh sách dataStreamId."""
        url = f"{self.BASE_URL}/observations/dataStreamIds/latest"
        try:
            # Lưu ý: Postman để là GET nhưng API này cần gửi json body. Requests cho phép GET có json, 
            # nhưng chuẩn REST thường là POST. Postman JSON hiện đã đổi method: POST.
            response = requests.post(url, headers=self._get_headers(token), json=datastream_ids, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if e.response is not None and e.response.status_code == 401:
                raise e
            print(f"[AAEM API Error] get_latest_observations: {e}")
            return []

    def fetch_all_user_stations(self, token: str) -> List[Dict[str, Any]]:
        """Hàm tiện ích gom toàn bộ trạm của tất cả các agri-areas."""
        areas = self.get_agri_areas(token)
        all_stations = []
        for area in areas:
            area_id = area.get("agriAreaId")
            if area_id:
                stations = self.get_stations_for_area(token, area_id)
                all_stations.extend(stations)
        return all_stations
