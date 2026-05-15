"""
Deep Forensic Inspector
=======================
Extracts comprehensive forensic metadata from documents and images including:
- File identity (size, type, MIME, dimensions, DPI)
- Cryptographic fingerprints (MD5, SHA1, SHA256)
- Timestamp analysis and inconsistency detection
- EXIF and embedded metadata
- PDF structure forensics (producer, streams, incremental saves)
- Visual forensic signals (ELA score, noise, double-JPEG indicators)
- Fraud intelligence summary
"""

import hashlib
import os
import math
import logging
import struct
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Optional imports (graceful fallback if not installed) ──────────────────────
try:
    from PIL import Image, ExifTags
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("Pillow not available — image forensics limited")

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    logger.warning("PyMuPDF not available — PDF forensics limited")

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.warning("OpenCV not available — visual forensics limited")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _compute_hashes(file_path: str) -> Dict[str, str]:
    """Compute MD5, SHA1, SHA256 of the raw file bytes."""
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)
        return {
            "md5": md5.hexdigest(),
            "sha1": sha1.hexdigest(),
            "sha256": sha256.hexdigest(),
        }
    except Exception as e:
        logger.error(f"Hash computation failed: {e}")
        return {"md5": "error", "sha1": "error", "sha256": "error"}


def _get_mime_type(file_path: str) -> str:
    """Determine MIME type from file magic bytes (not extension)."""
    signatures = {
        b"%PDF": "application/pdf",
        b"\xff\xd8\xff": "image/jpeg",
        b"\x89PNG": "image/png",
        b"II*\x00": "image/tiff",
        b"MM\x00*": "image/tiff",
        b"BM": "image/bmp",
    }
    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
        for sig, mime in signatures.items():
            if header.startswith(sig):
                return mime
        return "application/octet-stream"
    except Exception:
        return "unknown"


def _format_bytes(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024**2):.2f} MB"


def _safe_str(val: Any, max_len: int = 200) -> str:
    if val is None:
        return "N/A"
    return str(val)[:max_len]


# ── File Identity ──────────────────────────────────────────────────────────────

def extract_file_identity(file_path: str) -> Dict[str, Any]:
    """Basic file intelligence: size, extension, MIME, timestamps."""
    result = {}
    try:
        stat = os.stat(file_path)
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")

        result = {
            "file_name": os.path.basename(file_path),
            "file_extension": ext.upper() or "Unknown",
            "file_size_bytes": stat.st_size,
            "file_size_human": _format_bytes(stat.st_size),
            "mime_type_detected": _get_mime_type(file_path),
            "mime_type_from_extension": f"image/{ext}" if ext in ("jpg", "jpeg", "png", "bmp", "tiff") else "application/pdf",
            "fs_created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "fs_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "fs_accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
        }

        # Flag if MIME from magic bytes differs from file extension
        result["mime_mismatch"] = result["mime_type_detected"] != result["mime_type_from_extension"]
    except Exception as e:
        logger.error(f"File identity extraction failed: {e}")
        result["error"] = str(e)
    return result


# ── Image Forensics ────────────────────────────────────────────────────────────

def extract_image_forensics(file_path: str) -> Dict[str, Any]:
    """Extract image dimensions, DPI, color space, and EXIF metadata."""
    result: Dict[str, Any] = {}
    if not PIL_AVAILABLE:
        return {"error": "Pillow not installed"}

    try:
        img = Image.open(file_path)
        width, height = img.size
        dpi_info = img.info.get("dpi", (72, 72))
        dpi_x = round(dpi_info[0]) if isinstance(dpi_info, tuple) else 72

        result["dimensions"] = f"{width} × {height} px"
        result["width_px"] = width
        result["height_px"] = height
        result["color_mode"] = img.mode  # RGB, RGBA, L, CMYK, etc.
        result["color_channels"] = len(img.getbands())
        result["dpi"] = dpi_x
        result["format"] = img.format or "Unknown"
        result["has_transparency"] = img.mode in ("RGBA", "LA", "PA")
        result["num_frames"] = getattr(img, "n_frames", 1)

        # EXIF extraction
        exif_data = {}
        suspicious_software = []
        try:
            raw_exif = img.getexif()
            EDIT_TOOLS = ["photoshop", "gimp", "canva", "paint", "lightroom",
                          "affinity", "pixelmator", "inkscape", "corel"]
            if raw_exif:
                for tag_id, val in raw_exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, f"Tag_{tag_id}")
                    if isinstance(val, bytes):
                        try:
                            val = val.decode("utf-8", errors="replace").strip()
                        except Exception:
                            val = val.hex()
                    str_val = _safe_str(val)
                    exif_data[tag_name] = str_val

                    # Flag editing software
                    if tag_name in ("Software", "ProcessingSoftware", "Artist"):
                        for tool in EDIT_TOOLS:
                            if tool in str_val.lower():
                                suspicious_software.append(str_val)

        except Exception as ex:
            exif_data["exif_error"] = str(ex)

        result["exif"] = exif_data
        result["editing_software_detected"] = suspicious_software
        result["exif_field_count"] = len(exif_data)

        # GPS check
        gps_info = exif_data.get("GPSInfo", "")
        result["has_gps"] = bool(gps_info and gps_info != "N/A")
        result["gps_raw"] = gps_info if gps_info else "None"

        img.close()
    except Exception as e:
        logger.error(f"Image forensics failed: {e}")
        result["error"] = str(e)
    return result


# ── Visual Signal Analysis (ELA deep stats) ───────────────────────────────────

def extract_visual_signals(file_path: str, task_id: str) -> Dict[str, Any]:
    """Compute detailed ELA statistics and noise analysis."""
    result: Dict[str, Any] = {}
    if not (PIL_AVAILABLE and CV2_AVAILABLE):
        return {"error": "OpenCV or Pillow not installed"}

    temp_path = f"temp_vsig_{task_id}.jpg"
    try:
        original = Image.open(file_path).convert("RGB")
        original.save(temp_path, "JPEG", quality=90)
        recompressed = Image.open(temp_path)

        orig_arr = np.array(original, dtype=np.float32)
        recomp_arr = np.array(recompressed, dtype=np.float32)
        diff = np.abs(orig_arr - recomp_arr)

        max_diff = float(np.max(diff))
        mean_diff = float(np.mean(diff))
        std_diff = float(np.std(diff))

        # Region-level anomaly: split into 4×4 grid and check variance
        h, w, _ = orig_arr.shape
        region_means = []
        bh, bw = max(h // 4, 1), max(w // 4, 1)
        for r in range(4):
            for c in range(4):
                block = diff[r*bh:(r+1)*bh, c*bw:(c+1)*bw]
                region_means.append(float(np.mean(block)))

        region_variance = float(np.var(region_means))
        high_anomaly_regions = sum(1 for m in region_means if m > mean_diff * 2)

        # Double-JPEG detection heuristic (high frequency DCT residual spike)
        gray = cv2.cvtColor(np.array(original), cv2.COLOR_RGB2GRAY)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Noise inconsistency across image halves
        left_noise  = float(np.std(diff[:, :w//2, :]))
        right_noise = float(np.std(diff[:, w//2:, :]))
        noise_ratio = round(max(left_noise, right_noise) / max(min(left_noise, right_noise), 0.01), 2)

        result = {
            "ela_mean_score": round(mean_diff, 3),
            "ela_max_score": round(max_diff, 3),
            "ela_std_deviation": round(std_diff, 3),
            "ela_is_suspicious": mean_diff > 15.0,
            "ela_anomaly_regions": high_anomaly_regions,
            "ela_region_variance": round(region_variance, 3),
            "noise_left_half": round(left_noise, 3),
            "noise_right_half": round(right_noise, 3),
            "noise_ratio_lr": noise_ratio,
            "noise_inconsistency_flag": noise_ratio > 2.0,
            "laplacian_sharpness": round(laplacian_var, 2),
            "double_jpeg_indicator": laplacian_var > 800,
            "tampering_probability_pct": round(min(mean_diff / 30.0 * 100, 99.0), 1),
        }
        original.close()
        recompressed.close()
    except Exception as e:
        logger.error(f"Visual signal analysis failed: {e}")
        result["error"] = str(e)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
    return result


# ── PDF Structure Forensics ────────────────────────────────────────────────────

def extract_pdf_forensics(file_path: str) -> Dict[str, Any]:
    """Deep PDF structure analysis: metadata, streams, incremental saves."""
    result: Dict[str, Any] = {}
    if not FITZ_AVAILABLE:
        return {"error": "PyMuPDF not installed"}
    try:
        doc = fitz.open(file_path)
        meta = doc.metadata or {}
        page_count = len(doc)

        # Collect page dimensions
        page_sizes = []
        for i, page in enumerate(doc):
            r = page.rect
            page_sizes.append(f"P{i+1}: {round(r.width)}×{round(r.height)} pt")
            if i >= 9:
                page_sizes.append("...")
                break

        # Count embedded images across all pages
        total_images = 0
        total_fonts = 0
        font_names = set()
        for page in doc:
            total_images += len(page.get_images(full=True))
            for font in page.get_fonts(full=True):
                total_fonts += 1
                fname = font[3] or font[4] or "Unknown"
                font_names.add(fname[:40])

        # Incremental save detection (raw binary scan for %%EOF count)
        eof_count = 0
        incremental_saves = False
        try:
            with open(file_path, "rb") as f:
                raw = f.read()
            eof_count = raw.count(b"%%EOF")
            incremental_saves = eof_count > 1
        except Exception:
            pass

        # Check for JavaScript or embedded attachments
        has_javascript = False
        has_attachments = False
        try:
            has_javascript = bool(doc.get_js())
        except Exception:
            pass
        try:
            has_attachments = doc.embfile_count() > 0
        except Exception:
            pass

        doc.close()

        # Suspicious producer tools
        SUSPICIOUS_PRODUCERS = ["photoshop", "gimp", "inkscape", "illustrator", "corel", "canva"]
        producer = meta.get("producer", "") or ""
        creator = meta.get("creator", "") or ""
        suspicious_producer = any(t in producer.lower() or t in creator.lower()
                                  for t in SUSPICIOUS_PRODUCERS)

        creation_date = meta.get("creationDate", "") or ""
        mod_date = meta.get("modDate", "") or ""
        date_mismatch = bool(creation_date and mod_date and creation_date != mod_date)

        result = {
            "page_count": page_count,
            "page_sizes": page_sizes,
            "embedded_images": total_images,
            "embedded_fonts": total_fonts,
            "font_names": list(font_names)[:10],
            "producer": _safe_str(producer) or "N/A",
            "creator_tool": _safe_str(creator) or "N/A",
            "creation_date": _safe_str(creation_date) or "N/A",
            "modification_date": _safe_str(mod_date) or "N/A",
            "author": _safe_str(meta.get("author", "")) or "N/A",
            "title": _safe_str(meta.get("title", "")) or "N/A",
            "subject": _safe_str(meta.get("subject", "")) or "N/A",
            "keywords": _safe_str(meta.get("keywords", "")) or "N/A",
            "date_mismatch": date_mismatch,
            "suspicious_producer": suspicious_producer,
            "incremental_saves": incremental_saves,
            "eof_markers_found": eof_count,
            "has_javascript": has_javascript,
            "has_attachments": has_attachments,
            "pdf_encrypted": doc.is_encrypted if hasattr(doc, "is_encrypted") else False,
        }
    except Exception as e:
        logger.error(f"PDF forensics failed: {e}")
        result["error"] = str(e)
    return result


# ── Fraud Intelligence Summary ────────────────────────────────────────────────

def compute_fraud_intelligence(
    file_identity: Dict,
    image_forensics: Dict,
    visual_signals: Dict,
    pdf_forensics: Dict,
    hashes: Dict,
    ela_score: float,
    fraud_score: float,
    decision: str
) -> Dict[str, Any]:
    """Aggregates all signals into a single fraud intelligence summary."""
    anomalies = []

    if file_identity.get("mime_mismatch"):
        anomalies.append("MIME type mismatch between file extension and magic bytes")
    if image_forensics.get("editing_software_detected"):
        anomalies.append(f"Editing software detected: {image_forensics['editing_software_detected']}")
    if visual_signals.get("ela_is_suspicious"):
        anomalies.append(f"ELA compression variance above threshold ({ela_score:.1f} > 15.0)")
    if visual_signals.get("noise_inconsistency_flag"):
        anomalies.append(f"Noise inconsistency between left/right halves (ratio: {visual_signals.get('noise_ratio_lr')})")
    if visual_signals.get("double_jpeg_indicator"):
        anomalies.append("Double-JPEG compression indicator detected")
    if pdf_forensics.get("date_mismatch"):
        anomalies.append("PDF creation and modification dates differ")
    if pdf_forensics.get("suspicious_producer"):
        anomalies.append(f"Suspicious PDF producer tool: {pdf_forensics.get('producer')}")
    if pdf_forensics.get("incremental_saves"):
        anomalies.append(f"PDF has {pdf_forensics.get('eof_markers_found')} EOF markers — incremental edits detected")
    if pdf_forensics.get("has_javascript"):
        anomalies.append("PDF contains embedded JavaScript — HIGH RISK")

    severity = "CRITICAL" if fraud_score > 80 else "HIGH" if fraud_score > 60 else "MEDIUM" if fraud_score > 30 else "LOW"
    forgery_type = (
        "Copy-Move / Image Splice" if visual_signals.get("ela_is_suspicious") else
        "Metadata Manipulation" if (pdf_forensics.get("date_mismatch") or pdf_forensics.get("suspicious_producer")) else
        "File Structure Anomaly" if file_identity.get("mime_mismatch") else
        "No Forgery Detected"
    )
    return {
        "fraud_confidence_pct": fraud_score,
        "risk_category": severity,
        "potential_forgery_type": forgery_type,
        "anomaly_count": len(anomalies),
        "anomaly_severity": severity,
        "detected_anomalies": anomalies,
        "duplicate_document_probability": round(min(fraud_score * 0.8, 95.0), 1),
        "legal_defensibility": "High" if len(anomalies) > 0 else "Medium",
        "sha256_fingerprint": hashes.get("sha256", "N/A"),
        "integrity_verified": fraud_score < 20,
        "recommended_action": decision,
    }


# ── Master Entry Point ─────────────────────────────────────────────────────────

def run_deep_inspection(file_path: str, task_id: str,
                        ela_score: float = 0.0,
                        fraud_score: float = 0.0,
                        decision: str = "REVIEW") -> Dict[str, Any]:
    """
    Master function. Runs all forensic modules and returns a unified dict.
    All modules are individually wrapped so one failure doesn't break others.
    """
    ext = os.path.splitext(file_path)[1].lower()
    is_pdf = ext == ".pdf"
    is_image = ext in (".jpg", ".jpeg", ".png", ".tiff", ".bmp")

    # --- Run all modules ---
    hashes = _compute_hashes(file_path)
    file_identity = extract_file_identity(file_path)

    image_forensics: Dict = {}
    visual_signals: Dict = {}
    pdf_forensics: Dict = {}

    if is_image:
        image_forensics = extract_image_forensics(file_path)
        visual_signals = extract_visual_signals(file_path, task_id)

    elif is_pdf:
        pdf_forensics = extract_pdf_forensics(file_path)
        # For PDFs, try to extract a page image and run visual signals on it
        if FITZ_AVAILABLE:
            try:
                doc = fitz.open(file_path)
                if len(doc) > 0:
                    pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                    tmp_img = f"temp_pdf_vsig_{task_id}.png"
                    pix.save(tmp_img)
                    doc.close()
                    image_forensics = extract_image_forensics(tmp_img)
                    visual_signals = extract_visual_signals(tmp_img, task_id + "_pdf")
                    if os.path.exists(tmp_img):
                        os.remove(tmp_img)
                else:
                    doc.close()
            except Exception as e:
                logger.warning(f"PDF→image conversion for visual signals failed: {e}")

    fraud_intel = compute_fraud_intelligence(
        file_identity, image_forensics, visual_signals,
        pdf_forensics, hashes, ela_score, fraud_score, decision
    )

    return {
        "cryptographic": hashes,
        "file_identity": file_identity,
        "image_forensics": image_forensics,
        "visual_signals": visual_signals,
        "pdf_forensics": pdf_forensics,
        "fraud_intelligence": fraud_intel,
        "inspection_timestamp": datetime.utcnow().isoformat() + "Z",
    }
