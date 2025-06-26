# Photosort

A modern Python tool for organizing photos and videos into a clean year/month folder structure based on creation dates.

## Features

- **Smart Organization**: Automatically sorts photos and videos by creation date into `YYYY/MM/` folders
- **Live Photo Friendly**: Photos and videos in same folders for better photo management software support
- **Multiple Media Types**: Supports photos (JPG, RAW formats), videos, and handles metadata files separately
- **Metadata Separation**: Apple .AAE files and other metadata moved to dedicated `Metadata/` directory
- **Auto Source Cleanup**: Automatically cleans and removes empty directories from source after moving
- **Safe Operations**: Moves files with validation to prevent data loss
- **Duplicate Detection**: Intelligent deduplication based on file size and content hashing
- **Progress Tracking**: Rich progress bars and detailed reporting
- **Remembers Settings**: Stores your preferred source and destination paths
- **macOS Optimized**: Uses native `sips` command for accurate photo metadata extraction

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

### Configuration

Photosort remembers your last used source and destination paths in `~/.config/photosort.yml`. The help message shows your current configured defaults:

```bash
photosort --help
```

### Options

- `--source`, `-s`: Source directory containing photos to organize
- `--dest`, `-d`: Destination directory for organized photos
- `--dry-run`: Preview operations without making changes
- `--move`: Move files (default) vs copy
- `--verbose`, `-v`: Detailed logging output

## File Organization

Photos and videos are organized into this structure:
```
Destination/
├── 2024/
│   ├── 01/
│   │   ├── 2024-01-15 14-30-22.jpg
│   │   ├── 2024-01-15 16-45-10.mp4  # Videos alongside photos
│   │   └── 2024-01-20 12-30-45.jpg
│   └── 02/
│       └── 2024-02-03 09-15-33.jpg
├── Metadata/           # Apple .AAE files and other metadata
│   ├── IMG_1234.aae
│   └── config.xml
├── UnknownFiles/       # Unrecognized file types
└── Unsorted/          # Files that couldn't be processed
```

## Supported Formats

### Photos
- JPG, JPEG, JPE
- RAW formats: CR2, NEF, ARW, DNG, RAF, ORF, PEF, RW2, and many more
- HEIC (iPhone photos)
- PNG

### Videos
- MP4, MOV, AVI, MKV, M4V
- And many other common video formats

### Metadata Files
- AAE (iOS photo adjustments)
- XML, JSON, PLIST configuration files
- INI, CFG, DAT data files
- LOG, TXT documentation files
- All moved to separate `Metadata/` directory

## Requirements

- **macOS**: Uses `sips` command for photo metadata
- **Python 3.8+**
- Dependencies: `rich`, `pyyaml`

## Migration from organize-photos.py

If you were using the old `organize-photos.py` script:

1. Your existing organized photos remain unchanged
2. Install photosort as shown above
3. First run will ask for your source/destination preferences
4. New features: metadata separation, source cleanup, no movies subfolder
5. Live Photos will work better with photo management software

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Format code
uv run black .

# Type checking
uv run mypy photosort.py
```
