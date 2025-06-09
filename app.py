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
    with granular controls tuned for distinct compression levels, and return the compressed PDF.
    """
    try:
        data = request.get_json()
        if not data or 'pdfFileBase64' not in data:
            return jsonify({'error': 'No PDF file data provided'}), 400

        pdf_file_base64 = data['pdfFileBase64']
        original_filename = data.get('fileName', 'document.pdf')
        compression_level_hint = data.get('compressionLevel', 'recommended')

        pdf_bytes = base64.b64decode(pdf_file_base64)
        
        # Create temporary input and output files to interact with Ghostscript
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_input_pdf:
            temp_input_pdf.write(pdf_bytes)
            temp_input_path = temp_input_pdf.name

        with tempfile.NamedTemporaryFile(delete=False, suffix="_compressed.pdf") as temp_output_pdf:
            temp_output_path = temp_output_pdf.name
        
        original_size_kb = len(pdf_bytes) / 1024

        # Base Ghostscript parameters common to all compression levels
        # These settings ensure PDF generation and basic optimizations are applied.
        ghostscript_command = [
            'gs',
            '-sDEVICE=pdfwrite',        # Output device is PDF writer
            '-dCompatibilityLevel=1.4', # For broader compatibility
            '-dNOPAUSE',                # Do not pause for errors/prompts
            '-dQUIET',                  # Suppress verbose output
            '-dBATCH',                  # Exit after processing
            '-dDetectDuplicateImages=true', # Identify and remove duplicate images
            '-dEmbedAllFonts=true',     # Embed all fonts to maintain appearance
            '-dSubsetFonts=true',       # Embed only the characters used from fonts
            '-dCompressFonts=true',     # Compress font data
            '-dOptimize=true',          # General PDF optimization
            '-dFastWebView=true',       # Linearize PDF for faster web viewing
            f'-sOutputFile={temp_output_path}', # Specify output file path
            temp_input_path             # Specify input file path
        ]

        # Apply specific, highly differentiated parameters based on the requested compression level.
        # These settings primarily control image resolution and JPEG quality.
        if compression_level_hint == 'extreme':
            # EXTREME COMPRESSION: Aggressively reduce file size, expect significant quality loss.
            ghostscript_command.extend([
                '-dDownsampleColorImages=true',
                '-dDownsampleGrayImages=true',
                '-dDownsampleMonoImages=true',
                '-dColorImageResolution=40',  # Very low resolution for color images
                '-dGrayImageResolution=40',   # Very low resolution for grayscale images
                '-dMonoImageResolution=72',   # Low resolution for monochrome images (for readability)
                '-dJPEGQ=5',                  # Extremely low JPEG quality (0-100, lower is worse quality)
                '-dColorImageDownsampleType=/Average', # Faster, more aggressive downsampling
                '-dGrayImageDownsampleType=/Average',
                '-dMonoImageDownsampleType=/Average',
                # Consider adding -dDoNotEmbedFont for extreme cases if text size is significant,
                # but it can lead to font substitution issues, so not including by default.
            ])
        elif compression_level_hint == 'recommended':
            # RECOMMENDED COMPRESSION: Good balance between file size and quality.
            ghostscript_command.extend([
                '-dDownsampleColorImages=true',
                '-dDownsampleGrayImages=true',
                '-dDownsampleMonoImages=true',
                '-dColorImageResolution=100', # Moderate resolution
                '-dGrayImageResolution=100',
                '-dMonoImageResolution=200',
                '-dJPEGQ=25',                 # Medium JPEG quality
                '-dColorImageDownsampleType=/Bicubic', # Higher quality downsampling
                '-dGrayImageDownsampleType=/Bicubic',
                '-dMonoImageDownsampleType=/Bicubic',
            ])
        elif compression_level_hint == 'less':
            # LESS COMPRESSION: Prioritize high quality, with moderate size reduction.
            ghostscript_command.extend([
                '-dDownsampleColorImages=true', # Still apply downsampling, but at higher res
                '-dDownsampleGrayImages=true',
                '-dDownsampleMonoImages=true',
                '-dColorImageResolution=200', # High resolution
                '-dGrayImageResolution=200',
                '-dMonoImageResolution=400',
                '-dJPEGQ=50',                 # Higher JPEG quality
                '-dColorImageDownsampleType=/Bicubic',
                '-dGrayImageDownsampleType=/Bicubic',
                '-dMonoImageDownsampleType=/Bicubic',
            ])
        else:
            # Default to recommended if an unknown level is provided
            app.logger.warning(f"Unknown compression level '{compression_level_hint}'. Defaulting to 'recommended'.")
            ghostscript_command.extend([
                '-dDownsampleColorImages=true',
                '-dDownsampleGrayImages=true',
                '-dDownsampleMonoImages=true',
                '-dColorImageResolution=100',
                '-dGrayImageResolution=100',
                '-dMonoImageResolution=200',
                '-dJPEGQ=25',
                '-dColorImageDownsampleType=/Bicubic',
                '-dGrayImageDownsampleType=/Bicubic',
                '-dMonoImageDownsampleType=/Bicubic',
            ])

        app.logger.info(f"Executing Ghostscript command: {' '.join(ghostscript_command)}")
        
        # Execute Ghostscript command and capture output
        # check=False is used so we can manually handle non-zero return codes
        result = subprocess.run(ghostscript_command, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            app.logger.error(f"Ghostscript compression failed (Return Code: {result.returncode}): {result.stderr}")
            # Raise a more specific error message based on Ghostscript's stderr
            if result.stderr:
                raise Exception(f"PDF compression failed: {result.stderr.strip()}")
            else:
                raise Exception(f"PDF compression failed with exit code {result.returncode}. No detailed error from Ghostscript.")

        # Read the compressed PDF from the temporary output file
        with open(temp_output_path, 'rb') as f:
            compressed_pdf_bytes = f.read()

        # Get original and compressed file sizes in KB for reporting to the frontend
        compressed_size_kb = len(compressed_pdf_bytes) / 1024

        # Clean up temporary files immediately
        os.unlink(temp_input_path)
        os.unlink(temp_output_path)

        # Encode the compressed PDF bytes back to Base64 for sending to the frontend
        compressed_pdf_base64 = base64.b64encode(compressed_pdf_bytes).decode('utf-8')

        # Construct the output filename
        name, ext = os.path.splitext(original_filename)
        compressed_filename = f"{name}_compressed{ext}"

        # Return success response with compressed data and sizes
        return jsonify({
            'body': compressed_pdf_base64,
            'isBase64Encoded': True, # Indicate that the body is Base64 encoded
            'fileName': compressed_filename,
            'originalSize': original_size_kb,
            'compressedSize': compressed_size_kb
        }), 200

    except Exception as e:
        app.logger.error(f"Error compressing PDF: {e}", exc_info=True)
        # Ensure temporary files are cleaned up even if an error occurs
        if 'temp_input_path' in locals() and os.path.exists(temp_input_path):
            os.unlink(temp_input_path)
        if 'temp_output_path' in locals() and os.path.exists(temp_output_path):
            os.unlink(temp_output_path)
        return jsonify({'error': f'Failed to compress PDF: {str(e)}'}), 500

# The /pdf-to-text route from your previous app.py
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
        
        # PyMuPDF is not installed by default on Render, needs to be added to requirements.txt
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
    # For Render deployment, Flask should listen on all available interfaces (0.0.0.0)
    # and the port specified by the PORT environment variable.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True) # debug=True can be useful for local testing
