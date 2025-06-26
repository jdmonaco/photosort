# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Photosort** is a modern Python tool for organizing photo and video collections into a year/month directory structure based on file creation dates. It's packaged as a proper Python tool installable via UV with comprehensive CLI features.

## Architecture

### Core Components
- **`photosort.py`**: Main script with class-based architecture
- **`PhotoSorter` class**: Handles the multi-phase processing workflow
- **`Config` class**: Manages YAML configuration and remembers user preferences
- **Rich UI**: Progress bars, tables, and colored console output

### Key Features
- **Smart path handling**: Uses `pathlib.Path` throughout for cross-platform compatibility
- **Configuration memory**: Stores last-used source/dest in `~/.config/photosort/photosort.yml`
- **Dynamic CLI help**: Shows current configured defaults in help text
- **Safe operations**: Move files with validation, automatic source cleanup
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

Output structure: `YYYY/MM/YYYY-MM-DD HH-MM-SS.ext`
- All media (photos and videos) go directly in month folders for better Live Photo support
- Metadata files (.aae, .xml, .json, etc.) go to `Metadata/` directory
- Unknown file types go to `UnknownFiles/` directory
- Problem files go to `Unsorted/` directory
- Source directory is automatically cleaned when moving files

## Key Functions

### Core Processing
- `PhotoSorter.process_files()`: Main media file processing with progress tracking
- `PhotoSorter.process_metadata_files()`: Handles metadata files separately
- `cleanup_source_directory()`: Module function for post-processing source cleanup

### File Discovery
- `find_source_files()`: Returns tuple of (media_files, metadata_files)
- Separates processing streams for different file types

## Configuration System

The `Config` class manages `~/.config/photosort/photosort.yml`:
- Remembers last source/destination paths
- Updates automatically when user specifies new paths
- CLI help shows current configured defaults
- Graceful fallback if config is missing/corrupted

## Error Handling

- Comprehensive logging with Rich formatting
- Problematic files moved to `Unsorted/` directory
- Unknown files moved to `UnknownFiles/` directory
- Metadata files moved to `Metadata/` directory
- Safe file operations with validation
- Automatic source directory cleanup after successful moves
- Graceful degradation (filesystem dates if EXIF extraction fails)
