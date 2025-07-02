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
├── constants.py        # File extension constants, program metadata, and settings
├── conversion.py       # Video format conversion using ffmpeg (VideoConverter class)
├── core.py             # Core photo sorting logic (PhotoSorter class)
├── file_operations.py  # Shared file operations and utilities (FileOperations class)
├── history.py          # Import history management (HistoryManager class)
├── livephoto.py        # Live Photo processing (LivePhotoProcessor class)
└── utils.py            # General utility functions
```

### Core Components
- **`photosort.cli`**: CLI argument parsing and main entry point
- **`photosort.core.PhotoSorter`**: Handles the multi-phase processing workflow
- **`photosort.config.Config`**: Manages YAML configuration and remembers user preferences
- **`photosort.conversion.VideoConverter`**: Automatic video format conversion to H.265/MP4
- **`photosort.file_operations.FileOperations`**: Shared utilities for file operations, duplicate detection, and permissions
- **`photosort.history.HistoryManager`**: Manages import history, logging, and auxiliary file placement
- **`photosort.livephoto.LivePhotoProcessor`**: Specialized Live Photo detection and processing
- **`photosort.constants`**: File extension definitions, program metadata, and configuration constants
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
- **Live Photo detection**: ContentIdentifier matching via exiftool with basename fallback
- **Automatic video conversion**: Legacy formats converted to H.265/MP4 with original archival
- **Clean COPY mode**: Video conversion uses temp directory to avoid source pollution
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
- `PhotoSorter.process_livephoto_pairs()`: Delegates Live Photo processing to LivePhotoProcessor
- `PhotoSorter.process_metadata_files()`: Handles metadata files separately
- `PhotoSorter.get_creation_date()`: Timezone-aware date extraction for photos and videos
- `PhotoSorter._get_video_creation_date()`: JSON-based ffprobe parsing with EST/EDT conversion
- `PhotoSorter._parse_iso8601_to_est()`: ISO 8601 timestamp parsing with timezone conversion
- `PhotoSorter.get_destination_path()`: Generates timestamped destination paths

### File Discovery (`photosort.core`)
- `PhotoSorter.find_source_files()`: Returns 3-tuple of (media_files, metadata_files, livephoto_pairs)
- Delegates Live Photo detection to LivePhotoProcessor
- Separates processing streams for individual files, Live Photo pairs, and metadata

### Live Photo Processing (`photosort.livephoto`)
- `LivePhotoProcessor.detect_livephoto_pairs()`: Main detection orchestrator
- `LivePhotoProcessor._detect_by_content_identifier()`: Primary ContentIdentifier-based detection
- `LivePhotoProcessor._detect_by_basename_fallback()`: Fallback Live Photo detection using filename basenames
- `LivePhotoProcessor._parse_livephoto_date()`: Extracts creation date with millisecond precision
- `LivePhotoProcessor._generate_shared_basename()`: Creates shared basenames for Live Photo pairs
- `LivePhotoProcessor.process_livephoto_pairs()`: Processes detected pairs with shared basenames
- `LivePhotoProcessor._process_livephoto_file()`: Individual file processing with predetermined basename

### History Management (`photosort.history`)
- `HistoryManager.__init__()`: Creates timestamped import folders
- `HistoryManager.setup_import_logger()`: Configures per-import logging
- `HistoryManager.log_import_summary()`: Records import summary to global log with conversion metrics
- `HistoryManager.get_metadata_dir()`: Path for metadata files in history
- `HistoryManager.get_legacy_videos_dir()`: Path for original videos before conversion
- `HistoryManager.get_unsorted_dir()`: Path for problematic files

### File Operations (`photosort.file_operations`)
- `FileOperations.is_duplicate()`: Advanced duplicate detection with size/hash comparison
- `FileOperations.same_size_same_hash()`: SHA-256 hash comparison for same-sized files
- `FileOperations.move_file_safely()`: File movement with validation and permission setting
- `FileOperations.image_creation_date()`: Image metadata extraction using sips with fallback
- `FileOperations.apply_file_permissions()`: Sets file permissions based on mode
- `FileOperations.apply_file_group()`: Sets group ownership based on GID
- `FileOperations.ensure_directory()`: Creates directories safely with dry-run support
- `FileOperations.handle_conversion_cleanup()`: Manages cleanup after video conversion
- `FileOperations.handle_duplicate_cleanup()`: Manages cleanup when duplicates detected
- `FileOperations.cleanup_failed_conversion()`: Cleanup when conversion fails
- `FileOperations.cleanup_failed_move()`: Cleanup when file move fails
- `FileOperations.cleanup_source_directory()`: Post-processing source cleanup
- `FileOperations.normalize_jpg_extension()`: Standardizes JPG file extensions
- `FileOperations.check_tool_availability()`: System tool availability checking

### Video Conversion (`photosort.conversion`)
- `VideoConverter.needs_conversion()`: Detects non-modern codec videos requiring conversion
- `VideoConverter.convert_video()`: H.265/MP4 conversion with libx265, CRF 28, AAC audio
- `VideoConverter.get_video_codec()`: Extract video codec using ffprobe for format detection
- `VideoConverter.get_conversion_info()`: Provides conversion details and size reduction metrics
- **COPY mode behavior**: Uses temp directory for conversion to avoid polluting source
- **MOVE mode behavior**: Converts in source directory for efficiency

### Configuration (`photosort.config`)
- `Config.get_last_source()`: Retrieves saved source directory
- `Config.get_last_dest()`: Retrieves saved destination directory
- `Config.update_paths()`: Saves new source/destination paths
- `Config.update_file_mode()`: Saves file permission preferences
- `Config.update_group()`: Saves group ownership preferences
- `Config.get_convert_videos()`: Retrieves video conversion setting
- `Config.update_convert_videos()`: Saves video conversion preference
- `Config.get_timezone()`: Retrieves saved timezone setting
- `Config.update_timezone()`: Saves timezone preference

### Utilities (`photosort.utils`)
- `cleanup_source_directory()`: Post-processing source cleanup
- Removes empty directories and nuisance files
- Moves unknown files to history directory

### Constants (`photosort.constants`)
- `PROGRAM`: Centralized program name constant for consistent naming
- `PHOTO_EXTENSIONS`: Supported photo file extensions (includes GIF, TIFF formats)
- `MOVIE_EXTENSIONS`: Supported video file extensions
- `MODERN_VIDEO_CODECS`: Video codecs that don't need conversion (h264, h265, av1)
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

## Live Photo Processing (`photosort.livephoto`)

The Live Photo system detects and processes Apple Live Photo pairs (image + video) to ensure they receive identical basenames and timestamps for proper photo management software support. This functionality is implemented in the dedicated `LivePhotoProcessor` class for better code organization and maintainability.

### Architecture
- **Dedicated Module**: Live Photo functionality extracted into `photosort.livephoto` module
- **Processor Integration**: PhotoSorter creates and delegates to LivePhotoProcessor instance
- **Shared Infrastructure**: LivePhotoProcessor uses PhotoSorter's video conversion, FileOperations utilities, and history management
- **Dependency Injection**: All required functions and objects passed to LivePhotoProcessor during initialization

### Detection Methods
1. **Primary: ContentIdentifier Matching**
   - Uses `exiftool` to extract Apple ContentIdentifier metadata from image and video files
   - Groups files with matching ContentIdentifiers as Live Photo pairs
   - Extracts SubSecCreateDate for millisecond precision in shared basenames

2. **Fallback: Basename Matching**
   - When exiftool unavailable, matches files by filename stem (e.g., IMG_1234.heic + IMG_1234.mov)
   - Uses image file creation date for shared timestamp

### Processing Workflow
1. **Detection Phase**: `detect_livephoto_pairs()` identifies pairs and returns remaining individual files
2. **Processing Order**: Live Photo pairs processed first to avoid filename collisions
3. **Shared Basenames**: Both files get identical `YYYYMMDD_HHMMSS_###` basenames with millisecond counters
4. **Individual Processing**: Each file in pair processed with predetermined basename

### Video Conversion in Live Photos
- Live Photo videos are typically modern .mov files that don't need conversion
- If conversion needed, follows same COPY/MOVE mode behavior as individual files
- Preserves Live Photo relationship through shared basename

## Error Handling

- **Dual logging system**: Console shows warnings/errors, import.log captures everything
- **Problematic files**: Moved to history `Unsorted/` directory with error logging
- **Unknown files**: Moved to history `UnknownFiles/` directory during cleanup
- **Metadata files**: Moved to history `Metadata/` directory to keep destinations clean
- **Safe file operations**: Validation with permission and group setting post-move
- **Automatic source cleanup**: Removes empty directories and nuisance files
- **Graceful degradation**: Filesystem dates used if EXIF extraction fails
- **Permission errors**: File/group permission failures logged but don't stop processing

## Video Conversion Modes (`photosort.conversion`)

Video conversion uses a unified tempfile approach for both COPY and MOVE modes to maintain clean source directory handling.

### Unified Conversion Approach
- **Temp Directory Conversion**: All video conversions use system temp directory regardless of mode
- **Source Preservation**: Source directory never gets polluted during conversion process
- **Clean Operation**: Converted video appears in destination, temp files automatically cleaned up
- **Mode-Specific Archival**: Original video handling differs by mode:
  - **COPY Mode**: Original video copied to history `LegacyVideos/` directory
  - **MOVE Mode**: Original video moved to history `LegacyVideos/` directory

### Conversion Process
1. **Codec Detection**: Uses ffprobe to identify non-modern video codecs
2. **Temp File Creation**: Creates temporary converted file using system temp directory
3. **H.265 Encoding**: Converts with libx265, CRF 28 quality, AAC audio
4. **Metadata Preservation**: Maintains creation dates and global metadata
5. **Atomic Move**: Moves converted file from temp to destination
6. **Cleanup**: Archives original and removes temp files
7. **Archival**: Original videos preserved in timestamped history directories

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

### Timezone Configuration
- `--timezone, --tz`: Default timezone for creation time metadata (saves as new default)

### Other Options
- `--verbose, -v`: Enable debug logging to import.log
- `--help`: Shows dynamic help with current configured defaults

## Public API (`photosort.__init__.py`)

The package exports these key classes and functions:
- `photosort.main`: Main CLI entry point function
- `photosort.Config`: Configuration management class
- `photosort.VideoConverter`: Video format conversion class
- `photosort.PhotoSorter`: Core photo sorting class
- `photosort.FileOperations`: Shared file operations and utilities class
- `photosort.HistoryManager`: Import history management class
- `photosort.LivePhotoProcessor`: Live Photo detection and processing class

### Usage Examples

```python
# Direct API usage
from photosort import Config, PhotoSorter
from pathlib import Path

config = Config()
sorter = PhotoSorter(
    source=Path("~/Downloads/Photos"), 
    dest=Path("~/Pictures/Organized"),
    root_dir=config.program_root,
    dry_run=True
)
media_files, metadata_files, livephoto_pairs = sorter.find_source_files()
sorter.process_livephoto_pairs(livephoto_pairs)
sorter.process_files(media_files)
```

## Development Notes

### Module Dependencies
- `cli.py` → `config.py`, `core.py`, `constants.py`
- `core.py` → `constants.py`, `config.py`, `file_operations.py`, `history.py`, `livephoto.py`, `conversion.py`
- `file_operations.py` → `constants.py` (central utility used by multiple modules)
- `livephoto.py` → `constants.py` (with dependency injection from core.py)
- `history.py` → `file_operations.py` (uses FileOperations for directory creation)
- `conversion.py` → `constants.py`, `file_operations.py`
- `config.py` → `constants.py` (only system modules + yaml)
- `utils.py` → `constants.py`, `file_operations.py`
- `constants.py` → standalone (no dependencies)

### Testing Strategy
- **Unit tests**: Each module can be tested independently
- **Integration tests**: CLI functionality and end-to-end workflows
- **Mock testing**: File operations for safe testing without actual file moves

### Extensibility Points
- **New file formats**: Add to `constants.py` extension lists
- **Custom processors**: Subclass `PhotoSorter` or `LivePhotoProcessor` for specialized behavior
- **Alternative storage**: Implement custom `HistoryManager` subclasses
- **File operations**: Extend `FileOperations` for custom file handling behaviors
- **Live Photo enhancements**: Modify `LivePhotoProcessor` for new detection methods or processing logic
- **Plugin system**: Future enhancement for custom processing pipelines
