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
├── constants.py        # File extension constants, program metadata, centralized logger, and shared utilities
├── conversion.py       # Video format conversion using ffmpeg (VideoConverter class, ConversionResult)
├── core.py             # Core photo sorting logic (PhotoSorter class)
├── file_operations.py  # Shared file operations and utilities (FileOperations class)
├── history.py          # Import history management (HistoryManager class)
├── livephoto.py        # Live Photo processing (LivePhotoProcessor class)
├── progress.py         # Progress tracking encapsulation (ProgressContext class)
├── stats.py            # Statistics tracking and management (StatsManager class)
└── timestamps.py       # Centralized date/time parsing and timezone handling
```

### Core Components
- **`photosort.cli`**: CLI argument parsing and main entry point
- **`photosort.core.PhotoSorter`**: Handles the multi-phase processing workflow
- **`photosort.config.Config`**: Manages YAML configuration and remembers user preferences
- **`photosort.conversion.VideoConverter`**: Automatic video format conversion to H.265/MP4 with encapsulated config
- **`photosort.conversion.ConversionResult`**: Dataclass for video conversion results with cleanup handling
- **`photosort.file_operations.FileOperations`**: Shared utilities for file operations, duplicate detection, and permissions
- **`photosort.history.HistoryManager`**: Manages import history, logging, and auxiliary file placement
- **`photosort.livephoto.LivePhotoProcessor`**: Specialized Live Photo detection and processing
- **`photosort.progress.ProgressContext`**: Unified progress tracking for all operations
- **`photosort.stats.StatsManager`**: Centralized statistics tracking and management
- **`photosort.constants`**: File extension definitions, program metadata, centralized logger utility, and shared functions
- **`photosort.timestamps`**: Centralized date/time parsing, timezone conversion, and EXIF metadata extraction
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
- **macOS optimized**: Uses `exiftool` and `sips` for photos, `ffprobe` for accurate video metadata extraction
- **Streamlined architecture**: Encapsulated progress tracking, statistics, and configuration management
- **Unified progress tracking**: Single progress bar for all operations with consistent updates

## Package Management

- **UV-compatible**: Defined in `pyproject.toml` with proper dependencies
- **Tool installation**: `uv tool install .` creates isolated environment (add `--editable` for development)
- **Dependencies**: `rich` (UI), `pyyaml` (config)
- **Entry point**: `photosort` command runs `photosort.cli:main`

## Development Commands

```bash
# Install in development mode
uv sync

# Run from source (if photosort is available on PATH)
photosort --help

# Run from source via uv (if photosort not available on PATH)
uv tool run photosort --help

# Install as tool
uv tool install --editable .

# Run tests
uv run pytest

# Run specific test module
uv run pytest tests/test_basic_operations.py -v

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
- `PhotoSorter.get_creation_date()`: Timezone-aware date extraction delegating to timestamps module
- `PhotoSorter.get_destination_path()`: Generates timestamped destination paths

### File Discovery (`photosort.core`)
- `PhotoSorter.find_source_files()`: Returns 3-tuple of (media_files, metadata_files, livephoto_pairs)
- Delegates Live Photo detection to LivePhotoProcessor
- Separates processing streams for individual files, Live Photo pairs, and metadata

### Live Photo Processing (`photosort.livephoto`)
- `LivePhotoProcessor.detect_livephoto_pairs()`: Main detection orchestrator
- `LivePhotoProcessor._detect_by_content_identifier()`: Primary ContentIdentifier-based detection
- `LivePhotoProcessor._detect_by_basename_fallback()`: Fallback Live Photo detection using filename basenames
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
- `FileOperations.apply_file_permissions()`: Sets file permissions based on mode
- `FileOperations.apply_file_group()`: Sets group ownership based on GID
- `FileOperations.ensure_directory()`: Creates directories safely with dry-run support
- `FileOperations.archive_file()`: Generic archival method with path preservation options
- `FileOperations.create_unique_path()`: Generates unique file paths with counter if needed
- `FileOperations.delete_safely()`: Safe file deletion supporting multiple files via *args
- `FileOperations.cleanup_source_directory()`: Post-processing source cleanup
- `FileOperations.normalize_jpg_extension()`: Standardizes JPG file extensions

### Video Conversion (`photosort.conversion`)
- `VideoConverter._needs_conversion()`: Detects non-modern codec videos requiring conversion (private method)
- `VideoConverter.convert_video()`: H.265/MP4 conversion with libx265, CRF 26, AAC audio
- `VideoConverter.get_video_codec()`: Extract video codec using ffprobe for format detection
- `VideoConverter.get_content_identifier()`: Extract Apple ContentIdentifier tag using ffprobe
- `VideoConverter._content_id_preserved()`: Verify ContentIdentifier metadata preservation after conversion
- `VideoConverter.handle_video_conversion()`: Unified conversion workflow returning ConversionResult
- **Encapsulated configuration**: VideoConverter handles convert_videos setting internally
- **Unified conversion approach**: All conversions use temp directory regardless of mode

### Configuration (`photosort.config`)
- `Config.get_last_source()`: Retrieves saved source directory
- `Config.get_last_dest()`: Retrieves saved destination directory
- `Config.update_paths()`: Saves new source/destination paths
- `Config.update_file_mode()`: Saves file permission preferences
- `Config.update_group()`: Saves group ownership preferences
- `Config.get_timezone()`: Retrieves saved timezone setting
- `Config.update_timezone()`: Saves timezone preference

### Constants (`photosort.constants`)
- `PROGRAM`: Centralized program name constant for consistent naming
- `PHOTO_EXTENSIONS`: Supported photo file extensions (includes GIF, TIFF formats)
- `MOVIE_EXTENSIONS`: Supported video file extensions
- `MODERN_VIDEO_CODECS`: Video codecs that don't need conversion (hevc, h265, h264, avc, av1, vp9)
- `METADATA_EXTENSIONS`: Metadata file extensions
- `NUISANCE_EXTENSIONS`: System files to remove during cleanup
- `get_logger()`: Centralized logger utility for consistent logging across modules
- `get_console()`: Shared Rich Console instance for consistent UI across modules
- `check_tool_availability()`: System tool availability checking utility
- **Tool availability constants**: `ffmpeg_available`, `ffprobe_available`, `exiftool_available`, `sips_available`

### Date/Time Processing (`photosort.timestamps`)
- `get_image_creation_date()`: Extract creation date from images using exiftool, sips, or file stat
- `get_video_creation_date()`: Extract creation date from video metadata with Apple QuickTime priority
- `canonical_EXIF_date()`: Parse EXIF image creation date with millisecond precision and priority handling
- `parse_iso8601_datetime()`: Parse ISO 8601 date-time strings with timezone awareness and conversion
- **Centralized timezone handling**: Module-level timezone configuration with fallback to "America/New_York"
- **Performance optimization**: Batch EXIF processing for improved speed

### Progress Tracking (`photosort.progress`)
- `ProgressContext.update()`: Update progress description if tracking is active
- `ProgressContext.advance()`: Advance progress by given number of steps
- `ProgressContext.is_active`: Check if progress tracking is active
- **Unified progress tracking**: Single progress context shared across all operations

### Statistics Management (`photosort.stats`)
- `StatsManager.record_successful_file()`: Record successfully processed files with size tracking
- `StatsManager.increment_photos()`: Increment photo count
- `StatsManager.increment_videos()`: Increment video count
- `StatsManager.increment_metadata()`: Increment metadata file count
- `StatsManager.increment_duplicates()`: Increment duplicate file count
- `StatsManager.increment_unsorted()`: Increment unsorted file count
- `StatsManager.increment_converted_videos()`: Increment converted video count
- `StatsManager.increment_livephoto_pairs()`: Increment Live Photo pair count
- **Centralized statistics**: All stats operations encapsulated in single manager class

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
- **Shared Infrastructure**: LivePhotoProcessor uses shared VideoConverter, FileOperations, and StatsManager instances
- **Streamlined Dependencies**: Simplified constructor with 5 core dependencies (down from 11 parameters)

### Detection Methods
1. **Primary: ContentIdentifier Matching**
   - Uses `exiftool` to extract Apple ContentIdentifier metadata from image and video files
   - Groups files with matching ContentIdentifiers as Live Photo pairs
   - Extracts SubSecCreateDate for millisecond precision in shared basenames
   - **Batch Processing**: Processes files in batches of 100 to reduce subprocess overhead (10-15x speedup)
   - **Progress Tracking**: Shows dedicated progress bar during EXIF scanning phase

2. **Fallback: Basename Matching**
   - When exiftool unavailable, matches files by filename stem (e.g., IMG_1234.heic + IMG_1234.mov)
   - Uses image file creation date for shared timestamp

### Performance Optimizations
- **Batch EXIF Processing**: Groups 100 files per exiftool subprocess call for dramatic speedup
- **Duplicate Prevention**: Uses `set()` internally to prevent duplicate file processing
- **Progress Feedback**: Separate progress bar for Live Photo detection phase
- **Deterministic Processing**: Files processed in sorted order for consistent behavior

### Processing Workflow
1. **Detection Phase**: `detect_livephoto_pairs()` identifies pairs and returns remaining individual files
2. **Processing Order**: Live Photo pairs processed first (sorted by image filename) to avoid filename collisions
3. **Shared Basenames**: Both files get identical `YYYYMMDD_HHMMSS_###` basenames with millisecond counters
4. **Individual Processing**: Each file in pair processed with predetermined basename

### Duplicate Handling
- **ContentIdentifier Collision**: When multiple files have same ContentIdentifier (edited versions), system prevents duplicate processing
- **Set-Based Deduplication**: Prevents files from being processed multiple times using internal sets
- **Graceful Skipping**: Files already processed are skipped silently during individual file processing

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
3. **H.265 Encoding**: Converts with libx265, CRF 26 quality, AAC audio
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
- `--no-convert-videos`: Disable automatic conversion of legacy video formats to H.265/MP4 (per-run flag, not persistent)

### Timezone Configuration
- `--timezone, --tz`: Default timezone for creation time metadata (saves as new default)

### Safety and Confirmation
- `--yes, -y`: Auto-confirm processing when using saved source/dest paths (bypasses confirmation prompt)

### Other Options
- `--verbose, -v`: Enable debug logging to import.log
- `--help`: Shows dynamic help with current configured defaults

## CLI Behavior and Safety Features

### Processing Plan Display
Photosort always displays a comprehensive Processing Plan before execution, showing:
- Source and destination paths
- Processing mode (MOVE, COPY, or DRY RUN)
- Video conversion setting
- Timezone setting
- File mode and group ownership (if configured)

Example Processing Plan:
```
Processing Plan:
  Source:          /Users/dev/Downloads/Photos
  Destination:     /Users/dev/Pictures/Organized
  Processing Mode: MOVE
  Convert Videos:  Yes
  Timezone:        America/New_York
  File Mode:       644
  Group:           staff
```

### Confirmation Prompt for Saved Configuration
When photosort is run with no arguments (using saved source/destination paths), it displays a confirmation prompt:

```
Confirm processing plan with saved configuration.
Continue? [y/N]: 
```

This safety feature prevents accidental processing with forgotten or outdated saved configuration.

#### Bypassing Confirmation
- Use `--yes` or `-y` flag to automatically confirm and skip the prompt
- Explicit source/destination arguments never trigger confirmation
- Useful for automation and scripting

#### Examples
```bash
# Shows confirmation prompt
$ photosort

# Bypasses confirmation
$ photosort --yes

# No confirmation needed (explicit paths)
$ photosort ~/Downloads ~/Pictures
```

## Public API (`photosort.__init__.py`)

The package exports these key classes and functions:
- `photosort.main`: Main CLI entry point function
- `photosort.Config`: Configuration management class
- `photosort.VideoConverter`: Video format conversion class
- `photosort.PhotoSorter`: Core photo sorting class
- `photosort.FileOperations`: Shared file operations and utilities class
- `photosort.HistoryManager`: Import history management class
- `photosort.LivePhotoProcessor`: Live Photo detection and processing class
- `photosort.StatsManager`: Statistics tracking and management class
- `photosort.ProgressContext`: Progress tracking encapsulation class
- `photosort.ConversionResult`: Video conversion result dataclass
- **New modules**: `photosort.timestamps` with date/time parsing functions and `photosort.constants` with shared utilities

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
- `cli.py` → `config.py`, `core.py`, `constants.py`, `progress.py`
- `core.py` → `constants.py`, `config.py`, `file_operations.py`, `history.py`, `livephoto.py`, `conversion.py`, `progress.py`, `stats.py`, `timestamps.py`
- `timestamps.py` → `constants.py`, `config.py` (centralized date/time parsing with timezone handling)
- `file_operations.py` → `constants.py` (central utility used by multiple modules)
- `livephoto.py` → `constants.py`, `conversion.py`, `progress.py`, `timestamps.py` (with streamlined dependency injection)
- `history.py` → `file_operations.py` (uses FileOperations for directory creation)
- `conversion.py` → `constants.py`, `file_operations.py`, `progress.py`
- `config.py` → `constants.py` (only system modules + yaml)
- `progress.py` → standalone (no dependencies)
- `stats.py` → `constants.py`
- `constants.py` → standalone (shared utilities and tool availability constants)

## Test Suite Implementation

The photosort project includes a comprehensive pytest-based test suite that conducts end-to-end command-line-driven tests of all distinct behavior paths configurable through CLI options.

### Test Architecture
- **Real Media Testing**: Tests use real media files with actual EXIF metadata for authentic behavior
- **Test Isolation**: Each test uses a separate temporary config directory to avoid interference
- **CLI Integration**: Tests simulate actual command-line usage through subprocess-style execution
- **Comprehensive Coverage**: 61 tests across 6 modules covering all major functionality

### Test Structure
```
tests/
├── conftest.py                     # Core fixtures and test infrastructure
├── create_test_media.py           # Script for generating test media directory
├── test_basic_operations.py       # Move/copy/dry-run modes and validation (9 tests)
├── test_configuration.py          # Config persistence and defaults (15 tests)
├── test_file_organization.py      # Date structure and file handling (8 tests)
├── test_livephoto_processing.py   # Live Photo detection and processing (8 tests)
├── test_video_conversion.py       # H.265 conversion and archival (9 tests)
└── test_file_permissions.py       # File mode and group ownership (12 tests)
```

### Test Infrastructure
- **`conftest.py`**: Core pytest fixtures including `cli_runner`, `temp_source_folder`, `mock_external_tools`
- **`create_test_media.py`**: Comprehensive script for curating diverse test media from developer collections
- **CLI Test Support**: Modified `photosort.cli.main()` accepts optional `config_path` parameter for test isolation
- **Mock Strategy**: External tools (exiftool, ffmpeg) can be mocked for testing with/without dependencies

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test module
uv run pytest tests/test_basic_operations.py -v

# Run with verbose output
uv run pytest -v

# Run specific test
uv run pytest tests/test_configuration.py::TestConfiguration::test_path_persistence -v
```

### Test Media Requirements
Tests require an `example_media/` directory with real media files containing actual EXIF metadata. Use the provided script to create test media:

```bash
# Create test media from your photo collection
uv run python tests/create_test_media.py
```

The script will scan your media files and create a curated test directory with diverse file types, Live Photos, and metadata files.

### Test Coverage by Module

1. **Basic Operations** (`test_basic_operations.py`)
   - Move/copy/dry-run mode functionality
   - Source/destination validation
   - Argument parsing and flag combinations
   - Empty source directory handling

2. **Configuration** (`test_configuration.py`)
   - Configuration file creation and persistence
   - Path memory and defaults in help text
   - File mode and group ownership settings
   - Config validation and corruption handling

3. **File Organization** (`test_file_organization.py`)
   - Date-based directory structure creation
   - Filename format and timestamp generation
   - Duplicate detection and handling
   - Metadata file separation and source cleanup

4. **Live Photo Processing** (`test_livephoto_processing.py`)
   - Live Photo pair detection (with/without exiftool)
   - Shared basename generation for pairs
   - Processing order and collision avoidance
   - Incomplete pair handling

5. **Video Conversion** (`test_video_conversion.py`)
   - Legacy video codec detection and conversion
   - H.265/MP4 encoding with quality settings
   - Original video archival in history directories
   - Copy vs. move mode handling for conversions

6. **File Permissions** (`test_file_permissions.py`)
   - Custom file mode application (644, 600, 755, etc.)
   - Group ownership setting and validation
   - Directory permission inheritance
   - Permission persistence in configuration

### Test Design Considerations

- **Real vs. Mock Files**: Tests using `create_test_files` fixture create simple mock files without metadata, suitable for testing basic file operations. Tests using `temp_source_folder` use real media files with EXIF data for Live Photo detection and metadata extraction.

- **Live Photo Testing**: Live Photo detection requires real ContentIdentifier EXIF metadata. Mock files without this metadata will be processed as individual files, which is expected behavior.

- **External Tool Dependencies**: Tests can mock external tools (exiftool, ffmpeg, sips) to test behavior with/without these dependencies.

- **Exit Code Philosophy**: Photosort returns exit code 0 for successful processing, even when files are moved to "Unsorted" directory. Exit code 1 is reserved for unexpected errors only.

- **Configuration Persistence**: Most settings (paths, file mode, group, timezone) persist in config file, but `--no-convert-videos` is a per-run flag that doesn't persist.

### Testing Strategy
- **Unit tests**: Each module can be tested independently
- **Integration tests**: CLI functionality and end-to-end workflows
- **Mock testing**: File operations for safe testing without actual file moves
- **Real media testing**: Uses actual EXIF metadata for authentic Live Photo and date extraction testing

### Extensibility Points
- **New file formats**: Add to `constants.py` extension lists
- **Custom processors**: Subclass `PhotoSorter` or `LivePhotoProcessor` for specialized behavior
- **Alternative storage**: Implement custom `HistoryManager` subclasses
- **File operations**: Extend `FileOperations` for custom file handling behaviors
- **Live Photo enhancements**: Modify `LivePhotoProcessor` for new detection methods or processing logic
- **Statistics extensions**: Extend `StatsManager` for additional metrics tracking
- **Progress customization**: Extend `ProgressContext` for specialized progress tracking
- **Plugin system**: Future enhancement for custom processing pipelines

### Recent Architectural Improvements (2024)
The codebase has undergone significant refactoring to improve modularity, reduce duplication, and enhance maintainability:

#### **Timestamp Processing Extraction**
1. **New `timestamps.py` Module**: Created dedicated module for all date/time parsing functionality
   - Moved `get_image_creation_date()` and `get_video_creation_date()` from other modules
   - Consolidated EXIF parsing with new `canonical_EXIF_date()` function
   - Centralized ISO 8601 parsing with `parse_iso8601_datetime()`
   - Module-level timezone configuration with proper fallback handling

#### **Shared Utilities Consolidation**
2. **Enhanced `constants.py` Module**: Centralized shared utilities and tool availability
   - Added `get_console()` function for shared Rich Console instance (removed separate `console.py`)
   - Added `check_tool_availability()` moved from `FileOperations` class
   - Module-level tool availability constants for performance optimization
   - Eliminated redundant tool checking across modules

#### **Class and Method Refinements**
3. **FileOperations Simplification**: Removed timestamp-related methods moved to `timestamps.py`
4. **VideoConverter Enhancements**: Added ContentIdentifier preservation verification methods
5. **Core Processing Streamlining**: Simplified by delegating timestamp extraction to dedicated module
6. **LivePhotoProcessor Updates**: Uses centralized EXIF parsing from `timestamps.py`

#### **Performance and Maintainability**
7. **Progress Tracking Consolidation**: Unified `ProgressContext` class for consistent progress handling
8. **Statistics Encapsulation**: `StatsManager` class centralizes all metrics tracking
9. **Tool Availability Optimization**: Check external tools once at module load time vs. repeatedly
10. **Dependency Reduction**: Cleaner module boundaries with reduced inter-module dependencies

These improvements reduced code duplication by approximately 186 lines while enhancing modularity, performance, and maintainability. The extraction of timestamp processing into a dedicated module significantly improves code organization and testability.
