"""
File extension constants and settings for photo organization.
"""

# File extension constants
JPG_EXTENSIONS = (".jpg", ".jpeg", ".jpe")
RAW_EXTENSIONS = (
    ".3fr", ".3pr", ".arw", ".ce1", ".ce2", ".cib", ".cmt", ".cr2", ".craw",
    ".crw", ".dc2", ".dcr", ".dng", ".erf", ".exf", ".fff", ".fpx", ".gray",
    ".grey", ".gry", ".heic", ".iiq", ".kc2", ".kdc", ".mdc", ".mef", ".mfw",
    ".mos", ".mrw", ".ndd", ".nef", ".nop", ".nrw", ".nwb", ".orf", ".pcd",
    ".pef", ".png", ".ptx", ".ra2", ".raf", ".raw", ".rw2", ".rwl", ".rwz",
    ".sd0", ".sd1", ".sr2", ".srf", ".srw", ".st4", ".st5", ".st6", ".st7",
    ".st8", ".stx", ".x3f", ".ycbcra",
)
PHOTO_EXTENSIONS = JPG_EXTENSIONS + RAW_EXTENSIONS
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

# TODO: Future enhancement - Add ffmpeg video conversion for legacy formats
# Goal: Convert old formats (mpg, 3gp, etc.) to modern mp4/h264