#app.py
Add commentMore actions
from flask import Flask, request, jsonify
from io import BytesIO
import base64
import os
import pikepdf # The powerful PDF manipulation library
import fitz # PyMuPDF for text extraction
from flask_cors import CORS # To allow cross-origin requests from your frontend
import io
from flask import Flask, request, send_file, jsonify, Response
from pypdf import PdfReader, PdfWriter
from flask_cors import CORS # Required for cross-origin requests from your HTML

app = Flask(__name__)
# Enable CORS for all routes, allowing requests from any origin ('*')
CORS(app)
CORS(app) # Enable CORS for all routes, allowing your HTML to make requests

@app.route('/')
def home():
    """
    Simple home route to confirm the backend server is running.
    This message will appear when you visit your Render.com URL directly.
    """
    return "PDF Processing Backend (Pikepdf & PyMuPDF) is running!"
    """Simple home route for testing if the server is running."""
    return "PDF Compressor Backend is running!"

@app.route('/compress-pdf', methods=['POST'])
@app.route('/compress_pdf', methods=['POST'])
def compress_pdf():
    """
    API endpoint to receive a PDF file (base64 encoded), compress it using pikepdf,
    and return the compressed PDF (also base64 encoded).
    Handles PDF compression requests.
    Expects a PDF file and a compression_level in the request.
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

        # Define highly aggressive image compression parameters based on hint
        # jpeg_quality: Lower values mean more compression, lower image quality.
        # This is the primary lever we have for affecting compression significantly.

        jpeg_quality = 50 # Default for 'recommended' image quality (moderate reduction)

        if compression_level_hint == 'less':
            jpeg_quality = 85 # Higher image quality, less aggressive compression
        elif compression_level_hint == 'extreme':
            jpeg_quality = 10 # VERY LOW image quality for maximum compression (significant visual degradation expected)
            
        # Iterate through all images in the PDF and recompress them
        # This is the primary mechanism for file size reduction that has proven compatible.
        for page in pdf.pages:
            for image in page.images:
                img_obj = pdf.get_object(image)
                # Ensure it's an image object and recompress as JPEG if applicable
                if img_obj.Type == '/XObject' and img_obj.Subtype == '/Image':
                    try:
                        pil_image = img_obj.as_pil_image()
                        # Apply specified JPEG quality during image write.
                        # This overwrites the original image data with a recompressed version.
                        img_obj.write(pil_image, file_format='jpeg', q=jpeg_quality)
                    except Exception as img_err:
                        # Log if an image cannot be processed (e.g., non-standard format),
                        # but don't fail the whole PDF.
                        print(f"Warning: Could not re-compress image on page {page.index + 1}: {img_err}")
        
        # The 'remove_unused_resources()' and 'compresslevel' arguments are intentionally omitted
        # from pdf.save() due to persistent compatibility issues on Render.com.
        # We are relying solely on the image re-compression for configurable size reduction.

        compressed_pdf_stream = BytesIO()
        # Save the modified PDF.
        pdf.save(compressed_pdf_stream)
        
        # Rewind the stream to the beginning before reading its content
        compressed_pdf_stream.seek(0)

        # Encode the compressed PDF bytes to base64 for sending back to the frontend
        compressed_pdf_base64 = base64.b64encode(compressed_pdf_stream.getvalue()).decode('utf-8')
    if 'pdf_file' not in request.files:
        return jsonify({"error": "No PDF file provided"}), 400

        # Determine the filename for the compressed PDF
        name, ext = os.path.splitext(original_filename)
        compressed_filename = f"{name}_compressed{ext}"
    pdf_file = request.files['pdf_file']
    compression_level = request.form.get('compression_level', 'recommended')

        # Return the success response with base64 encoded PDF and metadata
        return jsonify({
            'body': compressed_pdf_base64,
            'isBase64Encoded': True, # Indicate that the 'body' content is base64 encoded
            'fileName': compressed_filename,
            'originalSize': len(pdf_bytes),
            'compressedSize': len(compressed_pdf_stream.getvalue())
        }), 200
    if not pdf_file.filename.endswith('.pdf'):
        return jsonify({"error": "Invalid file type. Please upload a PDF."}), 400

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
            # Using default 'text' output which handles Unicode well.
            extracted_text += page.get_text("text") 
        
        doc.close() # Close the document after extraction

        # Determine the filename for the extracted text file
        name, ext = os.path.splitext(original_filename)
        text_filename = f"{name}_extracted.txt"

        # Encode the extracted text to base64 using UTF-8.
        text_base64 = base64.b64encode(extracted_text.encode('utf-8')).decode('utf-8')

        # Return the success response with base64 encoded text and metadata
        return jsonify({
            'fileContentBase64': text_base64, # This is the key that the frontend expects
            'fileName': text_filename,
            'mimeType': 'text/plain' # Specify the MIME type for the extracted text
        }), 200
        # Read the incoming PDF file into a BytesIO object
        input_pdf_bytes = io.BytesIO(pdf_file.read())
        original_size_kb = len(input_pdf_bytes.getvalue()) / 1024

        reader = PdfReader(input_pdf_bytes)
        writer = PdfWriter()

        # Iterate through pages and add them to the writer
        # This step is crucial for pypdf to process the content
        for page in reader.pages:
            writer.add_page(page)

        # Apply compression based on the selected level
        # pypdf's compress_content_streams() helps in reducing file size by compressing streams.
        # For 'extreme' compression, you might call it multiple times or use more aggressive settings
        # if pypdf exposed them. For simpler levels, fewer or no calls might be sufficient.
        # Note: True advanced PDF compression often involves image downsampling, font subsetting, etc.,
        # which might require more specialized libraries or complex logic.
        if compression_level == 'extreme':
            for page in writer.pages:
                page.compress_content_streams(level=9) # Higher level for more compression
            writer.add_compression() # Add an overall compression filter
        elif compression_level == 'recommended':
            for page in writer.pages:
                page.compress_content_streams(level=5) # Medium level
        # For 'low', we rely on pypdf's default writing, which might still apply some minimal compression.

        # Prepare output buffer for the compressed PDF
        output_pdf_bytes = io.BytesIO()
        writer.write(output_pdf_bytes)
        output_pdf_bytes.seek(0) # Go to the beginning of the BytesIO object for sending

        compressed_size_kb = len(output_pdf_bytes.getvalue()) / 1024

        # Send the compressed file back to the frontend
        response = send_file(
            output_pdf_bytes,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"compressed_{pdf_file.filename}"
        )
        # Add original file size to headers for frontend calculation (CORS exposed header)
        response.headers['Access-Control-Expose-Headers'] = 'X-Original-File-Size-KB'
        response.headers['X-Original-File-Size-KB'] = str(original_size_kb)
        return response

    except Exception as e:
        # Log the full error traceback for debugging on Render.com logs
        app.logger.error(f"Error extracting text from PDF: {e}", exc_info=True)
        # Return an error response to the frontend
        return jsonify({'error': f'Failed to extract text from PDF: {str(e)}'}), 500

        app.logger.error(f"Error compressing PDF: {e}")
        return jsonify({"error": f"Failed to compress PDF: {str(e)}"}), 500

if __name__ == '__main__':
    # This block is for local development only.
    # On Render.com, gunicorn (specified in Procfile) runs the app.
    app.run(debug=True, port=int(os.environ.get('PORT', 5000)))
    # This block is for local development/testing.
    # On Render, your deployment configuration will handle how your app is run.
    app.run(debug=True, port=5000)
