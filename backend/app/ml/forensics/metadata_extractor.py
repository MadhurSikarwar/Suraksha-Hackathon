import fitz  # PyMuPDF
from PIL import Image, ExifTags
import os
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Tools that indicate an image or PDF was edited, not scanned/photographed
SUSPICIOUS_TOOLS = [
    'photoshop', 'gimp', 'illustrator', 'corel', 'inkscape',
    'canva', 'paint.net', 'snagit', 'lightroom', 'affinity',
    'preview', 'paintshop',
]

# Tools that are ambiguous — flag as low-severity, not definitive
MEDIUM_RISK_TOOLS = ['acrobat', 'word', 'libreoffice', 'openoffice']


def _parse_pdf_date(date_str: str):
    """
    Attempts to parse a PDF date string (format: D:YYYYMMDDHHMMSS±HH'MM').
    Returns a datetime object or None on failure.
    """
    if not date_str:
        return None
    # Strip the 'D:' prefix if present
    s = date_str.strip()
    if s.startswith('D:'):
        s = s[2:]
    # Only use the first 14 digits (YYYYMMDDHHmmss)
    s = s[:14]
    try:
        return datetime.strptime(s, '%Y%m%d%H%M%S')
    except ValueError:
        return None


def analyze_pdf_metadata(file_path: str) -> dict:
    """
    Extracts metadata from a PDF file to check for forensic anomalies.
    Improvements:
    - Parses dates properly instead of simple string comparison
    - Distinguishes HIGH and MEDIUM severity suspicious tools
    - Flags missing metadata (legitimate docs usually have it)
    - Detects significant modification time lag (>24 hrs indicates post-signing edits)
    """
    try:
        doc = fitz.open(file_path)
        metadata = doc.metadata or {}

        results = {
            "is_suspicious": False,
            "reasons": [],
            "severity": "LOW",
            "extracted_data": metadata
        }

        producer = (metadata.get('producer') or '').lower()
        creator = (metadata.get('creator') or '').lower()

        # --- Check for high-risk editing tools ---
        for tool in SUSPICIOUS_TOOLS:
            if tool in producer or tool in creator:
                results["is_suspicious"] = True
                results["severity"] = "HIGH"
                tool_name = tool.capitalize()
                source = "Producer" if tool in producer else "Creator"
                results["reasons"].append(
                    f"Forensic Flag: Suspicious PDF {source} tool detected — '{tool_name}'. "
                    f"This tool is typically used for image editing, not document generation."
                )

        # --- Check for medium-risk tools (flagged but not definitive) ---
        if not results["is_suspicious"]:
            for tool in MEDIUM_RISK_TOOLS:
                if tool in producer or tool in creator:
                    results["reasons"].append(
                        f"Metadata Note: Document produced via '{tool.capitalize()}' — "
                        f"verify this matches expected document generation workflow."
                    )

        # --- Date consistency check ---
        creation_date_str = metadata.get('creationDate') or ''
        mod_date_str = metadata.get('modDate') or ''

        creation_dt = _parse_pdf_date(creation_date_str)
        mod_dt = _parse_pdf_date(mod_date_str)

        if creation_dt and mod_dt:
            delta = abs((mod_dt - creation_dt).total_seconds())
            if delta > 86400:  # > 24 hours difference
                hours = delta / 3600
                results["is_suspicious"] = True
                if results["severity"] == "LOW":
                    results["severity"] = "MEDIUM"
                results["reasons"].append(
                    f"Timestamp Anomaly: PDF was modified {hours:.1f} hours after creation "
                    f"(creation: {creation_date_str[:12]}, modified: {mod_date_str[:12]}). "
                    f"Indicates post-signing edits."
                )
            elif creation_date_str and mod_date_str and creation_date_str != mod_date_str:
                # Minor mismatch (< 24 hrs) — informational only
                results["reasons"].append(
                    f"Minor: PDF modification date slightly differs from creation date "
                    f"(within 24 hrs — possible version save, not definitive tampering)."
                )
        elif creation_date_str and mod_date_str and creation_date_str != mod_date_str:
            # Couldn't parse, fall back to string comparison
            results["is_suspicious"] = True
            if results["severity"] == "LOW":
                results["severity"] = "MEDIUM"
            results["reasons"].append(
                "PDF Modification date differs from Creation date (could not parse exact delta)."
            )

        # --- Missing metadata check ---
        missing_fields = [f for f in ['title', 'author', 'producer'] if not metadata.get(f)]
        if len(missing_fields) >= 3:
            results["reasons"].append(
                "Metadata Integrity: All key fields (title, author, producer) are empty. "
                "Legitimate institutional documents typically include these."
            )

        doc.close()
        return results

    except Exception as e:
        logger.error(f"PDF metadata analysis failed: {e}")
        return {
            "is_suspicious": False,
            "reasons": [f"Failed to parse PDF metadata: {str(e)}"],
            "severity": "LOW"
        }


def analyze_image_metadata(file_path: str) -> dict:
    """
    Extracts EXIF data from images for forensic signals.
    Improvements:
    - Checks GPS embedding (uncommon in scanned legal docs — suspicious)
    - Validates date/time format integrity
    - Checks for missing camera model (edited images often lack this)
    - Improved editing software detection with severity grading
    """
    try:
        image = Image.open(file_path)

        # Try to get EXIF data
        exifdata = image.getexif()
        if not exifdata and hasattr(image, '_getexif'):
            try:
                exifdata = image._getexif()
            except Exception:
                exifdata = None

        results = {
            "is_suspicious": False,
            "reasons": [],
            "severity": "LOW",
            "extracted_data": {}
        }

        # --- Physical integrity: resolution gate ---
        w, h = image.size
        if w < 200 or h < 200:
            results["is_suspicious"] = True
            results["severity"] = "HIGH"
            results["reasons"].append(
                f"Sub-threshold resolution ({w}×{h}px): Document dimensions are too small for "
                f"a genuine financial collateral document. Possible thumbnail substitution."
            )

        # Check if it's a known image format with no EXIF (could be generated/edited)
        if not exifdata:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ('.jpg', '.jpeg'):
                # JPEG without EXIF is common in edited/exported images
                results["reasons"].append(
                    "EXIF Absent: JPEG file has no EXIF metadata. "
                    "Camera-captured images almost always contain EXIF. "
                    "Absence suggests digital creation or EXIF stripping."
                )
            image.close()
            return results

        # --- Parse EXIF fields ---
        has_gps = False
        has_camera_model = False
        software_flagged = False

        for tag_id in exifdata:
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            data = exifdata.get(tag_id)
            if isinstance(data, bytes):
                try:
                    data = data.decode('utf-8', errors='ignore').strip()
                except Exception:
                    data = str(data)
            results["extracted_data"][str(tag)] = str(data)[:200]

            # --- Editing software check ---
            if str(tag) in ('Software', 'ProcessingSoftware'):
                sw_lower = str(data).lower()
                for tool in SUSPICIOUS_TOOLS:
                    if tool in sw_lower and not software_flagged:
                        results["is_suspicious"] = True
                        results["severity"] = "HIGH"
                        results["reasons"].append(
                            f"Forensic Flag: EXIF Software tag contains editing tool signature — "
                            f"'{data}'. This image was processed by an editing application."
                        )
                        software_flagged = True
                        break

            # --- GPS check (unusual in scanned legal docs) ---
            if str(tag) == 'GPSInfo' and data:
                has_gps = True

            # --- Camera model presence ---
            if str(tag) in ('Make', 'Model') and str(data).strip() not in ('', 'None', 'N/A'):
                has_camera_model = True

            # --- DateTime format validation ---
            if str(tag) in ('DateTime', 'DateTimeOriginal', 'DateTimeDigitized'):
                dt_str = str(data).strip()
                results["extracted_data"]["image_datetime"] = dt_str
                # Validate format: YYYY:MM:DD HH:MM:SS
                if dt_str and not re.match(r'^\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}$', dt_str):
                    results["reasons"].append(
                        f"Date Format Anomaly: EXIF '{tag}' has malformed value: '{dt_str}'. "
                        f"Expected format: YYYY:MM:DD HH:MM:SS."
                    )

        # --- GPS in legal document: unusual ---
        if has_gps:
            results["reasons"].append(
                "GPS Data Present: This image contains embedded GPS coordinates. "
                "Scanned property documents rarely have GPS. "
                "Could indicate a photographed (manipulated) copy."
            )

        # --- No camera model in JPEG (edited/created) ---
        if not has_camera_model and not software_flagged:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ('.jpg', '.jpeg'):
                results["reasons"].append(
                    "Missing Camera Make/Model: No camera manufacturer data in EXIF. "
                    "May indicate digitally created or heavily processed image."
                )

        image.close()
        return results

    except Exception as e:
        logger.error(f"Image metadata analysis failed: {e}")
        return {
            "is_suspicious": False,
            "reasons": [f"Failed to parse image metadata: {str(e)}"],
            "severity": "LOW"
        }


def extract_metadata(file_path: str) -> dict:
    """Main routing function based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return analyze_pdf_metadata(file_path)
    elif ext in ('.jpg', '.jpeg', '.png', '.tiff', '.bmp'):
        return analyze_image_metadata(file_path)
    else:
        return {
            "is_suspicious": False,
            "reasons": ["Unsupported file type for metadata forensics."],
            "severity": "LOW"
        }
