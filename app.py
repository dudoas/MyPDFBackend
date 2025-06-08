# app.py
from flask import Flask, request, jsonify, send_file
from io import BytesIO
import base64
import os
import pikepdf # The powerful PDF manipulation library
from flask_cors import CORS # To allow cross-origin requests from your frontend

app = Flask(__name__)
# Enable CORS for all routes, allowing your frontend to make requests
CORS(app) 

@app.route('/')
def home():
    """Simple home route to confirm the server is running."""
    return "PDF Compression Backend is running!"

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
        
        # Compression level hint from frontend (pikepdf uses 'q' parameter for quality)
        compression_level_hint = data.get('compressionLevel', 'recommended')

        pdf_bytes = base64.b64decode(pdf_file_base64)
        original_pdf_stream = BytesIO(pdf_bytes)

        # Open the PDF with pikepdf
        pdf = pikepdf.open(original_pdf_stream)

        # Apply compression settings
        # These settings provide more aggressive compression, especially for images.
        # The 'q' parameter controls JPEG quality (0-1, 1 is best, 0 is worst).
        # We can map the frontend's 'compressionLevel' to 'q' values.
        jpeg_quality = 0.75 # Default for 'recommended'
        if compression_level_hint == 'less':
            jpeg_quality = 0.90 # Higher quality, less compression
        elif compression_level_hint == 'extreme':
            jpeg_quality = 0.50 # Lower quality, more compression

        # Iterate through all images and apply compression
        for page in pdf.pages:
            for image in page.images:
                # Get the image object
                img_obj = pdf.get_object(image)
                if img_obj.Type == '/XObject' and img_obj.Subtype == '/Image':
                    # Apply JPEG compression if it's not already compressed or if current compression is less effective
                    if '/Filter' not in img_obj or img_obj.Filter not in ['/DCTDecode', '/JPXDecode']:
                        # Save the image as JPEG
                        img_obj.write(img_obj.as_pil_image(), file_format='jpeg', q=jpeg_quality)
                    # For images already JPEG/JPX, pikepdf's save will usually recompress if needed
                    # Or you can force recompression with a specific quality
                    elif img_obj.Filter == '/DCTDecode' or img_obj.Filter == '/JPXDecode':
                         # Recompress existing JPEGs/JPXs at desired quality
                         img_obj.write(img_obj.as_pil_image(), file_format='jpeg', q=jpeg_quality)
                    
        # Define output stream for the compressed PDF
        compressed_pdf_stream = BytesIO()

        # Save the compressed PDF.
        # With optimize_images=True, pikepdf applies further optimizations.
        pdf.save(compressed_pdf_stream, 
                 # optimize_images=True, # This option is deprecated/integrated, modern pikepdf does it by default with image manipulation
                 # If you just want to optimize streams and remove unreferenced objects without image recompression:
                 # fix_invalid_cross_references=False, # Often good to set this to True
                 # If you want to linearize (web optimize):
                 # linearize=True,
                 # You can also pass arbitrary qpdf options as a dictionary
                 q_values={'/FlateDecode': 1.0, '/DCTDecode': jpeg_quality} # Control quality for different filters
                )
        
        compressed_pdf_stream.seek(0) # Rewind to the beginning

        # Prepare response
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
        app.logger.error(f"Error compressing PDF: {e}", exc_info=True) # Log the full traceback
        return jsonify({'error': f'Failed to compress PDF: {str(e)}'}), 500

if __name__ == '__main__':
    # For local development
    app.run(debug=True, port=5000)
