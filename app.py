import io
import base64
import os
import subprocess
import tempfile
from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    """Simple home route to confirm the backend server is running."""
    return "PDF Processing Backend (Ghostscript Tuned Compression) is running!"

@app.route('/compress-pdf', methods=['POST'])
def compress_pdf():
    """
    API endpoint to receive a PDF file (base64 encoded), compress it using Ghostscript
    with granular controls tuned for target percentages, and return the compressed PDF.
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

        # Ghostscript command base
        # These are common settings that contribute to overall PDF size reduction
        ghostscript_command = [
            'gs',
            '-sDEVICE=pdfwrite',
            '-dCompatibilityLevel=1.4', # For broader compatibility
            '-dNOPAUSE',
            '-dQUIET',
            '-dBATCH',
            '-dDetectDuplicateImages=true', # Try to deduplicate images
            '-dEmbedAllFonts=true',       # Ensure text is still rendered
            '-dSubsetFonts=true',         # Subset fonts (embed only characters used)
            '-dCompressFonts=true',       # Compress font data
            '-dOptimize=true',            # General optimization
            '-dFastWebView=true',         # Linearize PDF for faster web viewing
            '-dColorImageDownsampleType=/Bicubic', # High-quality downsampling for images
            '-dGrayImageDownsampleType=/Bicubic',
            '-dMonoImageDownsampleType=/Bicubic',
            f'-sOutputFile={temp_output_path}',
            temp_input_path # Input file
        ]

        # Apply granular compression settings based on level
        if compression_level_hint == 'extreme':
            # Aim for ~90% reduction: Very low DPI and quality for images
            ghostscript_command.extend([
                '-dDownsampleColorImages=true',
                '-dDownsampleGrayImages=true',
                '-dDownsampleMonoImages=true', # Even monochrome images for extreme
                '-dColorImageResolution=40',   # Very low resolution for color images
                '-dGrayImageResolution=40',    # Very low resolution for grayscale images
                '-dMonoImageResolution=150',   # Keep mono low but readable
                '-dJPEGQ=8',                   # Extremely low JPEG quality (can cause blockiness)
            ])
        elif compression_level_hint == 'recommended':
            # Aim for ~60% reduction: Moderate DPI and quality
            ghostscript_command.extend([
                '-dDownsampleColorImages=true',
                '-dDownsampleGrayImages=true',
                '-dDownsampleMonoImages=true',
                '-dColorImageResolution=120',  # Medium resolution
                '-dGrayImageResolution=120',
                '-dMonoImageResolution=300',   # Standard mono resolution
                '-dJPEGQ=30',                  # Medium JPEG quality
            ])
        else: # 'less' compression
            # Aim for ~35% reduction: Higher DPI and quality
            ghostscript_command.extend([
                '-dDownsampleColorImages=true', # Still downsample to reduce some size
                '-dDownsampleGrayImages=true',
                '-dDownsampleMonoImages=true',
                '-dColorImageResolution=250',  # High resolution
                '-dGrayImageResolution=250',
                '-dMonoImageResolution=600',   # Good mono resolution
                '-dJPEGQ=70',                  # High JPEG quality
            ])

        app.logger.info(f"Executing Ghostscript command: {' '.join(ghostscript_command)}")
        
        result = subprocess.run(ghostscript_command, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            app.logger.error(f"Ghostscript compression failed (Return Code: {result.returncode}): {result.stderr}")
            # Try to read and return a more specific error if possible
            if "GPL Ghostscript" not in result.stderr and result.stderr.strip():
                raise Exception(f"Ghostscript compression failed: {result.stderr.strip()}")
            else:
                raise Exception(f"Ghostscript compression failed with exit code {result.returncode}. Check server logs for details.")

        # Read the compressed PDF bytes
        with open(temp_output_path, 'rb') as f:
            compressed_pdf_bytes = f.read()

        compressed_size_kb = len(compressed_pdf_bytes) / 1024

        # Clean up temporary files
        os.unlink(temp_input_path)
        os.unlink(temp_output_path)

        compressed_pdf_base64 = base64.b64encode(compressed_pdf_bytes).decode('utf-8')

        name, ext = os.path.splitext(original_filename)
        compressed_filename = f"{name}_compressed{ext}"

        return jsonify({
            'body': compressed_pdf_base64,
            'isBase64Encoded': True,
            'fileName': compressed_filename,
            'originalSize': original_size_kb,
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
        
        import fitz
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
