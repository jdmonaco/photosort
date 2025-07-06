# Example Media Directory

This directory contains curated test media files with real EXIF metadata for comprehensive testing of the photosort tool.

## Directory Structure

```
example_media/
├── photos/           # Photo files with EXIF data
│   ├── *.jpg        # JPEG photos with creation dates
│   ├── *.heic       # HEIC photos (iPhone format)
│   ├── *.png        # PNG images
│   └── *.gif        # GIF images
├── videos/          # Video files with metadata
│   ├── *.mp4        # MP4 videos (modern H.264/H.265)
│   ├── *.mov        # MOV videos (QuickTime format)
│   └── *.avi        # Legacy AVI videos (for conversion testing)
├── livephotos/      # Apple Live Photo pairs
│   ├── IMG_*.heic   # Live Photo images
│   └── IMG_*.mov    # Live Photo videos
├── metadata/        # Metadata files
│   ├── *.aae        # Apple Adjustment files
│   ├── *.xml        # XML metadata
│   └── *.json       # JSON metadata
└── misc/           # Miscellaneous test files
    ├── *.txt        # Unknown file types
    └── .DS_Store    # System files for cleanup testing
```

## Creating the Example Media Directory

The `example_media` directory is not included in the repository and must be created using the `create_test_media.py` script:

```bash
# From the tests directory
python create_test_media.py /path/to/your/media/collection

# Example with typical media locations
python create_test_media.py ~/Pictures
python create_test_media.py ~/Downloads
python create_test_media.py /Volumes/Camera/DCIM
```

## Media Requirements

The test media should include:

### Photos
- **JPEG files** with EXIF creation dates from different years/months
- **HEIC files** from iPhone/iPad (for Live Photo testing)
- **PNG files** for format diversity
- **GIF files** for animation handling
- **Burst sequences** with identical timestamps
- **Photos with different timezones** for timezone testing

### Videos
- **Modern MP4/MOV files** with H.264/H.265 codecs (no conversion needed)
- **Legacy format videos** (.avi, .wmv, .mpg) for conversion testing
- **iPhone videos** (.mov) with proper metadata
- **Videos with different creation dates** spanning multiple years
- **Short duration videos** to minimize test file sizes

### Live Photos
- **Matching HEIC+MOV pairs** from iPhone with ContentIdentifier metadata
- **Files with identical basenames** for fallback detection testing
- **Live Photos from different dates** for organization testing

### Metadata Files
- **Apple Adjustment files** (.aae) paired with photos
- **XML metadata** files from various sources
- **JSON metadata** files from photo management apps
- **Sidecar files** for metadata handling testing

### Miscellaneous Files
- **Unknown file types** (.txt, .doc, etc.) for cleanup testing
- **System files** (.DS_Store, Thumbs.db) for nuisance file removal
- **Empty directories** for cleanup testing

## File Selection Criteria

The `create_test_media.py` script looks for files with these characteristics:

### Date Distribution
- Files from at least 3 different years
- Files from at least 6 different months
- Files from at least 10 different days

### Size Requirements
- Photos: 50KB - 50MB (reasonable test sizes)
- Videos: 1MB - 100MB (to avoid huge test files)
- Total collection: Aim for &lt; 1GB

### Metadata Quality
- Files with valid EXIF creation dates
- Files with GPS coordinates (optional)
- Files with proper format-specific metadata

### Format Diversity
- At least 3 different photo formats
- At least 2 different video formats
- At least 1 legacy video format for conversion testing

## Usage in Tests

The example media directory is used by pytest fixtures:

```python
@pytest.fixture(scope="session")
def example_media_dir():
    """Path to the example media directory with real files."""
    media_dir = Path(__file__).parent / "example_media"
    if not media_dir.exists():
        pytest.skip("Example media directory not found. Run create_test_media.py")
    return media_dir

@pytest.fixture
def temp_source_folder(example_media_dir, tmp_path):
    """Create a temporary copy of example media for each test."""
    temp_source = tmp_path / "source"
    shutil.copytree(example_media_dir, temp_source)
    return temp_source
```

Each test gets a fresh copy of the example media in a temporary directory, ensuring test isolation and preventing side effects.

## Test Coverage

The example media enables testing of:

- **Basic operations**: move, copy, dry-run with real files
- **Date-based organization**: YYYY/MM structure with real dates
- **File format handling**: Multiple photo and video formats
- **Live Photo processing**: ContentIdentifier and basename matching
- **Video conversion**: Legacy format detection and H.265 conversion
- **Metadata handling**: Sidecar files and Apple adjustments
- **Duplicate detection**: Size and hash-based comparison
- **Permission handling**: File mode and group ownership
- **Configuration persistence**: Path and preference memory
- **Error handling**: Problematic files and edge cases

## Maintenance

The example media directory should be periodically refreshed to:

- Add new file formats as they become common
- Update codec testing with newer video formats
- Include files from recent camera models
- Test edge cases discovered in real usage

Run the creation script with different source directories to maintain a diverse test collection:

```bash
# Refresh with new media
python create_test_media.py --refresh ~/Pictures/Recent

# Add specific file types
python create_test_media.py --formats heic,mov ~/iPhone/Photos

# Create minimal test set
python create_test_media.py --minimal ~/Downloads/Camera
```

## Security Note

Do not commit the example media directory to version control:
- Contains potentially personal photos/videos
- Large binary files bloat repository size
- Each developer should curate their own test media

The `.gitignore` file excludes this directory:
```
tests/example_media/
```
