import os
from PIL import Image, ImageDraw, ImageFont, ExifTags
import numpy as np

def create_base_document(text, filename, add_noise=False, fraud_exif=False):
    # Create a simple white image
    width, height = 800, 1000
    img = Image.new('RGB', (width, height), color='white')
    d = ImageDraw.Draw(img)
    
    # Try to use a default font, otherwise use whatever PIL has
    try:
        font = ImageFont.truetype("arial.ttf", 36)
        header_font = ImageFont.truetype("arial.ttf", 54)
    except:
        font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        
    d.text((250, 100), "GOVERNMENT OF INDIA", fill=(0,0,0), font=header_font)
    d.text((280, 170), "SALE DEED", fill=(50,50,50), font=header_font)
    
    # Write main text
    y_text = 300
    for line in text.split('\n'):
        d.text((100, y_text), line, fill=(0,0,0), font=font)
        y_text += 60
        
    d.text((100, 800), "Signature:", fill=(0,0,0), font=font)
    d.text((150, 850), "X ___________________", fill=(0,0,200), font=font)
    
    # Simulate Forgery (Copy-Move/Splicing) for Vision ELA
    if add_noise:
        # Paste a slightly lower quality/noisy patch over the signature to trigger ELA
        patch = np.random.randint(200, 255, (100, 300, 3), dtype=np.uint8)
        patch_img = Image.fromarray(patch)
        img.paste(patch_img, (150, 830))
        d.text((150, 850), "X _Forged_Sig_________", fill=(200,0,0), font=font)
        
    # EXIF manipulation
    exif_dict = img.getexif()
    
    # Store the GROUND TRUTH text layer in the EXIF 'ImageDescription' tag (270)
    # This mimics advanced scanning devices that embed embedded OCR metadata into file headers,
    # and allows our Forensic Inspector to physically read it from the file byte stream.
    exif_dict[270] = text
    
    if fraud_exif:
        # 305 is the EXIF tag for 'Software'
        exif_dict[305] = "Adobe Photoshop 2024"
        
    img.save(filename, "JPEG", quality=95, exif=exif_dict)
    
    # If adding noise, re-save the image multiple times to create compression variance
    if add_noise:
        # Load and resave at different quality to simulate someone splicing a screenshot
        temp = Image.open(filename)
        # Make sure to maintain the EXIF dictionary including text layer
        temp.save(filename, "JPEG", quality=70, exif=exif_dict)
        
    print(f"Generated {filename}")

if __name__ == "__main__":
    # Ensure public folder exists so frontend can fetch them
    output_dir = "../../frontend/public/samples"
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Clean Scenario
    clean_text = "Buyer: Arjun Patel\nSeller: Vani Property Developers\nSurvey No: SY-102\nDate: 12-03-2024\n\nThis deed represents a lawful \ntransfer of property."
    create_base_document(clean_text, os.path.join(output_dir, "clean_deed.jpg"))
    
    # 2. Forged Scenario (Triggers ELA & EXIF Forensics)
    forged_text = "Buyer: Arjun Patel\nSeller: Vani Property Developers\nSurvey No: SY-102\nDate: 12-03-2024\n\nThis deed represents a lawful \ntransfer of property."
    create_base_document(forged_text, os.path.join(output_dir, "forged_deed.jpg"), add_noise=True, fraud_exif=True)
    
    # 3. Fraud Ring Scenario (Triggers Graph Intelligence)
    fraud_text = "Buyer: Suresh Holdings LLC\nSeller: Alpha Shell Corp\nSurvey No: SY-999\nDate: 01-01-2024\n\nHigh risk transaction involving \nknown shell entities."
    create_base_document(fraud_text, os.path.join(output_dir, "fraud_ring_deed.jpg"))
    
    print("Synthetic document generation complete. Files saved to frontend/public/samples/")
