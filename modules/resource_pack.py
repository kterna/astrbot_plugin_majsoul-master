from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DEFAULT_RESOURCE_PACK_URL = (
    "https://github.com/kterna/astrbot_plugin_majsoul_resources/releases/download/"
    "v2026.05.04/majsoul-assets-full-2026.05.04.zip"
)
DEFAULT_RESOURCE_PACK_SHA256 = "6fa514b9026a68e6e374bfb48ed138d455d88096c0de3e6b7cbb7ecc60a79bc8"
REQUIRED_RESOURCE_DIRS = ("person", "background", "decoration", "gift", "jades")


@dataclass
class ResourcePackStatus:
    installed: bool
    resources_dir: Path
    version: str = ""
    file_count: int = 0
    total_size_bytes: int = 0


class ResourcePackManager:
    def __init__(self, data_root: Path, config: dict):
        self.data_root = Path(data_root)
        self.resources_dir = self.data_root / "resources"
        self.cache_dir = self.data_root / "cache" / "resource_pack"
        self.manifest_path = self.resources_dir / ".majsoul_resource_manifest.json"
        self.pack_url = config.get("resource_pack_url") or DEFAULT_RESOURCE_PACK_URL
        self.pack_sha256 = config.get("resource_pack_sha256") or DEFAULT_RESOURCE_PACK_SHA256
        self.timeout = int(config.get("resource_pack_timeout_seconds", 600))

    def status(self) -> ResourcePackStatus:
        manifest = self._load_manifest()
        return ResourcePackStatus(
            installed=self.is_installed(),
            resources_dir=self.resources_dir,
            version=str(manifest.get("version", "")),
            file_count=int(manifest.get("file_count", 0) or 0),
            total_size_bytes=int(manifest.get("total_size_bytes", 0) or 0),
        )

    def is_installed(self) -> bool:
        return all(self._dir_has_images(self.resources_dir / name) for name in REQUIRED_RESOURCE_DIRS)

    def install(self, force: bool = False) -> ResourcePackStatus:
        if self.is_installed() and not force:
            return self.status()

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self.cache_dir / "majsoul-resource-pack.zip"
        extract_dir = self.cache_dir / "extract"
        new_resources = extract_dir / "resources"
        manifest = extract_dir / "manifest.json"

        if extract_dir.exists():
            shutil.rmtree(extract_dir)

        self._download(zip_path)
        self._verify_sha256(zip_path)

        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)

        if not all((new_resources / name).is_dir() for name in REQUIRED_RESOURCE_DIRS):
            raise RuntimeError("资源包结构不完整，缺少必要资源目录")

        backup_dir = self.cache_dir / "resources.backup"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        try:
            if self.resources_dir.exists():
                self.resources_dir.rename(backup_dir)
            new_resources.rename(self.resources_dir)
            if manifest.exists():
                shutil.copy2(manifest, self.manifest_path)
        except Exception:
            if self.resources_dir.exists():
                shutil.rmtree(self.resources_dir)
            if backup_dir.exists():
                backup_dir.rename(self.resources_dir)
            raise
        finally:
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            shutil.rmtree(extract_dir, ignore_errors=True)

        return self.status()

    def delete(self) -> None:
        if self.resources_dir.exists():
            shutil.rmtree(self.resources_dir)

    def _download(self, target: Path) -> None:
        with urllib.request.urlopen(self.pack_url, timeout=self.timeout) as response:
            with target.open("wb") as output:
                shutil.copyfileobj(response, output)

    def _verify_sha256(self, path: Path) -> None:
        if not self.pack_sha256:
            return
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        actual = digest.hexdigest()
        if actual.lower() != self.pack_sha256.lower():
            raise RuntimeError(f"资源包校验失败: {actual}")

    def _load_manifest(self) -> dict:
        if not self.manifest_path.exists():
            return {}
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _dir_has_images(path: Path) -> bool:
        if not path.is_dir():
            return False
        return any(
            item.is_file() and item.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif"}
            for item in path.rglob("*")
        )


def format_bytes(value: int) -> str:
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"
