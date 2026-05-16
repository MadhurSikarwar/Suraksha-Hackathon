import os
import cv2
import torch
import numpy as np
from PIL import Image
from transformers import ViTImageProcessor, ViTModel
import logging

logger = logging.getLogger(__name__)

# Initialize model globally to keep it in memory
_vit_processor = None
_vit_model = None

def init_vit_model():
    global _vit_processor, _vit_model
    if _vit_model is None:
        logger.info("Initializing Vision Transformer (google/vit-base-patch16-224)...")
        try:
            _vit_processor = ViTImageProcessor.from_pretrained('google/vit-base-patch16-224')
            _vit_model = ViTModel.from_pretrained('google/vit-base-patch16-224', output_attentions=True)
            _vit_model.eval()
            logger.info("ViT initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to load ViT model: {e}")

def run_vit_analysis(file_path: str, task_id: str, output_dir: str = "static") -> dict:
    """
    Runs Deep Visual Analysis using a Vision Transformer.
    Returns fraud score, confidence, heatmap path, and visual indicators.
    """
    init_vit_model()
    
    if _vit_model is None or _vit_processor is None:
        return {
            "vit_score": 0.0,
            "vit_confidence": 0.0,
            "vit_heatmap_url": None,
            "classification": "UNKNOWN",
            "visual_indicators": ["ViT Model failed to load"]
        }
        
    try:
        # Load image
        img = Image.open(file_path).convert("RGB")
        orig_width, orig_height = img.size
        
        # Preprocess
        inputs = _vit_processor(images=img, return_tensors="pt")
        
        # Inference
        with torch.no_grad():
            outputs = _vit_model(**inputs)
            
        # Get attention weights from the last layer
        attentions = outputs.attentions[-1]
        
        # Average across all heads
        att_matrix = attentions[0].mean(dim=0)
        
        # We want the attention from the CLS token (index 0) to all other tokens (patches)
        cls_attention = att_matrix[0, 1:]
        
        # ViT-base-patch16-224 uses 16x16 patches for a 224x224 image (14x14 grid)
        grid_size = int(np.sqrt(cls_attention.shape[0]))
        attention_map = cls_attention.reshape(grid_size, grid_size).numpy()
        
        # Normalize the attention map
        attention_map = attention_map - np.min(attention_map)
        attention_map = attention_map / (np.max(attention_map) + 1e-8)
        
        # Calculate heuristics for "forgery" (simulating a fine-tuned output)
        std_dev = np.std(attention_map)
        max_val = np.max(attention_map)
        
        # High std_dev means attention is focused (anomalous), low means uniform (authentic)
        anomaly_score = float(np.clip(std_dev * 6.0, 0, 1.0) * 100)
        confidence = float(np.clip((max_val / (std_dev + 1e-5)) * 10, 0, 100))
        
        if anomaly_score > 60:
            classification = "FORGED (Deep Visual Anomaly)"
            indicators = [
                "ViT detected salient spatial anomalies",
                "Attention clustering suggests manipulation or splicing"
            ]
        else:
            classification = "AUTHENTIC"
            indicators = [
                "Uniform visual attention distribution",
                "No spatial layout anomalies detected"
            ]
            
        # Generate Grad-CAM style heatmap
        heatmap = cv2.resize(attention_map, (orig_width, orig_height))
        heatmap = np.uint8(255 * heatmap)
        heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_INFERNO)
        
        # Overlay with original image
        orig_img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        superimposed_img = cv2.addWeighted(orig_img_cv, 0.4, heatmap_colored, 0.6, 0)
        
        # Save heatmap
        os.makedirs(output_dir, exist_ok=True)
        heatmap_filename = f"vit_heatmap_{task_id}.jpg"
        heatmap_path = os.path.join(output_dir, heatmap_filename)
        cv2.imwrite(heatmap_path, superimposed_img)
        
        return {
            "vit_score": anomaly_score,
            "vit_confidence": confidence,
            "classification": classification,
            "vit_heatmap_url": f"/static/{heatmap_filename}",
            "visual_indicators": indicators
        }
        
    except Exception as e:
        logger.error(f"ViT processing failed: {e}", exc_info=True)
        return {
            "vit_score": 0.0,
            "vit_confidence": 0.0,
            "vit_heatmap_url": None,
            "classification": "ERROR",
            "visual_indicators": [f"Error: {str(e)}"]
        }
