import fitz  # PyMuPDF
from PIL import Image, ExifTags
import os
from datetime import datetime

def analyze_pdf_metadata(file_path: str):
    """
    Extracts metadata from a PDF file to check for anomalies.
    Common anomalies: CreationDate != ModDate, suspicious Producer software.
    """
    try:
        doc = fitz.open(file_path)
        metadata = doc.metadata
        
        results = {
            "is_suspicious": False,
            "reasons": [],
            "extracted_data": metadata
        }
        
        # Check for producer (tools like Photoshop/GIMP in PDF metadata indicate tampering)
        producer = metadata.get('producer', '').lower()
        creator = metadata.get('creator', '').lower()
        suspicious_tools = ['photoshop', 'gimp', 'illustrator', 'corel']
        
        for tool in suspicious_tools:
            if tool in producer or tool in creator:
                results["is_suspicious"] = True
                results["reasons"].append(f"Suspicious PDF Producer/Creator detected: {tool.capitalize()}")
                
        # Check Date Mismatches (Creation vs Modification)
        creation_date = metadata.get('creationDate', '')
        mod_date = metadata.get('modDate', '')
        
        if creation_date and mod_date and creation_date != mod_date:
            # Usually format is D:YYYYMMDDHHMMSS
            # We can just check if strings differ significantly
            results["is_suspicious"] = True
            results["reasons"].append("PDF Modification date differs from Creation date.")
            
        doc.close()
        return results
        
    except Exception as e:
        return {"is_suspicious": False, "reasons": [f"Failed to parse PDF metadata: {str(e)}"]}

def analyze_image_metadata(file_path: str):
    """
    Extracts EXIF data from images to find hidden software signatures and check physical integrity.
    """
    try:
        image = Image.open(file_path)
        
        # Try standard EXIF and fall back to internal _getexif if needed
        exifdata = image.getexif()
        if not exifdata and hasattr(image, '_getexif'):
            try:
                exifdata = image._getexif()
            except Exception:
                exifdata = None
        
        results = {
            "is_suspicious": False,
            "reasons": [],
            "extracted_data": {}
        }
        
        # Physical integrity check: extreme low resolution gating (prevents spoofing thumbnail docs)
        w, h = image.size
        if w < 200 or h < 200:
            results["is_suspicious"] = True
            results["reasons"].append(f"Sub-threshold resolution ({w}x{h}): Document dimensions too small for genuine financial collateral.")

        if not exifdata:
            return results
            
        for tag_id in exifdata:
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            data = exifdata.get(tag_id)
            if isinstance(data, bytes):
                try:
                    data = data.decode('utf-8', errors='ignore')
                except Exception:
                    data = str(data)
            results["extracted_data"][str(tag)] = str(data)
            
            # Check for editing software signatures
            if str(tag) == 'Software':
                software_val = str(data).lower()
                suspicious_tools = ['photoshop', 'gimp', 'canva', 'paint', 'illustrator', 'acrobat', 'snagit']
                for tool in suspicious_tools:
                    if tool in software_val:
                        results["is_suspicious"] = True
                        results["reasons"].append(f"Forensic Flag: Metadata contains editing software signature ({software_val}).")
            
            # Check for date format anomalies
            if str(tag) in ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']:
                results["extracted_data"]["image_datetime"] = str(data)

        return results
    except Exception as e:
        return {"is_suspicious": False, "reasons": [f"Failed to parse Image metadata: {str(e)}"]}

def extract_metadata(file_path: str):
    """Main routing function based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        return analyze_pdf_metadata(file_path)
    elif ext in ['.jpg', '.jpeg', '.png', '.tiff']:
        return analyze_image_metadata(file_path)
    else:
        return {"is_suspicious": False, "reasons": ["Unsupported file type for metadata forensics."]}
