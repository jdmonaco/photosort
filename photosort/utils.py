"""
Utility functions for photosort.
"""

import os
import shutil
from pathlib import Path

from rich.console import Console

from .constants import NUISANCE_EXTENSIONS
from .history import HistoryManager


def cleanup_source_directory(source: Path, history_manager: HistoryManager, console: Console) -> None:
    """Clean up source directory by removing empty folders and moving unknown files."""
    if not any(source.iterdir()):
        return
    
    console.print("Cleaning source folder...")
    
    # First, remove all nuisance files recursively
    nuisance_count = 0
    for file_path in source.rglob("*"):
        if file_path.is_file() and file_path.name.lower() in NUISANCE_EXTENSIONS:
            try:
                file_path.unlink()
                nuisance_count += 1
            except Exception as e:
                console.print(f"[yellow]Warning: Could not remove {file_path}: {e}[/yellow]")
    
    if nuisance_count > 0:
        console.print(f"Removed {nuisance_count} nuisance files (.DS_Store, etc.)")
    
    # Recursively prune empty subfolders from the source tree
    for thisdir, subdirs, _ in os.walk(source, topdown=False):
        for thissubdir in subdirs:
            try:
                os.rmdir(Path(thisdir) / thissubdir)
            except OSError:
                pass

    # Move remaining unknown files to history folder
    unknowns = list(source.glob("*"))
    if unknowns:
        console.print(f"Moving {len(unknowns)} unknown files...")
        unkpath = history_manager.get_unknown_files_dir()
        unkpath.mkdir(parents=True, exist_ok=True)
        for remaining in unknowns:
            shutil.move(remaining, unkpath / remaining.name)