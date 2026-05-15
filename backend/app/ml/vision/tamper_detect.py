import cv2
import numpy as np
import os
import logging
import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)


def error_level_analysis(image_path: str, task_id: str, quality=90):
    """
    Performs Error Level Analysis (ELA) to detect compressed tampering.
    Uses task_id in temp filename to prevent race conditions in concurrent requests.
    """
    temp_path = f"temp_ela_{task_id}.jpg"
    try:
        original = Image.open(image_path).convert('RGB')

        # Save a temporary re-compressed copy
        original.save(temp_path, 'JPEG', quality=quality)
        recompressed = Image.open(temp_path)

        orig_arr = np.array(original)
        recomp_arr = np.array(recompressed)

        diff_arr = np.abs(orig_arr.astype(np.int16) - recomp_arr.astype(np.int16))

        max_diff = np.max(diff_arr)
        if max_diff == 0:
            max_diff = 1  # prevent division by zero

        ela_arr = (diff_arr / max_diff * 255.0).astype(np.uint8)
        mean_anomaly = float(np.mean(ela_arr))

        # Generate heatmap overlay
        heatmap_img = cv2.applyColorMap(ela_arr, cv2.COLORMAP_JET)
        # BUGFIX: Was cv2.COLORRGB2BGR (invalid constant). Correct is cv2.COLOR_RGB2BGR
        orig_cv = cv2.cvtColor(orig_arr, cv2.COLOR_RGB2BGR)
        overlay = cv2.addWeighted(orig_cv, 0.4, heatmap_img, 0.6, 0)

        os.makedirs("static/heatmaps", exist_ok=True)
        heatmap_filename = f"{task_id}_heatmap.png"
        heatmap_path = os.path.join("static/heatmaps", heatmap_filename)
        cv2.imwrite(heatmap_path, overlay)

        is_suspicious = mean_anomaly > 15.0

        return {
            "is_suspicious": is_suspicious,
            "anomaly_score": round(mean_anomaly, 2),
            "reasons": ["Vision ELA: High compression variance — potential copy-move or splice anomaly."] if is_suspicious else [],
            "heatmap_url": f"/static/heatmaps/{heatmap_filename}"
        }

    except Exception as e:
        logger.error(f"ELA analysis failed for task {task_id}: {e}")
        return {
            "is_suspicious": False,
            "anomaly_score": 0,
            "reasons": [f"Vision ELA skipped (processing error)."],
            "heatmap_url": None
        }
    finally:
        # Always clean up temp recompressed file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def extract_first_image_from_pdf(pdf_path: str, task_id: str):
    """Renders the first page of a PDF to a PNG image for vision analysis."""
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            doc.close()
            return None
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale for higher resolution
        img_path = f"temp_pdf_page_{task_id}.png"
        pix.save(img_path)
        doc.close()
        return img_path
    except Exception as e:
        logger.error(f"PDF page extraction failed: {e}")
        return None


def analyze_visual_tampering(file_path: str, task_id: str):
    """
    Main entry point. Routes to ELA based on file type.
    Handles both image files and PDFs safely.
    """
    ext = os.path.splitext(file_path)[1].lower()
    target_img = file_path
    is_pdf = False

    if ext == '.pdf':
        is_pdf = True
        target_img = extract_first_image_from_pdf(file_path, task_id)

    if not target_img or not os.path.exists(target_img):
        return {
            "is_suspicious": False,
            "reasons": ["Vision layer: Could not extract image for analysis."],
            "heatmap_url": None
        }

    results = error_level_analysis(target_img, task_id)

    # Clean up the temporary PDF page PNG
    if is_pdf and target_img != file_path and os.path.exists(target_img):
        try:
            os.remove(target_img)
        except Exception:
            pass

    return results
