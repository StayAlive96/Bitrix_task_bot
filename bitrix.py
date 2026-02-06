from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx


@dataclass
class BitrixError(Exception):
    message: str
    details: str = ""


class BitrixClient:
    def __init__(self, webhook_base: str, timeout: float = 20.0):
        self.webhook_base = webhook_base
        self.timeout = timeout

    async def call(self, method: str, data: list[tuple[str, str]] | dict[str, str]) -> dict[str, Any]:
        url = f"{self.webhook_base}{method}"
        encoded = urlencode(data).encode("utf-8")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                content=encoded,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        try:
            payload = response.json()
        except Exception:
            raise BitrixError(
                f"Bitrix returned non-JSON response (HTTP {response.status_code})",
                response.text,
            )

        if "error" in payload:
            raise BitrixError(payload.get("error", "bitrix_error"), payload.get("error_description", ""))
        return payload

    async def upload_to_folder(self, folder_id: int, local_path: str, filename: str | None = None) -> int:
        url = f"{self.webhook_base}disk.folder.uploadfile"
        name = filename or Path(local_path).name

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            with open(local_path, "rb") as file_obj:
                content = file_obj.read()
                response = await client.post(
                    url,
                    data={"id": str(int(folder_id))},
                    files={"file": (name, content)},
                )

        try:
            payload = response.json()
        except Exception:
            raise BitrixError(
                f"Bitrix returned non-JSON response (HTTP {response.status_code})",
                response.text,
            )

        if "error" in payload:
            raise BitrixError(payload.get("error", "bitrix_error"), payload.get("error_description", ""))

        try:
            return int(payload["result"]["ID"])
        except Exception:
            raise BitrixError("Cannot parse disk file id from Bitrix response", str(payload))

    async def create_task(
        self,
        title: str,
        description: str,
        responsible_id: int,
        group_id: int | None = None,
        priority: int | None = None,
        created_by: int | None = None,
        webdav_file_ids: list[int] | None = None,
    ) -> int:
        fields: list[tuple[str, str]] = [
            ("fields[TITLE]", title),
            ("fields[DESCRIPTION]", description),
            ("fields[RESPONSIBLE_ID]", str(responsible_id)),
        ]

        if group_id is not None:
            fields.append(("fields[GROUP_ID]", str(group_id)))
        if priority is not None:
            fields.append(("fields[PRIORITY]", str(priority)))
        if created_by is not None:
            fields.append(("fields[CREATED_BY]", str(created_by)))
        if webdav_file_ids:
            for idx, file_id in enumerate(webdav_file_ids):
                fields.append((f"fields[UF_TASK_WEBDAV_FILES][{idx}]", f"n{int(file_id)}"))

        payload = await self.call("tasks.task.add", fields)
        try:
            return int(payload["result"]["task"]["id"])
        except Exception:
            try:
                return int(payload["result"]["id"])
            except Exception:
                raise BitrixError("Cannot parse task id from Bitrix response", str(payload))
