# app.py
from flask import Flask, request, jsonify, send_file
from io import BytesIO
import base64
import os
import pikepdf # The powerful PDF manipulation library
import fitz # PyMuPDF for text extraction
from flask_cors import CORS # To allow cross-origin requests from your frontend

app = Flask(__name__)
# Enable CORS for all routes, allowing requests from any origin ('*')
CORS(app)

@app.route('/')
def home():
    """
    Simple home route to confirm the backend server is running.
    This message will appear when you visit your Render.com URL directly.
    """
    return "PDF Processing Backend (Pikepdf & PyMuPDF) is running!"

@app.route('/compress-pdf', methods=['POST'])
def compress_pdf():
    """
    API endpoint to receive a PDF file (base64 encoded), compress it using pikepdf,
    and return the compressed PDF (also base64 encoded).
    """
    try:
        data = request.get_json()
        if not data or 'pdfFileBase64' not in data:
            return jsonify({'error': 'No PDF file data provided'}), 400

        pdf_file_base64 = data['pdfFileBase64']
        original_filename = data.get('fileName', 'document.pdf')
        
        # Determine compression level based on hint from frontend
        compression_level_hint = data.get('compressionLevel', 'recommended')

        pdf_bytes = base64.b64decode(pdf_file_base64)
        original_pdf_stream = BytesIO(pdf_bytes)

        # Open the PDF using pikepdf
        pdf = pikepdf.open(original_pdf_stream)

        # Set JPEG quality based on compression level hint
        jpeg_quality = 0.75 # Default for 'recommended'
        if compression_level_hint == 'less':
            jpeg_quality = 0.90 # Higher quality, less compression
        elif compression_level_hint == 'extreme':
            jpeg_quality = 0.50 # Lower quality, more compression

        # Iterate through all images in the PDF and recompress them
        # This is the primary mechanism for file size reduction
        for page in pdf.pages:
            for image in page.images:
                img_obj = pdf.get_object(image)
                # Ensure it's an image object and recompress as JPEG
                if img_obj.Type == '/XObject' and img_obj.Subtype == '/Image':
                    try:
                        # Convert to PIL Image and then write back as JPEG with specified quality
                        pil_image = img_obj.as_pil_image()
                        img_obj.write(pil_image, file_format='jpeg', q=jpeg_quality)
                    except Exception as img_err:
                        # Log if an image cannot be processed, but don't fail the whole PDF
                        print(f"Warning: Could not re-compress image on page {page.index + 1}: {img_err}")
        
        compressed_pdf_stream = BytesIO()
        # Save the modified PDF. q_values applies compression to different filter types.
        pdf.save(compressed_pdf_stream, 
                 q_values={'/FlateDecode': 1.0, '/DCTDecode': jpeg_quality}
                )
        
        # Rewind the stream to the beginning before reading its content
        compressed_pdf_stream.seek(0)

        # Encode the compressed PDF bytes to base64 for sending back to the frontend
        compressed_pdf_base64 = base64.b64encode(compressed_pdf_stream.getvalue()).decode('utf-8')

        # Determine the filename for the compressed PDF
        name, ext = os.path.splitext(original_filename)
        compressed_filename = f"{name}_compressed{ext}"

        # Return the success response with base64 encoded PDF and metadata
        return jsonify({
            'body': compressed_pdf_base64,
            'isBase64Encoded': True, # Indicate that the 'body' content is base64 encoded
            'fileName': compressed_filename,
            'originalSize': len(pdf_bytes),
            'compressedSize': len(compressed_pdf_stream.getvalue())
        }), 200

    except Exception as e:
        # Log the full error traceback for debugging on Render.com logs
        app.logger.error(f"Error compressing PDF: {e}", exc_info=True)
        # Return an error response to the frontend
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

        # Decode the base64 PDF to bytes
        pdf_bytes = base64.b64decode(pdf_file_base64)
        
        # Open the PDF document from bytes using PyMuPDF (fitz)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        extracted_text = ""
        # Iterate through each page and extract text
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            extracted_text += page.get_text() # Get text from the page
        
        doc.close() # Close the document after extraction

        # Determine the filename for the extracted text file
        name, ext = os.path.splitext(original_filename)
        text_filename = f"{name}_extracted.txt"

        # Encode the extracted text to base64 for sending back to the frontend
        text_base64 = base64.b64encode(extracted_text.encode('utf-8')).decode('utf-8')

        # Return the success response with base64 encoded text and metadata
        return jsonify({
            'fileContentBase64': text_base64,
            'fileName': text_filename,
            'mimeType': 'text/plain' # Specify the MIME type for the extracted text
        }), 200

    except Exception as e:
        # Log the full error traceback for debugging on Render.com logs
        app.logger.error(f"Error extracting text from PDF: {e}", exc_info=True)
        # Return an error response to the frontend
        return jsonify({'error': f'Failed to extract text from PDF: {str(e)}'}), 500


if __name__ == '__main__':
    # This block is for local development only.
    # On Render.com, gunicorn (specified in Procfile) runs the app.
    app.run(debug=True, port=int(os.environ.get('PORT', 5000)))
