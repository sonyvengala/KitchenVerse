"""Image Service: local file upload and remote URL downloads for menu items.
Enforces strict security: server-side validation, SSRF defense, file size limits, magic bytes.
"""
import os
import time
import uuid
import logging
import socket
import ipaddress
import urllib.parse
from typing import Optional
from fastapi import HTTPException, status
import httpx

logger = logging.getLogger(__name__)

UPLOADS_DIR = os.path.join(os.getcwd(), "data", "uploads", "menu_images")
os.makedirs(UPLOADS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_magic_bytes(data: bytes) -> str:
    """Validate image magic bytes and return canonical extension (.png, .jpg, .webp) or raise HTTPException."""
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid image format. Allowed formats are PNG, JPG, JPEG, and WEBP."
    )


def is_ip_allowed(ip_str: str) -> bool:
    """Check if an IP address is a public, non-reserved address (anti-SSRF)."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_reserved
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
        return True
    except ValueError:
        return False


def validate_url_host(url: str) -> str:
    """Validate URL scheme and resolve host to ensure it is not targeting internal/loopback IPs."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image URL. Only HTTP and HTTPS URLs are supported."
        )
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image URL: missing hostname."
        )

    # Check for localhost literal
    if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security violation: private or local network addresses are not permitted."
        )

    try:
        ip_addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image URL: could not resolve host '{hostname}'."
        )

    for item in ip_addresses:
        ip_str = item[4][0]
        if not is_ip_allowed(ip_str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: private or local network addresses are not permitted."
            )

    return hostname


class MenuImageService:
    @staticmethod
    def validate_and_save_upload_file(
        file_content: bytes,
        original_filename: str,
        content_type: Optional[str],
        item_id: str
    ) -> str:
        """Validate and persist an uploaded image file."""
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image exceeds maximum allowed size of 5 MB."
            )
        if len(file_content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty."
            )

        # Check extension
        ext = os.path.splitext(original_filename)[1].lower() if original_filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file extension '{ext}'. Allowed extensions are PNG, JPG, JPEG, and WEBP."
            )

        # Check MIME type if supplied
        if content_type:
            clean_mime = content_type.lower().split(";")[0].strip()
            if clean_mime not in ALLOWED_MIME_TYPES and not clean_mime.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid MIME type '{clean_mime}'. Must be an image (PNG, JPG, or WEBP)."
                )

        # Validate magic bytes
        magic_ext = validate_magic_bytes(file_content)
        final_ext = ext if ext in (magic_ext, ".jpeg" if magic_ext == ".jpg" else magic_ext) else magic_ext

        safe_filename = f"dish_{item_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}{final_ext}"
        filepath = os.path.join(UPLOADS_DIR, safe_filename)
        with open(filepath, "wb") as f:
            f.write(file_content)

        return f"/uploads/menu_images/{safe_filename}"

    @staticmethod
    def download_and_save_remote_image(url: str, item_id: str) -> str:
        """Validate, download, and store a remote web image locally with SSRF protection."""
        url = url.strip()
        if not url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image URL is required."
            )

        current_url = url
        max_redirects = 4
        client = httpx.Client(timeout=10.0, follow_redirects=False)

        try:
            for _ in range(max_redirects):
                validate_url_host(current_url)
                try:
                    resp = client.get(
                        current_url,
                        headers={"User-Agent": "CloudKitchen-ImageDownloader/1.0"}
                    )
                except httpx.TimeoutException:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Image download timed out after 10 seconds."
                    )
                except httpx.RequestError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to fetch image from URL: {str(exc)}"
                    )

                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location")
                    if not location:
                        break
                    current_url = urllib.parse.urljoin(current_url, location)
                    continue

                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Remote server returned error status {resp.status_code}."
                    )

                content_type = resp.headers.get("Content-Type", "").lower().split(";")[0].strip()
                if not content_type.startswith("image/"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"URL did not return an image. Content-Type is '{content_type}'."
                    )

                content = resp.content
                if len(content) > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Remote image exceeds maximum allowed size of 5 MB."
                    )
                if len(content) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Remote image response is empty."
                    )

                ext = validate_magic_bytes(content)
                safe_filename = f"dish_{item_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"
                filepath = os.path.join(UPLOADS_DIR, safe_filename)
                with open(filepath, "wb") as f:
                    f.write(content)

                return f"/uploads/menu_images/{safe_filename}"

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many redirects while downloading remote image."
            )
        finally:
            client.close()
