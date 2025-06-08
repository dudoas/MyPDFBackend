# app.py
from flask import Flask, request, jsonify, send_file
from io import BytesIO
import base64
import os
import pikepdf # The powerful PDF manipulation library
import fitz # PyMuPDF for text extraction
from flask_cors import CORS # To allow cross-origin requests from your frontend

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

@app.route('/')
def home():
    """Simple home route to confirm the server is running."""
    return "PDF Processing Backend (Pikepdf & PyMuPDF) is running!"

@app.route('/compress-pdf', methods=['POST'])
def compress_pdf():
    """
    API endpoint to receive a PDF, compress it using pikepdf, and return the compressed PDF.
    """
    try:
        data = request.get_json()
        if not data or 'pdfFileBase64' not in data:
            return jsonify({'error': 'No PDF file data provided'}), 400

        pdf_file_base64 = data['pdfFileBase64']
        original_filename = data.get('fileName', 'document.pdf')
        
        # Compression level hint from frontend
        compression_level_hint = data.get('compressionLevel', 'recommended')

        pdf_bytes = base64.b64decode(pdf_file_base64)
        original_pdf_stream = BytesIO(pdf_bytes)

        pdf = pikepdf.open(original_pdf_stream)

        jpeg_quality = 0.75 # Default for 'recommended'
        if compression_level_hint == 'less':
            jpeg_quality = 0.90 # Higher quality, less compression
        elif compression_level_hint == 'extreme':
            jpeg_quality = 0.50 # Lower quality, more compression

        # Iterate through all images and apply compression
        for page in pdf.pages:
            for image in page.images:
                img_obj = pdf.get_object(image)
                if img_obj.Type == '/XObject' and img_obj.Subtype == '/Image':
                    # Check if it's already JPEG or similar, and recompress if needed
                    if '/Filter' not in img_obj or img_obj.Filter not in ['/DCTDecode', '/JPXDecode']:
                        img_obj.write(img_obj.as_pil_image(), file_format='jpeg', q=jpeg_quality)
                    elif img_obj.Filter in ['/DCTDecode', '/JPXDecode']:
                         img_obj.write(img_obj.as_pil_image(), file_format='jpeg', q=jpeg_quality)
                    
        compressed_pdf_stream = BytesIO()
        pdf.save(compressed_pdf_stream, 
                 q_values={'/FlateDecode': 1.0, '/DCTDecode': jpeg_quality}
                )
        
        compressed_pdf_stream.seek(0)

        compressed_pdf_base64 = base64.b64encode(compressed_pdf_stream.getvalue()).decode('utf-8')

        name, ext = os.path.splitext(original_filename)
        compressed_filename = f"{name}_pikepdf_compressed{ext}"

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
    API endpoint to receive a PDF and extract text using PyMuPDF.
    This does NOT perform OCR on image-based PDFs.
    """
    try:
        data = request.get_json()
        if not data or 'pdfFileBase64' not in data:
            return jsonify({'error': 'No PDF file data provided'}), 400

        pdf_file_base64 = data['pdfFileBase64']
        original_filename = data.get('fileName', 'document.pdf')

        pdf_bytes = base64.b64decode(pdf_file_base64)
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf") # Open PDF from bytes
        extracted_text = ""
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            extracted_text += page.get_text() # Extract text from page
        
        doc.close() # Close the document

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
    app.run(debug=True, port=5000)
