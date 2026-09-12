"""Repository Scanner & Topology Extractor for RADULOV.

Parses active repository manifests, file hierarchies, and tech stacks into a
dense, compressed architectural summary.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", ".radulov", "node_modules", "dist", "build", "archive"}


def scan_repository(repo_root: str | Path = ".") -> dict[str, Any]:
    """Scan and extract high-density metadata from the target repository."""
    root = Path(repo_root).resolve()

    manifests: dict[str, Any] = {}
    detected_languages: set[str] = set()
    file_tree_summary: list[str] = []
    total_files = 0
    total_bytes = 0

    # 1. Detect Package & Environment Manifests
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        manifests["pyproject.toml"] = pyproject.read_text(encoding="utf-8", errors="replace")[:2048]
        detected_languages.add("Python")

    package_json = root / "package.json"
    if package_json.is_file():
        try:
            manifests["package.json"] = json.loads(package_json.read_text(encoding="utf-8"))
            detected_languages.add("TypeScript/JavaScript")
        except Exception:
            manifests["package.json"] = "Invalid JSON"

    requirements_txt = root / "requirements.txt"
    if requirements_txt.is_file():
        manifests["requirements.txt"] = requirements_txt.read_text(encoding="utf-8", errors="replace")[:1024]
        detected_languages.add("Python")

    cargo_toml = root / "Cargo.toml"
    if cargo_toml.is_file():
        manifests["Cargo.toml"] = cargo_toml.read_text(encoding="utf-8", errors="replace")[:2048]
        detected_languages.add("Rust")

    go_mod = root / "go.mod"
    if go_mod.is_file():
        manifests["go.mod"] = go_mod.read_text(encoding="utf-8", errors="replace")[:1024]
        detected_languages.add("Go")

    # 2. Walk directory tree (bounded to depth 3)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        rel_dir = Path(dirpath).relative_to(root)
        depth = len(rel_dir.parts)

        if depth > 3:
            continue

        for fname in filenames:
            ext = Path(fname).suffix.lower()
            if ext in {".py", ".pyi"}:
                detected_languages.add("Python")
            elif ext in {".ts", ".tsx"}:
                detected_languages.add("TypeScript")
            elif ext in {".js", ".jsx"}:
                detected_languages.add("JavaScript")
            elif ext in {".rs"}:
                detected_languages.add("Rust")
            elif ext in {".go"}:
                detected_languages.add("Go")
            elif ext in {".html", ".htm"}:
                detected_languages.add("HTML")
            elif ext in {".css", ".scss"}:
                detected_languages.add("CSS")

            p = Path(dirpath) / fname
            try:
                sz = p.stat().st_size
                total_bytes += sz
                total_files += 1
                rel_file = p.relative_to(root).as_posix()
                if total_files <= 50:
                    file_tree_summary.append(f"{rel_file} ({sz} B)")
            except Exception:
                continue

    if total_files > 50:
        file_tree_summary.append(f"... [and {total_files - 50} more files]")

    return {
        "repo_root": str(root),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "detected_languages": sorted(list(detected_languages)),
        "manifests": manifests,
        "file_tree": file_tree_summary,
    }


def format_scan_summary(scan_data: dict[str, Any]) -> str:
    """Format the scan data into a compact context string for LLMs."""
    languages = ", ".join(scan_data.get("detected_languages", [])) or "Unknown"
    files = "\n".join(f"  - {f}" for f in scan_data.get("file_tree", []))

    manifest_blocks = []
    for name, content in scan_data.get("manifests", {}).items():
        if isinstance(content, dict):
            content_str = json.dumps(content, indent=2)
        else:
            content_str = str(content).strip()
        manifest_blocks.append(f"[{name}]\n{content_str}")

    manifest_text = "\n\n".join(manifest_blocks) if manifest_blocks else "(None detected)"

    return (
        f"=== REPOSITORY TOPOLOGY ===\n"
        f"Primary Languages: {languages}\n"
        f"Total Tracked Files: {scan_data.get('total_files', 0)} ({scan_data.get('total_bytes', 0)} bytes)\n\n"
        f"Key Manifests:\n{manifest_text}\n\n"
        f"Active File Tree:\n{files}\n"
        f"==========================="
    )
