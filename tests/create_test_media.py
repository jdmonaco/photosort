#!/usr/bin/env python3
"""
Create test media directory structure from developer-provided examples.

Usage:
    python create_test_media.py /path/to/your/media/collection

This script will:
1. Scan your media collection for suitable test files
2. Copy selected files to tests/example_media/
3. Modify dates/metadata as needed for test scenarios
4. Generate report of what was created
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path to import photosort modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from photosort.constants import PHOTO_EXTENSIONS, MOVIE_EXTENSIONS, METADATA_EXTENSIONS
from photosort.file_operations import FileOperations


class TestMediaCreator:
    """Creates a curated test media directory from user's media collection."""
    
    def __init__(self, source_dir: Path, target_dir: Path):
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.file_ops = FileOperations(dry_run=False, move_files=False, mode=None, gid=None)
        self.selected_files = {
            'photos': [],
            'videos': [],
            'livephotos': [],
            'metadata': [],
            'misc': []
        }
        self.report = []
    
    def scan_for_suitable_files(self) -> None:
        """Scan source directory for files matching our test requirements."""
        print(f"Scanning {self.source_dir} for suitable test files...")
        
        all_files = list(self.source_dir.rglob("*"))
        print(f"Found {len(all_files)} total files")
        
        # Categorize files
        photos = []
        videos = []
        metadata = []
        
        for file_path in all_files:
            if not file_path.is_file():
                continue
                
            ext = file_path.suffix.lower()
            
            if ext in PHOTO_EXTENSIONS:
                photos.append(file_path)
            elif ext in MOVIE_EXTENSIONS:
                videos.append(file_path)
            elif ext in METADATA_EXTENSIONS:
                metadata.append(file_path)
        
        print(f"Found {len(photos)} photos, {len(videos)} videos, {len(metadata)} metadata files")
        
        # Select diverse photos
        self._select_photos(photos)
        
        # Select videos with different codecs
        self._select_videos(videos)
        
        # Detect and select Live Photo pairs
        self._select_livephotos(photos, videos)
        
        # Select metadata files
        self._select_metadata(metadata)
        
        # Add misc files
        self._add_misc_files()
    
    def _select_photos(self, photos: List[Path]) -> None:
        """Select a diverse set of photos for testing."""
        selected = []
        
        # Group by extension
        by_extension = {}
        for photo in photos:
            ext = photo.suffix.lower()
            if ext not in by_extension:
                by_extension[ext] = []
            by_extension[ext].append(photo)
        
        # Select at least one of each type, prioritizing variety
        priority_exts = ['.jpg', '.heic', '.cr2', '.nef', '.arw', '.png']
        
        for ext in priority_exts:
            if ext in by_extension and by_extension[ext]:
                selected.append(by_extension[ext][0])
                if len(selected) >= 5:  # Limit selection
                    break
        
        # Add any remaining types
        for ext, files in by_extension.items():
            if ext not in priority_exts and files:
                selected.append(files[0])
                if len(selected) >= 8:
                    break
        
        self.selected_files['photos'] = selected[:8]
        self.report.append(f"Selected {len(self.selected_files['photos'])} photos")
    
    def _select_videos(self, videos: List[Path]) -> None:
        """Select videos with different codecs."""
        selected = []
        
        # Group by extension as proxy for codec variety
        by_extension = {}
        for video in videos:
            ext = video.suffix.lower()
            if ext not in by_extension:
                by_extension[ext] = []
            by_extension[ext].append(video)
        
        # Priority order for codec variety
        priority_exts = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.3gp']
        
        for ext in priority_exts:
            if ext in by_extension and by_extension[ext]:
                selected.append(by_extension[ext][0])
                if len(selected) >= 4:
                    break
        
        self.selected_files['videos'] = selected[:4]
        self.report.append(f"Selected {len(self.selected_files['videos'])} videos")
    
    def _select_livephotos(self, photos: List[Path], videos: List[Path]) -> None:
        """Detect and select Live Photo pairs."""
        # Build basename maps
        photo_map = {}
        video_map = {}
        
        for photo in photos:
            if photo.suffix.lower() in ('.jpg', '.jpeg', '.heic'):
                basename = photo.stem
                photo_map[basename] = photo
        
        for video in videos:
            if video.suffix.lower() in ('.mov', '.mp4'):
                basename = video.stem
                video_map[basename] = video
        
        # Find matching pairs
        pairs = []
        for basename in set(photo_map.keys()) & set(video_map.keys()):
            pairs.append((photo_map[basename], video_map[basename]))
            if len(pairs) >= 3:  # Limit to 3 pairs
                break
        
        # Flatten pairs for storage
        for photo, video in pairs:
            self.selected_files['livephotos'].extend([photo, video])
        
        self.report.append(f"Selected {len(pairs)} Live Photo pairs")
    
    def _select_metadata(self, metadata: List[Path]) -> None:
        """Select metadata files, prioritizing .aae files."""
        selected = []
        
        # Prioritize .aae files
        aae_files = [f for f in metadata if f.suffix.lower() == '.aae']
        other_metadata = [f for f in metadata if f.suffix.lower() != '.aae']
        
        # Select up to 3 .aae files
        selected.extend(aae_files[:3])
        
        # Add other metadata types
        for file in other_metadata:
            if len(selected) >= 5:
                break
            selected.append(file)
        
        self.selected_files['metadata'] = selected
        self.report.append(f"Selected {len(self.selected_files['metadata'])} metadata files")
    
    def _add_misc_files(self) -> None:
        """Add miscellaneous test files."""
        # Look for .DS_Store files
        ds_store_files = list(self.source_dir.rglob(".DS_Store"))
        if ds_store_files:
            self.selected_files['misc'].append(ds_store_files[0])
        
        # Look for any unknown extensions
        all_files = list(self.source_dir.rglob("*"))
        for file_path in all_files[:100]:  # Limit search
            if not file_path.is_file():
                continue
            ext = file_path.suffix.lower()
            if (ext and 
                ext not in PHOTO_EXTENSIONS and 
                ext not in MOVIE_EXTENSIONS and 
                ext not in METADATA_EXTENSIONS and
                ext != '.ds_store'):
                self.selected_files['misc'].append(file_path)
                break
    
    def create_test_structure(self) -> None:
        """Create the test media directory structure."""
        # Clean existing directory
        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)
        
        # Create subdirectories
        (self.target_dir / "photos").mkdir(parents=True, exist_ok=True)
        (self.target_dir / "videos").mkdir(parents=True, exist_ok=True)
        (self.target_dir / "livephotos").mkdir(parents=True, exist_ok=True)
        (self.target_dir / "metadata").mkdir(parents=True, exist_ok=True)
        (self.target_dir / "misc").mkdir(parents=True, exist_ok=True)
    
    def copy_and_prepare_files(self) -> None:
        """Copy selected files and prepare test scenarios."""
        print("\nCopying selected files...")
        
        # Copy photos
        for i, photo in enumerate(self.selected_files['photos']):
            dest_name = f"photo_{i:03d}{photo.suffix}"
            dest_path = self.target_dir / "photos" / dest_name
            shutil.copy2(photo, dest_path)
            print(f"  Copied {photo.name} -> {dest_name}")
        
        # Create burst sequence from first 3 photos
        if len(self.selected_files['photos']) >= 3:
            print("\nCreating burst sequence...")
            burst_time = datetime(2024, 1, 20, 12, 30, 45)
            for i in range(3):
                src = self.selected_files['photos'][i]
                dest_name = f"burst_{i+1:03d}{src.suffix}"
                dest_path = self.target_dir / "photos" / dest_name
                shutil.copy2(src, dest_path)
                # Note: Setting EXIF dates requires exiftool or similar
                print(f"  Created burst photo: {dest_name}")
        
        # Copy videos
        for i, video in enumerate(self.selected_files['videos']):
            ext = video.suffix.lower()
            # Name them descriptively
            if ext == '.mp4':
                dest_name = "modern_h264.mp4"
            elif ext == '.avi':
                dest_name = "legacy_avi.avi"
            elif ext == '.mov':
                dest_name = "quicktime.mov"
            else:
                dest_name = f"video_{i:03d}{video.suffix}"
            
            dest_path = self.target_dir / "videos" / dest_name
            shutil.copy2(video, dest_path)
            print(f"  Copied {video.name} -> {dest_name}")
        
        # Copy Live Photo pairs
        pair_count = len(self.selected_files['livephotos']) // 2
        for i in range(pair_count):
            photo = self.selected_files['livephotos'][i*2]
            video = self.selected_files['livephotos'][i*2 + 1]
            
            photo_dest = self.target_dir / "livephotos" / f"LP_{i+1:03d}{photo.suffix}"
            video_dest = self.target_dir / "livephotos" / f"LP_{i+1:03d}{video.suffix}"
            
            shutil.copy2(photo, photo_dest)
            shutil.copy2(video, video_dest)
            print(f"  Copied Live Photo pair: LP_{i+1:03d}")
        
        # Copy metadata files
        for i, metadata in enumerate(self.selected_files['metadata']):
            dest_path = self.target_dir / "metadata" / metadata.name
            shutil.copy2(metadata, dest_path)
            print(f"  Copied metadata: {metadata.name}")
        
        # Copy misc files
        for misc in self.selected_files['misc']:
            dest_path = self.target_dir / "misc" / misc.name
            shutil.copy2(misc, dest_path)
            print(f"  Copied misc: {misc.name}")
        
        # Create a file without EXIF (if we have photos)
        if self.selected_files['photos']:
            src = self.selected_files['photos'][0]
            no_exif_path = self.target_dir / "photos" / f"no_exif{src.suffix}"
            shutil.copy2(src, no_exif_path)
            # Note: Stripping EXIF requires additional tools
            print(f"  Created no_exif{src.suffix} (EXIF stripping requires exiftool)")
    
    def generate_documentation(self) -> None:
        """Generate README documenting the test files."""
        readme_path = self.target_dir / "README.md"
        
        content = ["# Test Media Files\n"]
        content.append("This directory contains real media files for testing photosort.\n")
        content.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        content.append(f"Source: {self.source_dir}\n")
        
        # Document each category
        if self.selected_files['photos']:
            content.append("\n## Photos\n")
            for i, photo in enumerate(self.selected_files['photos']):
                content.append(f"- `photo_{i:03d}{photo.suffix}`: {photo.name}\n")
            content.append("- `burst_001-003.*`: Burst sequence (same timestamp)\n")
            content.append("- `no_exif.*`: Photo with EXIF data stripped\n")
        
        if self.selected_files['videos']:
            content.append("\n## Videos\n")
            for video in self.selected_files['videos']:
                content.append(f"- `{video.name}`: Original file\n")
        
        if self.selected_files['livephotos']:
            content.append("\n## Live Photos\n")
            pair_count = len(self.selected_files['livephotos']) // 2
            for i in range(pair_count):
                content.append(f"- `LP_{i+1:03d}.*`: Live Photo pair\n")
        
        if self.selected_files['metadata']:
            content.append("\n## Metadata Files\n")
            for metadata in self.selected_files['metadata']:
                content.append(f"- `{metadata.name}`: {metadata.suffix} metadata\n")
        
        if self.selected_files['misc']:
            content.append("\n## Miscellaneous Files\n")
            for misc in self.selected_files['misc']:
                content.append(f"- `{misc.name}`: Test file\n")
        
        # Add setup notes
        content.append("\n## Setup Notes\n")
        content.append("- Burst photos need EXIF timestamps set to identical values\n")
        content.append("- no_exif.* needs EXIF data stripped\n")
        content.append("- Use exiftool to verify/modify metadata as needed\n")
        
        with open(readme_path, 'w') as f:
            f.writelines(content)
        
        print(f"\nGenerated {readme_path}")
    
    def create_test_media(self) -> None:
        """Main method to create test media directory."""
        self.scan_for_suitable_files()
        self.create_test_structure()
        self.copy_and_prepare_files()
        self.generate_documentation()
        
        print("\n=== Summary ===")
        for line in self.report:
            print(line)
        print(f"\nTest media created in: {self.target_dir}")
        print("\nNext steps:")
        print("1. Review the generated files")
        print("2. Use exiftool to set specific timestamps on burst photos")
        print("3. Use exiftool to strip EXIF from no_exif photo")
        print("4. Verify Live Photo pairs have ContentIdentifier metadata")


def main():
    parser = argparse.ArgumentParser(
        description="Create test media directory from your media collection"
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Path to your media collection"
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path(__file__).parent / "example_media",
        help="Target directory for test media (default: tests/example_media)"
    )
    
    args = parser.parse_args()
    
    if not args.source.exists():
        print(f"Error: Source directory does not exist: {args.source}")
        return 1
    
    if not args.source.is_dir():
        print(f"Error: Source is not a directory: {args.source}")
        return 1
    
    creator = TestMediaCreator(args.source, args.target)
    creator.create_test_media()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())