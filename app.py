from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
import os
import json
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Get the absolute path to the directory containing this file
current_dir = os.path.dirname(os.path.abspath(__file__))
templates_dir = os.path.join(current_dir, 'templates')
static_dir = os.path.join(current_dir, 'static')

try:
    from TC import run_analysis
    logger.info("Successfully imported TC module")
except Exception as e:
    logger.error(f"Error importing TC module: {str(e)}")

# Initialize Flask with explicit template and static folders
app = Flask(__name__, 
            template_folder=templates_dir,
            static_folder=static_dir)
app.secret_key = 'your_secret_key'  # برای استفاده از flash messages

# مسیر ذخیره نتایج
RESULTS_DIR = os.path.join(current_dir, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# مسیر ذخیره تنظیمات
CONFIG_DIR = os.path.join(current_dir, "config")
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# تنظیمات پیش‌فرض
DEFAULT_CONFIG = {
    "courses": [
        'Advanced Programming',
        'Algorithm Analysis',
        'Computer Vision',
        'Data Structure',
        'Database Systems',
        'Deep Learning',
        'Machine Learning',
        'Operating Systems',
        'Operations Research',
        'Programming Languages',
        'Software Engineering',
        'Theory of Computation'
    ],
    "scholar_ids": [
        "HChhDEwAAAAJ",
        "eSspyHIAAAAJ",
        "onm7tt0AAAAJ",
        "ql5JirMAAAAJ",
        "x55q6n0AAAAJ"
    ]
}

def load_config():
    """Load configuration from file or create default"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

def save_config(config):
    """Save configuration to file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

@app.route('/')
def index():
    """Main page"""
    logger.debug("Rendering index page")
    try:
        config = load_config()
        logger.debug(f"Loaded config: {config}")
        return render_template('index.html', 
                            courses=config['courses'],
                            scholar_ids=config['scholar_ids'])
    except Exception as e:
        logger.error(f"Error rendering index page: {str(e)}")
        return f"Error: {str(e)}", 500

@app.route('/update_config', methods=['POST'])
def update_config():
    """Update configuration"""
    try:
        courses = request.form.get('courses', '').strip().split('\n')
        courses = [course.strip() for course in courses if course.strip()]
        
        scholar_ids = request.form.get('scholar_ids', '').strip().split('\n')
        scholar_ids = [sid.strip() for sid in scholar_ids if sid.strip()]
        
        if not courses:
            flash('لیست دروس نمی‌تواند خالی باشد.', 'error')
            return redirect(url_for('index'))
            
        if not scholar_ids:
            flash('لیست شناسه‌های پژوهشگران نمی‌تواند خالی باشد.', 'error')
            return redirect(url_for('index'))
        
        config = {
            "courses": courses,
            "scholar_ids": scholar_ids
        }
        
        save_config(config)
        flash('تنظیمات با موفقیت ذخیره شد.', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        flash(f'خطا در ذخیره تنظیمات: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/run_analysis', methods=['POST'])
def analyze():
    """Run the analysis"""
    try:
        config = load_config()
        method = request.form.get('method', 'sum')
        
        # اجرای تحلیل
        _, result_paths = run_analysis(
            config['courses'], 
            config['scholar_ids'], 
            method=method,
            output_dir=RESULTS_DIR
        )
        
        flash('تحلیل با موفقیت انجام شد.', 'success')
        return render_template('results.html', 
                              result_paths=result_paths,
                              method=method)
        
    except Exception as e:
        flash(f'خطا در اجرای تحلیل: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/results/<path:filename>')
def download_file(filename):
    """Download result files"""
    return send_from_directory(RESULTS_DIR, filename)

@app.route('/test')
def test():
    """Test route to check if Flask is working"""
    return "Flask is working correctly!"

# Add this route after the other routes
@app.route('/template-test')
def template_test():
    """Test route to check if template rendering is working"""
    return render_template('test.html')

# تغییر secret_key برای امنیت بیشتر
# app.secret_key = os.environ.get('SECRET_KEY', 'your_default_secret_key')

if __name__ == '__main__':
    logger.info("Starting Flask application")
    app.run(debug=True)