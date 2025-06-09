import io
from flask import Flask, request, send_file, jsonify, Response
from pypdf import PdfReader, PdfWriter
from flask_cors import CORS # Required for cross-origin requests from your HTML

app = Flask(__name__)
CORS(app) # Enable CORS for all routes, allowing your HTML to make requests

@app.route('/')
def home():
    """Simple home route for testing if the server is running."""
    return "PDF Compressor Backend is running!"

@app.route('/compress_pdf', methods=['POST'])
def compress_pdf():
    """
    Handles PDF compression requests.
    Expects a PDF file and a compression_level in the request.
    """
    if 'pdf_file' not in request.files:
        return jsonify({"error": "No PDF file provided"}), 400

    pdf_file = request.files['pdf_file']
    compression_level = request.form.get('compression_level', 'recommended')

    if not pdf_file.filename.endswith('.pdf'):
        return jsonify({"error": "Invalid file type. Please upload a PDF."}), 400

    try:
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
        app.logger.error(f"Error compressing PDF: {e}")
        return jsonify({"error": f"Failed to compress PDF: {str(e)}"}), 500

if __name__ == '__main__':
    # This block is for local development/testing.
    # On Render, your deployment configuration will handle how your app is run.
    app.run(debug=True, port=5000)
