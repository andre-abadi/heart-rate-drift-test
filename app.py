from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
from heart_rate_drift import format_results_for_web

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@app.route('/')
def index():
    """Render the main upload page."""
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    """
    Handle GPX file upload and analysis.
    
    Expected form data:
    - file: GPX file
    - skip_first: Minutes to skip at start (default 15)
    - skip_last: Minutes to skip at end (default 15)
    - verbose: Boolean for detailed output (default False)
    """
    # Check if file was uploaded
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part in request'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.gpx'):
        return jsonify({'status': 'error', 'message': 'Only .gpx files are supported'}), 400
    
    try:
        # Get parameters from form
        skip_first = int(request.form.get('skip_first', 15))
        skip_last = int(request.form.get('skip_last', 15))
        verbose = request.form.get('verbose', 'false').lower() == 'true'
        
        # Validate parameters
        if skip_first < 0 or skip_last < 0:
            return jsonify({'status': 'error', 'message': 'Skip times must be non-negative'}), 400
        
        # Process file from memory (don't save to disk)
        file.seek(0)  # Reset file pointer to beginning
        results = format_results_for_web(
            gpx_file_obj=file,
            skip_first=skip_first,
            skip_last=skip_last,
            verbose=verbose
        )
        
        return jsonify(results)
        
    except ValueError as e:
        return jsonify({'status': 'error', 'message': f'Invalid parameter: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error processing file: {str(e)}'}), 500


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
