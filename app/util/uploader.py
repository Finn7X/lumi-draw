"""
Image upload + URL generation.

Strategy: try local copy to shared directory first, fall back to SFTP.
"""

import os
import shutil
import logging

from ..config import get_settings

logger = logging.getLogger(__name__)


def upload_image(local_path: str) -> dict:
    """
    Upload an image and return an accessible URL.

    Strategy:
        1. Local shutil.copy2 (if shared directory is mounted).
        2. Fallback SFTP upload to remote server.

    Args:
        local_path: Local image file path.

    Returns:
        dict: {status, url} or {status, error}.
    """
    if not os.path.exists(local_path):
        return {"status": "error", "error": f"File not found: {local_path}"}

    settings = get_settings()
    filename = os.path.basename(local_path)
    image_url = settings.image_url_base + filename

    # Strategy 1: local copy
    if _try_local_copy(local_path, filename, settings.image_local_dir):
        logger.info("[uploader] Local copy OK: %s -> %s", local_path, image_url)
        return {"status": "success", "url": image_url}

    # Strategy 2: SFTP upload
    if _try_sftp_upload(local_path, filename, settings):
        logger.info("[uploader] SFTP upload OK: %s -> %s", local_path, image_url)
        return {"status": "success", "url": image_url}

    return {
        "status": "error",
        "error": "Both local copy and SFTP upload failed. Check directory permissions or network.",
    }


def _try_local_copy(local_path: str, filename: str, image_local_dir: str) -> bool:
    """Attempt to copy the file to the local shared image directory."""
    try:
        if not os.path.isdir(image_local_dir):
            logger.debug("[uploader] Local dir not accessible: %s", image_local_dir)
            return False

        dest_path = os.path.join(image_local_dir, filename)
        shutil.copy2(local_path, dest_path)
        return True
    except Exception as e:
        logger.debug("[uploader] Local copy failed: %s", e)
        return False


def _try_sftp_upload(local_path: str, filename: str, settings) -> bool:
    """Upload to the remote server via SFTP."""
    try:
        import paramiko
    except ImportError:
        logger.warning("[uploader] paramiko not installed, SFTP unavailable")
        return False

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            settings.image_remote_host,
            username=settings.image_sftp_username,
            timeout=10,
            allow_agent=True,
            look_for_keys=True,
        )

        sftp = ssh.open_sftp()
        remote_path = settings.image_remote_dir + filename
        sftp.put(local_path, remote_path)
        sftp.close()
        ssh.close()
        return True
    except Exception as e:
        logger.warning("[uploader] SFTP upload failed: %s", e)
        return False
