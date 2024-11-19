import mimetypes
from flask import Flask, app, request, jsonify
import logging
import os
from dotenv import load_dotenv
from invoice_processing import process_invoice


# Set up logging
logging.basicConfig(level=logging.INFO)

# Initialize Flask app
app = Flask(__name__)

# Load environment variables
load_dotenv()

# Folder containing PDF invoices
invoice_folder = os.getenv("INVOICE_FOLDER")

# Output folder for XML and Excel files
output_folder = os.getenv("OUTPUT_FOLDER")
# Ensure output folder exists
os.makedirs(output_folder, exist_ok=True)

# Define /upload endpoint
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "Missing file input"}), 400
    
    # Get all files in the request
    files = request.files.getlist('file')

    # Check if there is more than one file
    if len(files) > 1:
        logging.error(f"Multiple files uploaded: {[file.filename for file in files]}")
        return jsonify({"error": "Only one pdf file is allowed as input"}), 400

    # Process the single file
    file = files[0]
    filename = file.filename
    mime_type, _ = mimetypes.guess_type(filename)
    if filename == '':
        return jsonify({"error": "No file selected"}), 400
    if (mime_type != "application/pdf"):
        return jsonify({"error": "Input type is not recognised"}), 400
    
    # Save the file temporarily
    file_path = os.path.join('uploads', file.filename)
    os.makedirs('uploads', exist_ok=True)
    file.save(file_path)
    logging.info(f"File saved to: {file_path}")
    
    # Process the file
    result = process_invoice(file_path, output_folder)
    
    # Clean up (optional)
    os.remove(file_path)  # Remove file after processing if no longer needed

    return jsonify({"message": result})

# Define /health endpoint to verify the application's status
# Returns JSON with corresponding message and status code 200 if the application is running
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "message": "Application is running!"}), 200


if __name__ == '__main__': 
    # Run Flask app in development mode
    app.run(debug=True, host="0.0.0.0", port=5000)