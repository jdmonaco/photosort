# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Photosort** is a modern Python tool for organizing photo and video collections into a year/month directory structure based on file creation dates. It's packaged as a proper Python tool installable via UV with comprehensive CLI features including file permissions, group ownership, and complete import history tracking.

## Architecture

### Core Components
- **`photosort.py`**: Main script with class-based architecture
- **`PhotoSorter` class**: Handles the multi-phase processing workflow
- **`Config` class**: Manages YAML configuration and remembers user preferences
- **`HistoryManager` class**: Manages import history, logging, and auxiliary file placement
- **Rich UI**: Progress bars, tables, and colored console output

### Key Features
- **Smart path handling**: Uses `pathlib.Path` throughout for cross-platform compatibility
- **Configuration memory**: Stores preferences in `~/.photosort/config.yml`
- **Import history tracking**: Complete audit trail in `~/.photosort/history/`
- **Dynamic CLI help**: Shows current configured defaults in help text
- **Safe operations**: Move files with validation, automatic source cleanup
- **File permissions control**: Configurable file mode settings (e.g., 644, 600)
- **Group ownership**: Configurable group ownership for files and directories
- **Clean destinations**: Auxiliary files moved to timestamped history folders
- **Simplified organization**: No movies subfolder - all media in same date folders
- **Metadata separation**: Handles .aae and other metadata files separately
- **Advanced deduplication**: Size comparison + optional content hashing for smaller files
- **macOS optimized**: Uses `sips` command for accurate photo metadata extraction

## Package Management

- **UV-compatible**: Defined in `pyproject.toml` with proper dependencies
- **Tool installation**: `uv tool install .` creates isolated environment
- **Dependencies**: `rich` (UI), `pyyaml` (config)
- **Entry point**: `photosort` command runs `photosort:main`

## Development Commands

```bash
# Install in development mode
uv sync

# Run from source
uv run photosort --help

# Install as tool
uv tool install .

# Run tests (when added)
uv run pytest

# Code formatting
uv run black photosort.py

# Type checking
uv run mypy photosort.py
```

## File Organization

### Destination Structure
Output structure: `YYYY/MM/YYYY-MM-DD_HH-MM-SS.ext`
- All media (photos and videos) go directly in month folders for better Live Photo support
- Clean destination folders contain only organized media files

### History Structure (`~/.photosort/`)
```
~/.photosort/
├── config.yml                    # Configuration with saved preferences
├── imports.log                   # Global import log with summary records
└── history/                      # Per-import history folders
    └── YYYY-MM-DD+DEST-NAME/     # Timestamped import sessions
        ├── import.log            # Detailed logs for this import
        ├── Metadata/             # .aae, .xml, .json metadata files
        ├── UnknownFiles/         # Unrecognized file types
        └── Unsorted/             # Problem files that couldn't be processed
```
- Source directory is automatically cleaned when moving files
- All auxiliary files preserved in searchable history

## Key Functions

### Core Processing
- `PhotoSorter.process_files()`: Main media file processing with progress tracking
- `PhotoSorter.process_metadata_files()`: Handles metadata files separately
- `cleanup_source_directory()`: Module function for post-processing source cleanup
- `set_directory_groups()`: Applies group ownership to destination directories

### File Discovery
- `find_source_files()`: Returns tuple of (media_files, metadata_files)
- Separates processing streams for different file types

### History Management
- `HistoryManager.__init__()`: Creates timestamped import folders
- `HistoryManager.setup_import_logger()`: Configures per-import logging
- `HistoryManager.log_import_summary()`: Records import summary to global log

### File Permissions
- `parse_file_mode()`: Validates and converts octal mode strings
- `parse_group()`: Validates group names against system groups
- `PhotoSorter._apply_file_permissions()`: Sets file permissions post-move
- `PhotoSorter._apply_file_group()`: Sets file group ownership post-move

## Configuration System

The `Config` class manages `~/.photosort/config.yml`:
- Remembers last source/destination paths, file mode, and group preferences
- Updates automatically when user specifies new values
- CLI help shows current configured defaults
- Graceful fallback if config is missing/corrupted
- Config migration from old `~/.config/photosort/` location

## Error Handling

- **Dual logging system**: Console shows warnings/errors, import.log captures everything
- **Problematic files**: Moved to history `Unsorted/` directory with error logging
- **Unknown files**: Moved to history `UnknownFiles/` directory during cleanup
- **Metadata files**: Moved to history `Metadata/` directory to keep destinations clean
- **Safe file operations**: Validation with permission and group setting post-move
- **Automatic source cleanup**: Removes empty directories and nuisance files
- **Graceful degradation**: Filesystem dates used if EXIF extraction fails
- **Permission errors**: File/group permission failures logged but don't stop processing

## CLI Arguments

### File Management
- `--source, -s`: Source directory (shows configured default)
- `--dest, -d`: Destination directory (shows configured default)
- `--copy, -c`: Copy instead of move files
- `--dry-run, -n`: Preview without making changes

### File Ownership
- `--mode, -m`: File permissions in octal (e.g., 644, 600) - saves as new default
- `--group, -g`: Group ownership (e.g., staff, wheel) - saves as new default

### Other Options
- `--verbose, -v`: Enable debug logging to import.log
- `--help`: Shows dynamic help with current configured defaults
