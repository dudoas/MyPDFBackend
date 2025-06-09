import io
import base64
import os
from flask import Flask, request, jsonify, Response, send_file
from pikepdf import Pdf, Page, Image
from PIL import Image as PILImage # Import Pillow for image manipulation
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    """Simple home route to confirm the backend server is running."""
    return "PDF Processing Backend (Pikepdf & PyMuPDF with Enhanced Compression) is running!"

@app.route('/compress-pdf', methods=['POST'])
def compress_pdf():
    """
    API endpoint to receive a PDF file (base64 encoded), compress it using pikepdf,
    and return the compressed PDF (also base64 encoded).
    This version includes image downsampling.
    """
    try:
        data = request.get_json()
        if not data or 'pdfFileBase64' not in data:
            return jsonify({'error': 'No PDF file data provided'}), 400

        pdf_file_base64 = data['pdfFileBase64']
        original_filename = data.get('fileName', 'document.pdf')
        compression_level_hint = data.get('compressionLevel', 'recommended')

        pdf_bytes = base64.b64decode(pdf_file_base64)
        original_pdf_stream = io.BytesIO(pdf_bytes)

        # Open the PDF using pikepdf
        pdf = Pdf.open(original_pdf_stream)

        # Define compression parameters based on the selected level
        # target_dpi: Lower DPI means more aggressive downsampling (smaller image size, lower quality)
        # jpeg_quality: Lower quality means more compression for JPEG images
        if compression_level_hint == 'less':
            target_dpi = 300 # Keep original resolution for higher quality (or slightly reduce)
            jpeg_quality = 85 # High quality JPEG
        elif compression_level_hint == 'extreme':
            target_dpi = 72 # Very aggressive downsampling for max compression
            jpeg_quality = 10 # Very low quality JPEG
        else: # 'recommended'
            target_dpi = 150 # Moderate downsampling
            jpeg_quality = 50 # Moderate quality JPEG

        # Iterate through all pages and images to apply compression
        for page in pdf.pages:
            for image in page.images:
                img_obj = pdf.get_object(image)
                
                # Check if it's an image object and if we can convert it to PIL image
                if img_obj.Type == '/XObject' and img_obj.Subtype == '/Image':
                    try:
                        pil_image = img_obj.as_pil_image()
                        
                        original_width, original_height = pil_image.size
                        
                        # Calculate new dimensions based on target DPI
                        # Assume original image was at 72 DPI for calculation of scale
                        # This is an approximation as true DPI might vary.
                        scale_factor_width = target_dpi / 72.0
                        scale_factor_height = target_dpi / 72.0

                        # Ensure new_width and new_height are at least 1 pixel
                        new_width = max(1, int(original_width * (target_dpi / (img_obj.Width if hasattr(img_obj, 'Width') else 72))))
                        new_height = max(1, int(original_height * (target_dpi / (img_obj.Height if hasattr(img_obj, 'Height') else 72))))

                        # To prevent excessive upscaling if target_dpi is very high and original image is low res.
                        # Only downsample or keep original size.
                        new_width = min(original_width, new_width)
                        new_height = min(original_height, new_height)

                        # Resize the image if new dimensions are smaller
                        if new_width < original_width or new_height < original_height:
                            pil_image = pil_image.resize((new_width, new_height), PILImage.LANCZOS) # LANCZOS for high quality downsampling
                        
                        # Convert to RGB if not already (important for JPEG saving)
                        if pil_image.mode != 'RGB':
                            pil_image = pil_image.convert('RGB')

                        # Save the recompressed image back to the PDF object
                        img_obj.write(pil_image, file_format='jpeg', q=jpeg_quality)

                    except Exception as img_err:
                        app.logger.warning(f"Warning: Could not re-compress image (possibly non-standard format) on page {page.index + 1}: {img_err}")
            
            # Also apply general content stream compression for text/line art
            # This is less effective than image compression for photo-heavy PDFs
            page.compress_content_streams()

        # Try to add overall compression filter, which might help for text/vector data.
        # This can sometimes cause issues with certain PDF viewers if not correctly handled.
        # It's less crucial if image compression is aggressive.
        pdf.add_compression()

        compressed_pdf_stream = io.BytesIO()
        pdf.save(compressed_pdf_stream)
        compressed_pdf_stream.seek(0)

        compressed_pdf_base64 = base64.b64encode(compressed_pdf_stream.getvalue()).decode('utf-8')

        name, ext = os.path.splitext(original_filename)
        compressed_filename = f"{name}_compressed{ext}"

        return jsonify({
            'body': compressed_pdf_base64,
            'isBase64Encoded': True,
            'fileName': compressed_filename,
            'originalSize': len(pdf_bytes),
            'compressedSize': len(compressed_pdf_stream.getvalue())
        }), 200

    except Exception as e:
        app.logger.error(f"Error compressing PDF: {e}", exc_info=True)
        return jsonify({'error': f'Failed to compress PDF: {str(e)}'}), 500

@app.route('/pdf-to-text', methods=['POST'])
def pdf_to_text():
    """
    API endpoint to receive a PDF file (base64 encoded), extract text from it
    using PyMuPDF, and return the extracted text (base64 encoded).
    """
    try:
        data = request.get_json()
        if not data or 'pdfFileBase64' not in data:
            return jsonify({'error': 'No PDF file data provided'}), 400

        pdf_file_base64 = data['pdfFileBase64']
        original_filename = data.get('fileName', 'document.pdf')

        pdf_bytes = base64.b64decode(pdf_file_base64)
        
        # Open the PDF document from bytes using PyMuPDF (fitz)
        import fitz # Importing here to ensure it's loaded only when needed
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        extracted_text = ""
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            extracted_text += page.get_text("text") 
        
        doc.close()

        name, ext = os.path.splitext(original_filename)
        text_filename = f"{name}_extracted.txt"

        text_base64 = base64.b64encode(extracted_text.encode('utf-8')).decode('utf-8')

        return jsonify({
            'fileContentBase64': text_base64,
            'fileName': text_filename,
            'mimeType': 'text/plain'
        }), 200

    except Exception as e:
        app.logger.error(f"Error extracting text from PDF: {e}", exc_info=True)
        return jsonify({'error': f'Failed to extract text from PDF: {str(e)}'}), 500

if __name__ == '__main__':
    # This block is for local development only.
    # On Render.com, gunicorn (specified in Procfile) runs the app.
    app.run(debug=True, port=int(os.environ.get('PORT', 5000)))
