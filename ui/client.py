"""HTTP client helper for the Streamlit UI."""

from __future__ import annotations

import os

import httpx


def api_url() -> str:
    return os.environ.get("API_URL", "http://127.0.0.1:8000").rstrip("/")


def api_get(path: str) -> dict:
    resp = httpx.get(f"{api_url()}{path}", timeout=60.0)
    resp.raise_for_status()
    return resp.json()


def api_post_json(path: str, payload: dict) -> dict:
    resp = httpx.post(f"{api_url()}{path}", json=payload, timeout=300.0)
    resp.raise_for_status()
    return resp.json()


def api_post_file(path: str, file_name: str, file_bytes: bytes, data: dict) -> dict:
    resp = httpx.post(
        f"{api_url()}{path}",
        files={"file": (file_name, file_bytes)},
        data=data,
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()


def api_get_bytes(path: str) -> tuple[bytes, str]:
    resp = httpx.get(f"{api_url()}{path}", timeout=60.0)
    resp.raise_for_status()
    disp = resp.headers.get("content-disposition", "")
    filename = "export.xlsx"
    if "filename=" in disp:
        filename = disp.split("filename=")[-1].strip('"')
    return resp.content, filename
