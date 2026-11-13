"""PEP 517 adapter for MMC's canonical stdlib-only wheel builder.

The public source installation path and the release builder intentionally emit
the same wheel bytes.  This backend performs no dependency acquisition and has
no publication or installation authority.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

from tools_t7.package import build_wheel as _build_wheel


DIST_INFO = "mosaic_migration_compiler-0.1.0a9.dist-info"
WHEEL_NAME = "mosaic_migration_compiler-0.1.0a9-py3-none-any.whl"


def get_requires_for_build_wheel(config_settings=None) -> list[str]:
    return []


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None) -> str:
    destination = Path(metadata_directory) / DIST_INFO
    destination.mkdir(parents=True, exist_ok=False)
    wheel = _build_wheel()
    with zipfile.ZipFile(BytesIO(wheel)) as archive:
        prefix = DIST_INFO + "/"
        for name in archive.namelist():
            if name.startswith(prefix) and name != prefix + "RECORD":
                relative = name[len(prefix):]
                if relative:
                    target = destination / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(name))
    return DIST_INFO


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None) -> str:
    destination = Path(wheel_directory) / WHEEL_NAME
    destination.write_bytes(_build_wheel())
    return WHEEL_NAME
