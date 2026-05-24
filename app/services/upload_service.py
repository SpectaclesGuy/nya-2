from __future__ import annotations

import os
import re
from typing import Tuple

import cloudinary.uploader
import cloudinary.utils
from fastapi import UploadFile

from app.core.cloudinary_client import configure_cloudinary
from app.core.config import settings


_SAFE_ID_RE = re.compile(r"[^a-zA-Z0-9_-]+")


class UploadService:
    @staticmethod
    async def upload_profile_resume_pdf(*, file: UploadFile, user_id: str) -> Tuple[str, str]:
        return await UploadService.upload_resume_pdf(file=file, user_id=user_id, job_id="profile")

    @staticmethod
    async def upload_resume_pdf(*, file: UploadFile, user_id: str, job_id: str) -> Tuple[str, str]:
        if not file:
            raise RuntimeError("Missing file")

        filename = (file.filename or "").lower()
        if not filename.endswith(".pdf"):
            raise RuntimeError("Only PDF allowed")

        content_type = (file.content_type or "").lower()
        if content_type not in {"application/pdf", "application/x-pdf"}:
            raise RuntimeError("Invalid file type")

        data = await file.read()
        max_bytes = int(settings.max_resume_size_mb) * 1024 * 1024
        if len(data) > max_bytes:
            raise RuntimeError("File too large")

        # Basic magic header check.
        if not data.startswith(b"%PDF"):
            raise RuntimeError("Invalid PDF")

        configure_cloudinary()
        if not (settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret):
            raise RuntimeError("Cloudinary not configured")

        base_public_id = f"resumes/{job_id}/{user_id}"
        public_id = _SAFE_ID_RE.sub("_", base_public_id)

        # Upload as raw to allow PDFs.
        # Prefer explicit base64 data URI for reliable uploads across environments.
        import base64

        b64 = base64.b64encode(data).decode("ascii")
        data_uri = f"data:application/pdf;base64,{b64}"

        result = cloudinary.uploader.upload(
            data_uri,
            resource_type="raw",
            public_id=public_id,
            type="private",
            overwrite=True,
            unique_filename=False,
            filename_override=os.path.basename(public_id) + ".pdf",
        )
        secure_url = result.get("secure_url")
        public_id_out = result.get("public_id")
        if not secure_url or not public_id_out:
            raise RuntimeError("Upload failed")
        public_id_out = str(public_id_out)
        # Some Cloudinary raw uploads may return public_id with an extension already appended.
        if public_id_out.lower().endswith(".pdf"):
            public_id_out = public_id_out[:-4]
        return secure_url, public_id_out

    @staticmethod
    def signed_resume_url(*, public_id: str, expires_in_seconds: int = 300) -> str:
        configure_cloudinary()
        if not (settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret):
            raise RuntimeError("Cloudinary not configured")
        import time

        expires_at = int(time.time()) + int(expires_in_seconds)

        pid = (public_id or "").strip()
        # Normalize: if stored with ".pdf" suffix, strip it to avoid ".pdf.pdf" URLs.
        if pid.lower().endswith(".pdf"):
            pid = pid[:-4]

        # Prefer dedicated private download URLs if supported by the SDK/account.
        # Some Cloudinary accounts will 401 on `raw/private/...` delivery URLs and require a download URL.
        try:
            private_download_url = getattr(cloudinary.utils, "private_download_url", None)
            if callable(private_download_url):
                return str(
                    private_download_url(
                        pid,
                        format="pdf",
                        resource_type="raw",
                        type="private",
                        expires_at=expires_at,
                    )
                )
        except Exception:
            pass

        url, _ = cloudinary.utils.cloudinary_url(
            pid,
            resource_type="raw",
            type="private",
            sign_url=True,
            expires_at=expires_at,
            format="pdf",
        )
        return str(url)
