# Photosort

A modern Python tool for organizing photos and videos into a clean year/month folder structure based on creation dates, with comprehensive file ownership control and complete import history tracking.

## Features

### Core Organization
- **Smart Organization**: Automatically sorts photos and videos by creation date into `YYYY/MM/` folders
- **Live Photo Detection**: Detects Apple Live Photo pairs using ContentIdentifier matching with basename fallback
- **Live Photo Processing**: Ensures paired files get identical basenames with millisecond precision
- **Multiple Media Types**: Supports photos (JPG, RAW formats), videos, and handles metadata files separately
- **Clean Destinations**: Only organized media in destination folders - auxiliary files moved to history
- **Auto Source Cleanup**: Automatically cleans and removes empty directories from source after moving
- **Duplicate Detection**: Intelligent deduplication based on file size and content hashing
- **Smart Video Conversion**: Converts legacy formats to H.265/MP4 with clean COPY mode operation
- **Source Preservation**: COPY mode uses temp directory for conversion, leaves source untouched
- **Timezone-Aware Dates**: EST/EDT conversion for accurate video timestamps and Live Photo compatibility
- **macOS Optimized**: Uses native `sips` for photos, `ffprobe` for accurate video metadata extraction

### Advanced Features
- **File Permissions**: Set custom file permissions (e.g., 644, 600) with persistent defaults
- **Group Ownership**: Configure group ownership for files and directories with system validation
- **Import History**: Complete audit trail with timestamped sessions in `~/.photosort/history/`
- **Dual Logging**: Console shows progress, detailed logs saved per import session
- **Safe Operations**: Moves files with validation and ownership control
- **Progress Tracking**: Rich progress bars and detailed reporting
- **Remembers Settings**: Stores all preferences (paths, permissions, groups) with dynamic help

## Installation

### With UV (Recommended)

Install as a tool in an isolated environment:
```bash
uv tool install .
```

Or run directly from the repository:
```bash
uv run photosort --help
```

### Development Installation

Clone and install in development mode:
```bash
git clone <repository-url>
cd photosort
uv sync
uv run photosort --help
```

## Usage

### Basic Usage

```bash
# First run - specify source and destination
photosort ~/Downloads/Photos ~/Pictures/Organized

# Subsequent runs - uses remembered paths
photosort

# Override remembered paths
photosort --source ~/Desktop/NewPhotos --dest ~/Pictures/Archive
```

### File Ownership Control

```bash
# Set file permissions (saved as new default)
photosort --mode 644 ~/source ~/dest

# Set group ownership (saved as new default)  
photosort --group staff ~/source ~/dest

# Combine permissions and group
photosort --mode 600 --group wheel ~/source ~/dest
```

### Video Conversion and Live Photos

```bash
# Copy mode - source directory stays clean during video conversion
photosort --copy ~/source ~/dest

# Move mode with video conversion disabled
photosort --no-convert-videos ~/source ~/dest

# Set timezone for video metadata extraction
photosort --timezone "America/Los_Angeles" ~/source ~/dest

# Process directory with Live Photos (automatic detection)
photosort ~/iPhone-Photos ~/Pictures/Organized
```

### Configuration

Photosort remembers your preferences in `~/.photosort/config.yml`. The help message shows your current configured defaults:

```bash
photosort --help
```

### Options

#### File Management
- `--source`, `-s`: Source directory containing photos to organize
- `--dest`, `-d`: Destination directory for organized photos
- `--dry-run`, `-n`: Preview operations without making changes
- `--copy`, `-c`: Copy files instead of moving them (default is to move)
- `--verbose`, `-v`: Enable detailed logging

#### File Ownership
- `--mode`, `-m`: File permissions in octal format (e.g., 644, 664, 400)
- `--group`, `-g`: Group ownership (e.g., staff, users, wheel)

#### Video Processing
- `--no-convert-videos`: Disable automatic conversion of legacy video formats to H.265/MP4

#### Timezone Configuration
- `--timezone`, `--tz`: Set default timezone for video metadata (e.g., "America/New_York")

## File Organization

### Clean Destination Structure

Photos and videos are organized into this clean structure:
```
Destination/
├── 2024/
│   ├── 01/
│   │   ├── 20240115_143022.jpg
│   │   ├── 20240115_164510.mp4      # Videos sorted alongside photos
│   │   ├── 20240120_123045_000.jpg
│   │   ├── 20240120_123045_001.jpg  # Sequential counter for multiple files same time
│   │   └── 20240120_123045_002.jpg
│   └── 02/
│       ├── 20240203_091533_045.jpg  # Live Photo pairs share base filename
│       ├── 20240203_091533_045.mov  # with millisecond precision counters
│       ├── 20240203_091834_000.jpg  # Regular photos with standard counters
│       └── 20240203_091834_000.mp4  # Individual video files
```

### Import History Structure

All auxiliary files are preserved in a searchable history:
```
~/.photosort/
├── config.yml                         # Your saved preferences
├── imports.log                        # Global import summary log
└── history/                           # Per-import session history
    ├── 2024-06-26+Pictures-Organized/
    │   ├── import.log                 # Detailed logs for this import
    │   ├── LegacyVideos/              # Original videos before H.265/MP4 conversion
    │   │   ├── movie_001.avi
    │   │   └── video_old.3gp
    │   ├── Metadata/                  # Apple .AAE files and other metadata
    │   │   ├── IMG_1234.aae
    │   │   └── config.xml
    │   ├── UnknownFiles/              # Unrecognized file types
    │   └── Unsorted/                  # Files that couldn't be processed
    └── 2024-06-25+Archive-Photos/
        └── (similar structure)
```

## Supported Formats

### Photos
- JPG, JPEG, JPE
- RAW formats: CR2, NEF, ARW, DNG, RAF, ORF, PEF, RW2, and many more
- HEIC (iPhone photos)
- PNG, GIF, TIFF

### Videos
- MP4, MOV, AVI, MKV, M4V
- And many other common video formats

### Metadata Files
- AAE (iOS photo adjustments)
- XML, JSON, PLIST configuration files
- INI, CFG, DAT data files
- LOG, TXT documentation files
- All moved to import history `Metadata/` directory

## Requirements

- **macOS**: Uses `sips` command for photo metadata and `ffprobe` for video metadata
- **Python 3.8+**
- **ffmpeg**: Required for video conversion and metadata extraction
- **exiftool** (optional): Enhanced Live Photo detection via ContentIdentifier matching
- Dependencies: `rich`, `pyyaml`

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Format code
uv run black .

# Type checking
uv run mypy photosort/
```
