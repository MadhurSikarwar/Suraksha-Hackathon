import fitz
import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

from PIL import Image, ExifTags

# Try to load Tesseract OCR for actual text extraction from images (no hardcoding).
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


def extract_text_from_pdf(file_path: str) -> str:
    """Extract raw text from all pages of a PDF document."""
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        logger.error(f"PDF text extraction error: {e}")
    return text


def extract_text_from_image(file_path: str) -> Tuple[str, str]:
    """Extracts text from image. Returns (text, source) where source indicates quality."""
    try:
        img = Image.open(file_path)

        # 1. Forensic Layer: Query EXIF Metadata (tag 270 = ImageDescription)
        exif = img.getexif()
        if exif and 270 in exif:
            desc_text = exif.get(270)
            if isinstance(desc_text, str) and desc_text.strip():
                img.close()
                logger.info("Recovered text layer directly from EXIF metadata header (270).")
                return desc_text, "exif"

        # 2. Fallback Layer: Active Tesseract OCR (if installed)
        if not TESSERACT_AVAILABLE:
            img.close()
            return "", "none"

        text = pytesseract.image_to_string(img)
        img.close()
        return text, "tesseract"
    except Exception as e:
        logger.error(f"Image text extraction failed: {e}")
        return "", "none"


def extract_legal_entities(file_path: str) -> dict:
    """
    Extracts critical legal entities (Survey Number, Buyer, Seller, Date)
    using rule-based regex patterns suited for Indian land records.
    Attempts ACTUAL text extraction from PDFs and images (via Tesseract).
    If no text is extractable, absolutely nothing is returned or fabricated.
    """
    ext = file_path.lower().rsplit('.', 1)[-1]
    text_source = "pdf"  # Track where text came from for confidence calibration

    if ext == 'pdf':
        text = extract_text_from_pdf(file_path)
        text_source = "pdf"
    else:
        text, text_source = extract_text_from_image(file_path)

    results = {
        "extracted_entities": {},
        "is_suspicious": False,
        "reasons": []
    }

    if not text.strip():
        results["extracted_entities"] = {
            "survey_number": {"value": "Not Detected", "confidence": 0.0, "status": "Not Detected"},
            "date": {"value": "Not Detected", "confidence": 0.0, "status": "Not Detected"},
            "buyer": {"value": "Not Detected", "confidence": 0.0, "status": "Not Detected"},
            "seller": {"value": "Not Detected", "confidence": 0.0, "status": "Not Detected"},
        }
        results["reasons"].append("NLP: No text could be extracted from this document.")
        results["is_suspicious"] = True
        return results

    # --- Regex Extractors ---
    survey_match = re.search(
        r'(survey\s*no|sy\s*no|sy[\.\-]?)\s*[:\.]?\s*([0-9a-zA-Z/\-]+)',
        text, re.IGNORECASE
    )
    date_match = re.search(r'\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b', text)
    # --- Robust Case-Sensitive Entity Extractors ---
    # To handle case-insensitive role matching WITHOUT breaking case-sensitive
    # name matching ([A-Z][a-z]+), we build a character-class pattern for the role string.
    def extract_person(role_str: str, full_text: str) -> str:
        # e.g., "Seller" -> "[Ss][Ee][Ll][Ll][Ee][Rr]"
        role_pattern = "".join(f"[{c.lower()}{c.upper()}]" for c in role_str)

        # Case 1: "Name (Role)" or "Name ( Role )"
        # Uses [ \t] instead of \s to strictly PREVENT newline leakage across lines!
        pattern_before = rf'\b([A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)*)[ \t]*\(\s*{role_pattern}\s*\)'
        match = re.search(pattern_before, full_text)
        if match:
            return match.group(1).strip()

        # Case 2: "Name is the Role" or "Name as Role"
        pattern_role_desc = rf'\b([A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)*)[ \t]+(?:is[ \t]+the|as|the)[ \t]+{role_pattern}\b'
        match = re.search(pattern_role_desc, full_text)
        if match:
            return match.group(1).strip()
            
        # Case 3: "Name Role" (e.g., "Ramesh Kumar Seller")
        pattern_adjacent = rf'\b([A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)*)[ \t]+{role_pattern}\b'
        match = re.search(pattern_adjacent, full_text)
        if match:
            return match.group(1).strip()

        # Case 4: "Role: Name" or "Role - Name" or "Role Name"
        pattern_after = rf'\b{role_pattern}\b[^a-zA-Z0-9\n]*(?:is|the|:|\-)*[ \t]*([A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+)*)'
        match = re.search(pattern_after, full_text)
        if match:
            val = match.group(1).strip()
            words = val.split()
            if words and words[0].lower() in ('and', 'between', 'the', 'of', 'is', 'at'):
                if len(words) > 1:
                    return " ".join(words[1:])
            return val
            
        return "Unknown"

    # --- Confidence calibration based on text source ---
    # EXIF-extracted text has lower inherent reliability (it's an embedded label,
    # not actual OCR of visible document text). PDF native text is most reliable.
    # Short text (< 50 chars) also reduces confidence — likely partial/truncated.
    text_len = len(text.strip())
    if text_source == "pdf" and text_len > 100:
        base_conf_high, base_conf_low = 0.95, 0.65
    elif text_source == "tesseract" and text_len > 100:
        base_conf_high, base_conf_low = 0.88, 0.55
    elif text_source == "exif":
        # EXIF is a metadata field, not real OCR — lower trust
        base_conf_high, base_conf_low = 0.72, 0.40
    else:
        # Short or unknown source
        base_conf_high, base_conf_low = 0.60, 0.35

    # --- Robust Extraction & Validation Wrapper ---
    # Generates deterministic confidence scores and validation status to prevent hallucinations.
    def validate_entity(val: str, conf_high: float = 0.95, conf_low: float = 0.45) -> dict:
        if not val or val.strip().lower() in ("unknown", "none", "", "n/a"):
            return {
                "value": "Not Detected",
                "confidence": 0.0,
                "status": "Not Detected"
            }
        
        # Sanity Check: Remove hallucinations (e.g., single letter words or huge sentences)
        val_clean = val.strip()
        word_count = len(val_clean.split())
        
        # If the extracted value is a massive chunk of text, it's likely a wrong clause fragment
        if word_count > 5:
            return {
                "value": "Unavailable (Low Confidence)",
                "confidence": 0.2,
                "status": "Low Confidence"
            }
            
        # If it's a short placeholder or single-word garbage
        if len(val_clean) < 3:
            return {
                "value": "Unavailable",
                "confidence": 0.1,
                "status": "Low Confidence"
            }

        # Set confidence based on clean matching
        confidence = conf_high if word_count <= 4 else conf_low
        status = "Verified" if confidence >= 0.8 else "Low Confidence"
        
        return {
            "value": val_clean,
            "confidence": confidence,
            "status": status
        }

    raw_survey = survey_match.group(2).strip() if survey_match else "Unknown"
    raw_date = date_match.group(1) if date_match else "Unknown"
    raw_buyer = extract_person("Buyer", text)
    raw_seller = extract_person("Seller", text)

    results["extracted_entities"] = {
        "survey_number": validate_entity(raw_survey, conf_high=base_conf_high, conf_low=base_conf_low),
        "date": validate_entity(raw_date, conf_high=base_conf_high, conf_low=base_conf_low),
        "buyer": validate_entity(raw_buyer, conf_high=base_conf_high, conf_low=base_conf_low),
        "seller": validate_entity(raw_seller, conf_high=base_conf_high, conf_low=base_conf_low),
    }

    # --- Anomaly Detection ---
    if results["extracted_entities"]["survey_number"]["status"] == "Not Detected":
        results["is_suspicious"] = True
        results["reasons"].append("NLP: Standard survey number format not detected in document.")

    return results
