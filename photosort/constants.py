"""
File extension constants, program metadata, and settings for photo organization.
"""

import logging
import subprocess
from rich.console import Console


# Program metadata
PROGRAM = "photosort"


# Shared console access
console = Console()
def get_console() -> Console:
    """Get a shared rich.Console() instance."""
    return console


# Shared logger access
def get_logger(name: str = PROGRAM) -> logging.Logger:
    """Get a logger instance with consistent naming."""
    return logging.getLogger(name)


# Tool availability
def check_tool_availability(cmd: str, version_flag: str = "-h") -> bool:
    """Check availability of a command-line tool on this system."""
    try:
        subprocess.run([cmd, version_flag], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


ffmpeg_available = check_tool_availability("ffmpeg", "-version")
ffprobe_available = check_tool_availability("ffprobe", "-version")
exiftool_available = check_tool_availability("exiftool", "-ver")
sips_available = check_tool_availability("sips", "-v")


# File extension constants
JPG_EXTENSIONS = (".jpg", ".jpeg", ".jpe")
IMG_EXTENSIONS = (
    ".3fr", ".3pr", ".arw", ".ce1", ".ce2", ".cib", ".cmt", ".cr2", ".craw",
    ".crw", ".dc2", ".dcr", ".dng", ".erf", ".exf", ".fff", ".fpx", ".gif",
    ".gray", ".grey", ".gry", ".heic", ".iiq", ".kc2", ".kdc", ".mdc", ".mef",
    ".mfw", ".mos", ".mrw", ".ndd", ".nef", ".nop", ".nrw", ".nwb", ".orf",
    ".pcd", ".pef", ".png", ".ptx", ".ra2", ".raf", ".raw", ".rw2", ".rwl",
    ".rwz", ".sd0", ".sd1", ".sr2", ".srf", ".srw", ".st4", ".st5", ".st6",
    ".st7", ".st8", ".stx", ".tif", ".tiff", ".x3f", ".ycbcra"
)
PHOTO_EXTENSIONS = JPG_EXTENSIONS + IMG_EXTENSIONS
MOVIE_EXTENSIONS = (
    ".3g2", ".3gp", ".asf", ".asx", ".avi", ".flv", ".m4v", ".mov", ".mp4",
    ".mpg", ".rm", ".srt", ".swf", ".vob", ".wmv", ".aepx", ".ale", ".avp",
    ".avs", ".bdm", ".bik", ".bin", ".bsf", ".camproj", ".cpi", ".dash",
    ".divx", ".dmsm", ".dream", ".dvdmedia", ".dvr-ms", ".dzm", ".dzp",
    ".edl", ".f4v", ".fbr", ".fcproject", ".hdmov", ".imovieproj", ".ism",
    ".ismv", ".m2p", ".mkv", ".mod", ".moi", ".mpeg", ".mts", ".mxf", ".ogv",
    ".otrkey", ".pds", ".prproj", ".psh", ".r3d", ".rcproject", ".rmvb",
    ".scm", ".smil", ".snagproj", ".sqz", ".stx", ".swi", ".tix", ".trp",
    ".ts", ".veg", ".vf", ".vro", ".webm", ".wlmp", ".wtv", ".xvid", ".yuv",
)
METADATA_EXTENSIONS = (
    ".aae", ".dat", ".ini", ".cfg", ".xml", ".plist", ".json", ".txt", ".log",
    ".info", ".meta", ".properties", ".conf", ".config", ".xmp"
)
NUISANCE_EXTENSIONS = (
    ".ds_store", ".thumbs.db", ".desktop.ini", "thumbs.db"
)
VALID_EXTENSIONS = PHOTO_EXTENSIONS + MOVIE_EXTENSIONS


# Video codecs
MODERN_VIDEO_CODECS = (
    "hevc", "h265", "h264", "avc", "av1", "vp9"
)

