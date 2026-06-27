import requests
import base64
import json
from typing import List, Dict, Any

class PPMClient:
    BASE_URL = "http://103.221.220.184:8026/api/ppm"

    def _get_headers(self, token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def _get_domain_id_from_token(self, token: str) -> str:
        """Trích xuất 'dom' (Domain ID) từ JWT."""
        try:
            parts = token.split(".")
            if len(parts) >= 2:
                payload = parts[1]
                # Thêm padding nếu thiếu
                payload += '=' * (-len(payload) % 4)
                decoded = base64.b64decode(payload)
                data = json.loads(decoded)
                # Trả về 'dom' thay vì 'sub' dựa trên góp ý của user
                return data.get("dom", "")
        except Exception as e:
            print(f"[PPM Client] Error decoding token: {e}")
        return ""

    def get_projects(self, token: str, statuses: List[str] = None) -> List[Dict[str, Any]]:
        """Lấy danh sách các dự án của người dùng theo trạng thái."""
        domain_id = self._get_domain_id_from_token(token)
        if not domain_id:
            print("[PPM Client] Warning: Không tìm thấy domainId (dom) trong token.")
            return []
            
        url = f"{self.BASE_URL}/projects"
        # Support passing multiple statuses, e.g. ?status=IN_PROGRESS&status=DONE
        # requests library handles list in params automatically
        params = {
            "domainId": domain_id,
        }
        if statuses:
            params["status"] = statuses
        try:
            response = requests.get(url, headers=self._get_headers(token), params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if e.response is not None and e.response.status_code == 401:
                raise e
            print(f"[PPM API Error] get_projects: {e}")
            return []

    def get_project_tasks(self, token: str, project_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách công việc của một dự án."""
        url = f"{self.BASE_URL}/tasks"
        params = {
            "projectId": project_id
        }
        try:
            response = requests.get(url, headers=self._get_headers(token), params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if e.response is not None and e.response.status_code == 401:
                raise e
            print(f"[PPM API Error] get_project_tasks for {project_id}: {e}")
            return []
            
    def get_tasks_by_statuses(self, token: str, statuses: List[str] = None) -> List[Dict[str, Any]]:
        """Hàm tiện ích lấy tất cả các task của người dùng theo trạng thái (mặc định IN_PROGRESS)."""
        if statuses is None:
            statuses = ["IN_PROGRESS"]
            
        # Fetch all projects for the domain without filtering by project status.
        # Project statuses (PENDING) are different from Task statuses (OPEN).
        projects = self.get_projects(token, statuses=None)
        all_filtered_tasks = []
        
        for proj in projects:
            proj_id = proj.get("id")
            if not proj_id:
                continue
                
            tasks = self.get_project_tasks(token, proj_id)
            for t in tasks:
                t_status = t.get("status")
                if t_status in statuses:
                    # Gắn thêm tên dự án để làm context
                    t["projectName"] = proj.get("name", "Unnamed Project")
                    all_filtered_tasks.append(t)
                    
        return all_filtered_tasks
