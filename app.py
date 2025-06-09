import io
import base64
import os
import subprocess # For calling external commands like Ghostscript
import tempfile # For creating temporary files safely
from flask import Flask, request, jsonify, Response, send_file
from pikepdf import Pdf, Page, Object, Name
from PIL import Image as PILImage
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    """Simple home route to confirm the backend server is running."""
    return "PDF Processing Backend (Pikepdf & PyMuPDF with Ghostscript Compression) is running!"

@app.route('/compress-pdf', methods=['POST'])
def compress_pdf():
    """
    API endpoint to receive a PDF file (base64 encoded), compress it using Ghostscript,
    and return the compressed PDF (also base64 encoded).
    """
    try:
        data = request.get_json()
        if not data or 'pdfFileBase64' not in data:
            return jsonify({'error': 'No PDF file data provided'}), 400

        pdf_file_base64 = data['pdfFileBase64']
        original_filename = data.get('fileName', 'document.pdf')
        compression_level_hint = data.get('compressionLevel', 'recommended')

        pdf_bytes = base64.b64decode(pdf_file_base64)
        
        # Create temporary input and output files
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_input_pdf:
            temp_input_pdf.write(pdf_bytes)
            temp_input_path = temp_input_pdf.name

        with tempfile.NamedTemporaryFile(delete=False, suffix="_compressed.pdf") as temp_output_pdf:
            temp_output_path = temp_output_pdf.name
        
        original_size_kb = len(pdf_bytes) / 1024

        # Map compression levels to Ghostscript presets
        # /screen: lowest quality, smallest size (e.g., 72 DPI images)
        # /ebook: better quality than screen, but still highly compressed (e.g., 150 DPI images)
        # /printer: higher quality, larger size (e.g., 300 DPI images)
        # /prepress: highest quality, largest size (no downsampling, high quality)
        gs_setting = '/ebook' # Default
        if compression_level_hint == 'extreme':
            gs_setting = '/screen'
        elif compression_level_hint == 'less':
            gs_setting = '/printer' # Use /printer for 'less' compression (higher quality)

        # Ghostscript command
        # -sDEVICE=pdfwrite: Output to PDF
        # -dCompatibilityLevel=1.4: For broader compatibility
        # -dPDFSETTINGS=/...: Apply the chosen preset
        # -dNOPAUSE -dQUIET -dBATCH: Standard options for non-interactive use
        # -sOutputFile: Output file path
        # -: Reads input from stdin (we'll use a temp file for simplicity here)
        ghostscript_command = [
            'gs',
            '-sDEVICE=pdfwrite',
            '-dCompatibilityLevel=1.4',
            f'-dPDFSETTINGS={gs_setting}',
            '-dNOPAUSE',
            '-dQUIET',
            '-dBATCH',
            f'-sOutputFile={temp_output_path}',
            temp_input_path # Input file
        ]

        app.logger.info(f"Executing Ghostscript command: {' '.join(ghostscript_command)}")
        
        # Execute the Ghostscript command
        result = subprocess.run(ghostscript_command, capture_output=True, text=True)

        # Check for errors from Ghostscript
        if result.returncode != 0:
            raise Exception(f"Ghostscript compression failed: {result.stderr}")

        # Read the compressed PDF bytes
        with open(temp_output_path, 'rb') as f:
            compressed_pdf_bytes = f.read()

        compressed_size_kb = len(compressed_pdf_bytes) / 1024

        # Clean up temporary files
        os.unlink(temp_input_pdf.name)
        os.unlink(temp_output_pdf.name)

        compressed_pdf_base64 = base64.b64encode(compressed_pdf_bytes).decode('utf-8')

        name, ext = os.path.splitext(original_filename)
        compressed_filename = f"{name}_compressed{ext}"

        return jsonify({
            'body': compressed_pdf_base64,
            'isBase64Encoded': True,
            'fileName': compressed_filename,
            'originalSize': original_size_kb, # Use actual original size from frontend
            'compressedSize': compressed_size_kb
        }), 200

    except Exception as e:
        app.logger.error(f"Error compressing PDF: {e}", exc_info=True)
        # Ensure temporary files are cleaned up even on error
        if 'temp_input_path' in locals() and os.path.exists(temp_input_path):
            os.unlink(temp_input_path)
        if 'temp_output_path' in locals() and os.path.exists(temp_output_path):
            os.unlink(temp_output_path)
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
    app.run(debug=True, port=int(os.environ.get('PORT', 5000)))
