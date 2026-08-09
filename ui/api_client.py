"""Thin HTTP client for the SAR Copilot FastAPI backend.

Interview point: Streamlit has zero business logic — it only calls the API.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class SarApiClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self, token: Optional[str] = None) -> dict[str, str]:
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def _raise_for_detail(self, response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            payload = response.json()
            detail = payload.get("detail", response.text)
        except Exception:
            detail = response.text or response.reason_phrase
        if isinstance(detail, list):
            detail = "; ".join(str(item) for item in detail)
        raise ApiError(response.status_code, str(detail))

    def login(self, email: str, password: str) -> str:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.post(
                "/api/v1/auth/login",
                data={"username": email, "password": password},
            )
            self._raise_for_detail(response)
            return response.json()["access_token"]

    def me(self, token: str) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.get("/api/v1/auth/me", headers=self._headers(token))
            self._raise_for_detail(response)
            return response.json()

    def list_cases(self, token: str) -> list[dict[str, Any]]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.get("/api/v1/cases", headers=self._headers(token))
            self._raise_for_detail(response)
            return response.json()

    def get_case(self, token: str, case_id: int) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.get(f"/api/v1/cases/{case_id}", headers=self._headers(token))
            self._raise_for_detail(response)
            return response.json()

    def list_drafts(self, token: str, case_id: int) -> list[dict[str, Any]]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.get(
                f"/api/v1/cases/{case_id}/drafts",
                headers=self._headers(token),
            )
            self._raise_for_detail(response)
            return response.json()

    def generate_draft(self, token: str, case_id: int) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.post(
                f"/api/v1/cases/{case_id}/generate-draft",
                headers=self._headers(token),
            )
            self._raise_for_detail(response)
            return response.json()

    def update_draft(self, token: str, case_id: int, fields: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.patch(
                f"/api/v1/cases/{case_id}/draft",
                headers=self._headers(token),
                json=fields,
            )
            self._raise_for_detail(response)
            return response.json()

    def submit_case(self, token: str, case_id: int) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.post(
                f"/api/v1/cases/{case_id}/submit",
                headers=self._headers(token),
            )
            self._raise_for_detail(response)
            return response.json()

    def approve_case(self, token: str, case_id: int, comment: str) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.post(
                f"/api/v1/cases/{case_id}/approve",
                headers=self._headers(token),
                json={"comment": comment},
            )
            self._raise_for_detail(response)
            return response.json()

    def reject_case(self, token: str, case_id: int, comment: str) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.post(
                f"/api/v1/cases/{case_id}/reject",
                headers=self._headers(token),
                json={"comment": comment},
            )
            self._raise_for_detail(response)
            return response.json()

    def case_audit(self, token: str, case_id: int) -> list[dict[str, Any]]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.get(
                f"/api/v1/cases/{case_id}/audit",
                headers=self._headers(token),
            )
            self._raise_for_detail(response)
            return response.json()
