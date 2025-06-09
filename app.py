import io
import base64
import os
import subprocess
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    """Simple home route to confirm the backend server is running and Ghostscript is available."""
    try:
        # Check if 'gs' (Ghostscript) command is available
        subprocess.run(['gs', '--version'], capture_output=True, check=True)
        ghostscript_status = "Ghostscript is installed and available."
    except Exception as e:
        ghostscript_status = f"Ghostscript is NOT available. Error: {e}. Ensure it's installed via build.sh"

    return f"PDF Processing Backend (Ghostscript Tuned Compression) is running! {ghostscript_status}"

@app.route('/compress-pdf', methods=['POST'])
def compress_pdf():
    """
    API endpoint to receive a PDF file (base64 encoded), compress it using Ghostscript
    with granular controls tuned for distinct compression levels, and return the compressed PDF.
    """
    temp_input_path = None
    temp_output_path = None
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
            # Important: Ensure the file is actually created/touched before passing path
            temp_output_pdf.write(b'') 
            temp_output_path = temp_output_pdf.name
        
        original_size_bytes = len(pdf_bytes)
        original_size_kb = original_size_bytes / 1024

        # Base Ghostscript parameters common to all compression levels
        # These settings ensure PDF generation and basic optimizations are applied.
        ghostscript_command = [
            'gs',
            '-sDEVICE=pdfwrite',        # Output device is PDF writer
            '-dCompatibilityLevel=1.4', # For broader compatibility
            '-dNOPAUSE',                # Do not pause for errors/prompts
            '-dQUIET',                  # Suppress verbose output
            '-dBATCH',                  # Exit after processing
            '-dSAFER',                  # Enable safer mode for file operations
            '-dEmbedAllFonts=true',     # Embed all fonts to maintain appearance (can be overridden)
            '-dSubsetFonts=true',       # Embed only the characters used from fonts
            '-dCompressFonts=true',     # Compress font data
            '-dOptimize=true',          # General PDF optimization
            '-dFastWebView=true',       # Linearize PDF for faster web viewing
            '-dColorConversionStrategy=/LeaveAlone', # Default to not convert color unless specified
            '-dGrayImageDownsampleType=/Bicubic',
            '-dColorImageDownsampleType=/Bicubic',
            '-dMonoImageDownsampleType=/Bicubic',
            f'-sOutputFile={temp_output_path}', # Specify output file path
            temp_input_path             # Specify input file path
        ]

        # Apply specific, highly differentiated parameters based on the requested compression level.
        # We are being EXTREMELY explicit and aggressive here.
        if compression_level_hint == 'extreme':
            # EXTREME COMPRESSION: Aggressively reduce file size, expect SEVERE quality loss.
            app.logger.info("Applying EXTREME compression settings.")
            ghostscript_command.extend([
                '-sProcessColorModel=DeviceGray', # *** CRITICAL: Convert all colors to grayscale ***
                '-dDownsampleColorImages=true',
                '-dDownsampleGrayImages=true',
                '-dDownsampleMonoImages=true',
                '-dColorImageResolution=15',  # EXTREMELY low resolution for color images
                '-dGrayImageResolution=15',   # EXTREMELY low resolution for grayscale images
                '-dMonoImageResolution=30',   # VERY low resolution for monochrome images
                '-dColorImageQuality=0',      # Absolute MINIMUM JPEG quality for color
                '-dGrayImageQuality=0',       # Absolute MINIMUM JPEG quality for grayscale
                # Forcing /Average for extreme downsampling
                '-dColorImageDownsampleType=/Average', 
                '-dGrayImageDownsampleType=/Average',
                '-dMonoImageDownsampleType=/Average',
                '-dUseFlateCompression=true', # Try to use Flate where possible for text/line art
                '-dEncodeColorImages=true',   # Force re-encoding of all images
                '-dEncodeGrayImages=true',
                '-dEncodeMonoImages=true',
                '-dAutoFilterColorImages=true', # Let GS choose best filter
                '-dAutoFilterGrayImages=true',
                '-dColorImageFilter=/DCTEncode', # Force JPEG compression for color
                '-dGrayImageFilter=/DCTEncode', # Force JPEG compression for grayscale
                '-dPreserveEPSInfo=false',    # Strip EPS metadata
                '-dPreserveOPIComments=false',# Strip OPI comments
                '-dPreserveOverprintSettings=false', # Strip overprint settings
                '-dDetectDuplicateImages=true',
                '-dMaxSubsetPct=10',           # Aggressive font subsetting (e.g., only 10% of font size is kept)
            ])
        elif compression_level_hint == 'less':
            # LESS COMPRESSION: Prioritize high quality, with moderate size reduction.
            app.logger.info("Applying LESS compression settings.")
            ghostscript_command.extend([
                '-dDownsampleColorImages=true',
                '-dDownsampleGrayImages=true',
                '-dDownsampleMonoImages=true',
                '-dColorImageResolution=200', # High resolution
                '-dGrayImageResolution=200',  
                '-dMonoImageResolution=400',  
                '-dColorImageQuality=80',     # High JPEG quality
                '-dGrayImageQuality=80',      
                '-dColorImageDownsampleType=/Bicubic', # High quality downsampling
                '-dGrayImageDownsampleType=/Bicubic',
                '-dMonoImageDownsampleType=/Bicubic',
                '-dUseFlateCompression=true',
                '-dEncodeColorImages=true',
                '-dEncodeGrayImages=true',
                '-dEncodeMonoImages=true',
                '-dAutoFilterColorImages=true',
                '-dAutoFilterGrayImages=true',
                '-dColorImageFilter=/DCTEncode',
                '-dGrayImageFilter=/DCTEncode',
                '-dMaxSubsetPct=100',           # Max font subsetting (full font)
            ])
        else: # 'recommended' or any other unsupported level defaults to recommended
            # RECOMMENDED COMPRESSION: Good balance between file size and quality.
            app.logger.info("Applying RECOMMENDED compression settings.")
            ghostscript_command.extend([
                '-dDownsampleColorImages=true',
                '-dDownsampleGrayImages=true',
                '-dDownsampleMonoImages=true',
                '-dColorImageResolution=100', # Moderate resolution
                '-dGrayImageResolution=100',  
                '-dMonoImageResolution=200',  
                '-dColorImageQuality=40',     # Medium JPEG quality
                '-dGrayImageQuality=40',      
                '-dColorImageDownsampleType=/Bicubic',
                '-dGrayImageDownsampleType=/Bicubic',
                '-dMonoImageDownsampleType=/Bicubic',
                '-dUseFlateCompression=true',
                '-dEncodeColorImages=true',
                '-dEncodeGrayImages=true',
                '-dEncodeMonoImages=true',
                '-dAutoFilterColorImages=true',
                '-dAutoFilterGrayImages=true',
                '-dColorImageFilter=/DCTEncode',
                '-dGrayImageFilter=/DCTEncode',
                '-dMaxSubsetPct=50',           # Moderate font subsetting
            ])

        app.logger.info(f"Final Ghostscript command being executed: {' '.join(ghostscript_command)}")
        
        # Execute Ghostscript command and capture output
        result = subprocess.run(ghostscript_command, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            app.logger.error(f"Ghostscript compression failed (Return Code: {result.returncode}): {result.stderr}")
            if result.stderr:
                raise Exception(f"PDF compression failed: {result.stderr.strip()}")
            else:
                raise Exception(f"PDF compression failed with exit code {result.returncode}. No detailed error from Ghostscript.")

        # Read the compressed PDF from the temporary output file
        with open(temp_output_path, 'rb') as f:
            compressed_pdf_bytes = f.read()

        # Get original and compressed file sizes in KB for reporting to the frontend
        compressed_size_kb = len(compressed_pdf_bytes) / 1024

        # Encode the compressed PDF bytes back to Base64 for sending to the frontend
        compressed_pdf_base64 = base64.b64encode(compressed_pdf_bytes).decode('utf-8')

        # Construct the output filename
        name, ext = os.path.splitext(original_filename)
        # Added compression level to the filename for easy identification of test results
        compressed_filename = f"{name}_compressed_{compression_level_hint}{ext}" 

        # Return success response with compressed data and sizes
        return jsonify({
            'body': compressed_pdf_base64,
            'isBase64Encoded': True, # Indicate that the body is Base64 encoded
            'fileName': compressed_filename,
            'originalSize': original_size_kb,
            'compressedSize': compressed_size_kb,
            'compressionLevelApplied': compression_level_hint # Confirm applied level
        }), 200

    except Exception as e:
        app.logger.error(f"Error compressing PDF: {e}", exc_info=True)
        return jsonify({'error': f'Failed to compress PDF: {str(e)}'}), 500
    finally:
        # Ensure temporary files are cleaned up, regardless of success or failure
        if temp_input_path and os.path.exists(temp_input_path):
            os.unlink(temp_input_path)
        if temp_output_path and os.path.exists(temp_output_path):
            os.unlink(temp_output_path)

# The /pdf-to-text route from your previous app.py (unchanged)
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
        
        # PyMuPDF needs to be in requirements.txt
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
