# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Photosort** is a modern Python tool for organizing photo and video collections into a year/month directory structure based on file creation dates. It's packaged as a proper Python tool installable via UV with comprehensive CLI features including file permissions, group ownership, and complete import history tracking.

## Architecture

### Package Structure (Multi-Module)
Photosort is organized as a Python package with clear separation of concerns:

```
photosort/
├── __init__.py          # Package init with public API
├── cli.py              # Command-line interface and main entry point
├── config.py           # Configuration management (Config class)
├── constants.py        # File extension constants and settings
├── conversion.py       # Video format conversion using ffmpeg (VideoConverter class)
├── core.py             # Core photo sorting logic (PhotoSorter class)
├── history.py          # Import history management (HistoryManager class)
├── permissions.py      # File permissions and group ownership utilities
└── utils.py            # General utility functions
```

### Core Components
- **`photosort.cli`**: CLI argument parsing and main entry point
- **`photosort.core.PhotoSorter`**: Handles the multi-phase processing workflow
- **`photosort.config.Config`**: Manages YAML configuration and remembers user preferences
- **`photosort.conversion.VideoConverter`**: Automatic video format conversion to H.265/MP4
- **`photosort.history.HistoryManager`**: Manages import history, logging, and auxiliary file placement
- **`photosort.constants`**: File extension definitions and configuration constants
- **`photosort.permissions`**: File mode and group ownership utilities
- **`photosort.utils`**: Source directory cleanup and general utilities
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
- **Automatic video conversion**: Legacy formats converted to H.265/MP4 with original archival
- **Timezone-aware video dates**: EST/EDT conversion with Live Photo compatibility
- **macOS optimized**: Uses `sips` for photos, `ffprobe` for accurate video metadata extraction

## Package Management

- **UV-compatible**: Defined in `pyproject.toml` with proper dependencies
- **Tool installation**: `uv tool install .` creates isolated environment
- **Dependencies**: `rich` (UI), `pyyaml` (config)
- **Entry point**: `photosort` command runs `photosort.cli:main`

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
uv run black photosort/

# Type checking
uv run mypy photosort/
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
        ├── LegacyVideos/         # Original videos before H.265/MP4 conversion
        ├── Metadata/             # .aae, .xml, .json metadata files
        ├── UnknownFiles/         # Unrecognized file types
        └── Unsorted/             # Problem files that couldn't be processed
```
- Source directory is automatically cleaned when moving files
- All auxiliary files preserved in searchable history

## Key Functions by Module

### Core Processing (`photosort.core`)
- `PhotoSorter.process_files()`: Main media file processing with progress tracking
- `PhotoSorter.process_metadata_files()`: Handles metadata files separately
- `PhotoSorter.get_creation_date()`: Timezone-aware date extraction for photos and videos
- `PhotoSorter._get_video_creation_date()`: JSON-based ffprobe parsing with EST/EDT conversion
- `PhotoSorter._parse_iso8601_to_est()`: ISO 8601 timestamp parsing with timezone conversion
- `PhotoSorter.is_duplicate()`: Advanced duplicate detection with size/hash comparison
- `PhotoSorter.get_destination_path()`: Generates timestamped destination paths

### File Discovery (`photosort.core`)
- `PhotoSorter.find_source_files()`: Returns tuple of (media_files, metadata_files)
- Separates processing streams for different file types

### History Management (`photosort.history`)
- `HistoryManager.__init__()`: Creates timestamped import folders
- `HistoryManager.setup_import_logger()`: Configures per-import logging
- `HistoryManager.log_import_summary()`: Records import summary to global log with conversion metrics
- `HistoryManager.get_metadata_dir()`: Path for metadata files in history
- `HistoryManager.get_legacy_videos_dir()`: Path for original videos before conversion
- `HistoryManager.get_unsorted_dir()`: Path for problematic files

### File Permissions (`photosort.permissions`)
- `parse_file_mode()`: Validates and converts octal mode strings
- `parse_group()`: Validates group names against system groups
- `set_directory_groups()`: Applies group ownership to destination directories
- `get_system_default_mode()`: Gets system default file mode from umask

### Video Conversion (`photosort.conversion`)
- `VideoConverter.needs_conversion()`: Detects non-modern codec videos requiring conversion
- `VideoConverter.convert_video()`: H.265/MP4 conversion with libx265, CRF 28, AAC audio
- `VideoConverter.get_video_codec()`: Extract video codec using ffprobe for format detection
- `VideoConverter.get_conversion_info()`: Provides conversion details and size reduction metrics

### Configuration (`photosort.config`)
- `Config.get_last_source()`: Retrieves saved source directory
- `Config.get_last_dest()`: Retrieves saved destination directory
- `Config.update_paths()`: Saves new source/destination paths
- `Config.update_file_mode()`: Saves file permission preferences
- `Config.update_group()`: Saves group ownership preferences
- `Config.get_convert_videos()`: Retrieves video conversion setting
- `Config.update_convert_videos()`: Saves video conversion preference

### Utilities (`photosort.utils`)
- `cleanup_source_directory()`: Post-processing source cleanup
- Removes empty directories and nuisance files
- Moves unknown files to history directory

### Constants (`photosort.constants`)
- `PHOTO_EXTENSIONS`: Supported photo file extensions
- `MOVIE_EXTENSIONS`: Supported video file extensions
- `METADATA_EXTENSIONS`: Metadata file extensions
- `NUISANCE_EXTENSIONS`: System files to remove during cleanup

## Configuration System (`photosort.config`)

The `Config` class manages `~/.photosort/config.yml`:
- **Path memory**: Remembers last source/destination paths automatically
- **Permission preferences**: Stores file mode (e.g., 644) and group ownership settings
- **Dynamic CLI help**: Shows current configured defaults in help text
- **Auto-update**: Configuration updates when user specifies new values
- **Graceful fallback**: Handles missing/corrupted config files without errors
- **YAML format**: Human-readable configuration file format

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

### Video Conversion
- `--no-convert-videos`: Disable automatic conversion of legacy video formats to H.265/MP4

### Other Options
- `--verbose, -v`: Enable debug logging to import.log
- `--help`: Shows dynamic help with current configured defaults

## Public API (`photosort.__init__.py`)

The package exports these key classes and functions:
- `photosort.main`: Main CLI entry point function
- `photosort.Config`: Configuration management class
- `photosort.VideoConverter`: Video format conversion class
- `photosort.PhotoSorter`: Core photo sorting class
- `photosort.HistoryManager`: Import history management class

### Usage Examples

```python
# Direct API usage
from photosort import Config, PhotoSorter
from pathlib import Path

config = Config()
sorter = PhotoSorter(
    source=Path("~/Downloads/Photos"), 
    dest=Path("~/Pictures/Organized"),
    dry_run=True
)
media_files, metadata_files = sorter.find_source_files()
sorter.process_files(media_files)
```

## Development Notes

### Module Dependencies
- `cli.py` → `config.py`, `core.py`, `permissions.py`, `utils.py`
- `core.py` → `constants.py`, `history.py` 
- `utils.py` → `constants.py`, `history.py`
- `permissions.py` → standalone (only system modules)
- `config.py` → standalone (only system modules + yaml)
- `history.py` → standalone (only system modules)
- `constants.py` → standalone (no dependencies)

### Testing Strategy
- **Unit tests**: Each module can be tested independently
- **Integration tests**: CLI functionality and end-to-end workflows
- **Mock testing**: File operations for safe testing without actual file moves

### Extensibility Points
- **New file formats**: Add to `constants.py` extension lists
- **Custom processors**: Subclass `PhotoSorter` for specialized behavior
- **Alternative storage**: Implement custom `HistoryManager` subclasses
- **Plugin system**: Future enhancement for custom processing pipelines
