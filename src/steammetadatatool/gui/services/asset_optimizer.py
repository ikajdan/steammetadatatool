# SPDX-FileCopyrightText: 2026 Ignacy Kajdan <ignacy.kajdan@gmail.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader

from steammetadatatool.gui.data.app_data import app_data_path

_ASSET_OPTIMIZATION_TARGETS = {
    "capsule": QSize(600, 900),
    "header": QSize(920, 430),
    "hero": QSize(3840, 1240),
    "logo": QSize(1280, 720),
    "icon": QSize(256, 256),
}
_OPTIMIZABLE_ASSET_SUFFIXES = {".jpg", ".jpeg", ".png"}


@dataclass(frozen=True)
class AssetOptimizationChange:
    path: Path
    display_path: Path
    source_size: QSize
    optimized_size: QSize
    source_bytes: int


@dataclass(frozen=True)
class AssetOptimizationResult:
    change: AssetOptimizationChange
    optimized_bytes: int


def _load_image(path: Path) -> QImage:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    return reader.read()


def _optimized_asset_size(source_size: QSize, target_size: QSize) -> QSize:
    if (
        source_size.width() <= target_size.width()
        and source_size.height() <= target_size.height()
    ):
        return source_size

    return source_size.scaled(
        target_size,
        Qt.AspectRatioMode.KeepAspectRatio,
    )


def _optimize_asset_file(path: Path, target_size: QSize) -> bool:
    image = _load_image(path)
    if image.isNull():
        raise ValueError(f"Could not load image: {path}")

    optimized_size = _optimized_asset_size(image.size(), target_size)
    if optimized_size == image.size():
        return False

    optimized = image.scaled(
        optimized_size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if optimized.isNull():
        raise ValueError(f"Could not resize image: {path}")

    temp_path = path.with_name(f".{path.stem}.optimized{path.suffix}")
    if temp_path.exists():
        temp_path.unlink()

    if not optimized.save(str(temp_path)):
        if temp_path.exists():
            temp_path.unlink()
        raise OSError(f"Could not write optimized image: {path}")

    temp_path.replace(path)
    return True


def scan_custom_asset_optimizations() -> tuple[
    list[AssetOptimizationChange], int, list[str]
]:
    assets_root = app_data_path("assets")
    if not assets_root.is_dir():
        return ([], 0, [])

    changes: list[AssetOptimizationChange] = []
    unchanged_count = 0
    errors: list[str] = []

    for app_dir in sorted(path for path in assets_root.iterdir() if path.is_dir()):
        for dirname, target_size in _ASSET_OPTIMIZATION_TARGETS.items():
            asset_dir = app_dir / dirname
            if not asset_dir.is_dir():
                continue

            for path in sorted(asset_dir.iterdir()):
                if (
                    not path.is_file()
                    or path.suffix.lower() not in _OPTIMIZABLE_ASSET_SUFFIXES
                ):
                    continue

                try:
                    source_bytes = path.stat().st_size
                    image = _load_image(path)
                    if image.isNull():
                        raise ValueError(f"Could not load image: {path}")
                except (OSError, ValueError) as exc:
                    errors.append(str(exc))
                    continue

                optimized_size = _optimized_asset_size(image.size(), target_size)
                if optimized_size == image.size():
                    unchanged_count += 1
                else:
                    changes.append(
                        AssetOptimizationChange(
                            path=path,
                            display_path=path.relative_to(assets_root),
                            source_size=image.size(),
                            optimized_size=optimized_size,
                            source_bytes=source_bytes,
                        )
                    )

    return (changes, unchanged_count, errors)


def optimize_custom_assets(
    changes: list[AssetOptimizationChange],
) -> tuple[list[AssetOptimizationResult], list[str]]:
    results: list[AssetOptimizationResult] = []
    errors: list[str] = []
    for change in changes:
        try:
            did_optimize = _optimize_asset_file(change.path, change.optimized_size)
            if did_optimize:
                results.append(
                    AssetOptimizationResult(
                        change=change,
                        optimized_bytes=change.path.stat().st_size,
                    )
                )
        except (OSError, ValueError) as exc:
            errors.append(str(exc))

    return (results, errors)


def _format_byte_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024.0 or unit == "GiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{size} B"
        value /= 1024.0

    return f"{size} B"


def run_asset_optimization_prompt() -> int:
    changes, unchanged_count, scan_errors = scan_custom_asset_optimizations()
    for error in scan_errors:
        print(error, file=sys.stderr)

    if not changes:
        print(
            "No asset optimization changes found: "
            f"{unchanged_count} already within limits."
        )
        return 1 if scan_errors else 0

    print("Asset optimization would make these changes:")
    for change in changes:
        print(
            f"- {change.display_path}: "
            f"{change.source_size.width()}x{change.source_size.height()} -> "
            f"{change.optimized_size.width()}x{change.optimized_size.height()}"
        )

    try:
        response = input("\nProceed and overwrite these source files? [y/N]: ")
    except EOFError:
        response = ""

    if response.strip().casefold() not in {"y", "yes"}:
        print("Asset optimization cancelled.")
        return 1 if scan_errors else 0

    optimize_results, optimize_errors = optimize_custom_assets(changes)
    for error in optimize_errors:
        print(error, file=sys.stderr)

    before_bytes = sum(result.change.source_bytes for result in optimize_results)
    after_bytes = sum(result.optimized_bytes for result in optimize_results)
    delta_bytes = before_bytes - after_bytes
    optimized_count = len(optimize_results)
    print(
        "Asset optimization complete: "
        f"{optimized_count} optimized, {unchanged_count} already within limits."
    )
    if optimize_results:
        print(
            "Optimized asset size: "
            f"{_format_byte_size(before_bytes)} -> "
            f"{_format_byte_size(after_bytes)} "
            f"({_format_byte_size(delta_bytes)} saved)"
        )
    return 1 if scan_errors or optimize_errors else 0
