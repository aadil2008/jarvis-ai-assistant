from __future__ import annotations

import difflib
import os
import platform
from pathlib import Path
from typing import Iterable


SKIP_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    "Library",
    "node_modules",
    "$RECYCLE.BIN",
}


class Explorer:
    """Small, privacy-friendly index of common user folders."""

    def __init__(self, roots: Iterable[str | Path] | None = None) -> None:
        self.file_index: dict[str, list[Path]] = {}
        self.common_paths = list(roots) if roots is not None else self._default_paths()

    @staticmethod
    def _default_paths() -> list[Path]:
        home = Path.home()
        paths = [home / "Desktop", home / "Documents", home / "Downloads"]

        if platform.system() == "Windows":
            program_data = os.getenv("ProgramData")
            app_data = os.getenv("AppData")
            if program_data:
                paths.append(Path(program_data) / "Microsoft/Windows/Start Menu/Programs")
            if app_data:
                paths.append(Path(app_data) / "Microsoft/Windows/Start Menu/Programs")

        return [path for path in paths if path.exists()]

    def scan_files(self, max_files: int = 50_000) -> int:
        """Index filenames in common folders and return the number indexed."""
        self.file_index.clear()
        indexed = 0
        print("Indexing Desktop, Documents, and Downloads...")

        for start_path in self.common_paths:
            start = Path(start_path).expanduser()
            if not start.exists():
                continue

            for root, directories, files in os.walk(start):
                directories[:] = [
                    name
                    for name in directories
                    if name not in SKIP_DIRECTORIES and not name.startswith(".")
                ]
                for filename in files:
                    if filename.startswith("."):
                        continue
                    path = Path(root) / filename
                    keys = {filename.casefold(), path.stem.casefold()}
                    for key in keys:
                        self.file_index.setdefault(key, []).append(path)
                    indexed += 1
                    if indexed >= max_files:
                        print(f"Stopped after indexing {indexed} files.")
                        return indexed

        print(f"Indexed {indexed} files.")
        return indexed

    def find_files(self, filename: str, limit: int = 5) -> list[Path]:
        query = filename.strip().casefold()
        if not query:
            return []

        exact = self.file_index.get(query)
        if exact:
            return exact[:limit]

        contains: list[Path] = []
        seen: set[Path] = set()
        for key, paths in self.file_index.items():
            if query in key:
                for path in paths:
                    if path not in seen:
                        seen.add(path)
                        contains.append(path)
                        if len(contains) >= limit:
                            return contains

        close_keys = difflib.get_close_matches(query, self.file_index.keys(), n=limit, cutoff=0.72)
        for key in close_keys:
            for path in self.file_index[key]:
                if path not in seen:
                    seen.add(path)
                    contains.append(path)
                    if len(contains) >= limit:
                        return contains
        return contains

    def find_file(self, filename: str) -> str | None:
        matches = self.find_files(filename, limit=1)
        return str(matches[0]) if matches else None


if __name__ == "__main__":
    explorer = Explorer()
    explorer.scan_files()
    print(explorer.find_file(input("File to find: ")))
