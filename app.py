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
# در بخش تنظیمات اولیه Flask
app = Flask(__name__, 
            template_folder=templates_dir,
            static_folder=static_dir)
# Use environment variable for secret key
app.secret_key = os.environ.get('SECRET_KEY', 'a8f5f167f44f4964e6c998dee827110c')

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

# In the analyze function, add a check for TC module availability
# Add this after the imports
import time
import traceback
from datetime import datetime

@app.route('/run_analysis', methods=['POST'])
def analyze():
    """Run the analysis"""
    try:
        # Check if TC module is fully functional
        if not hasattr(run_analysis, '__module__') or run_analysis.__module__ != 'TC':
            flash('ماژول تحلیل به درستی بارگذاری نشده است. لطفاً با مدیر سیستم تماس بگیرید.', 'error')
            return redirect(url_for('index'))
            
        config = load_config()
        method = request.form.get('method', 'sum')
        
        # Create a status file to track progress
        status_file = os.path.join(RESULTS_DIR, "analysis_status.json")
        status = {
            "status": "started",
            "start_time": datetime.now().isoformat(),
            "method": method,
            "progress": 0,
            "total_scholars": len(config['scholar_ids']),
            "current_scholar": 0,
            "current_scholar_id": "",
            "error": None,
            "debug_info": "Analysis starting"
        }
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(status_file), exist_ok=True)
        
        with open(status_file, 'w') as f:
            json.dump(status, f)
        
        # Start a background task for analysis
        import threading
        
        def run_analysis_task():
            try:
                logger.info(f"Starting analysis with method: {method}")
                logger.info(f"Courses: {config['courses']}")
                logger.info(f"Scholar IDs: {config['scholar_ids']}")
                
                # Update status to running
                status = {
                    "status": "running",
                    "start_time": datetime.now().isoformat(),
                    "method": method,
                    "progress": 0,
                    "total_scholars": len(config['scholar_ids']),
                    "current_scholar": 0,
                    "current_scholar_id": "",
                    "error": None,
                    "debug_info": "Analysis running"
                }
                with open(status_file, 'w') as f:
                    json.dump(status, f)
                
                # Create a progress callback function
                def progress_callback(scholar_index, scholar_id):
                    nonlocal status
                    status["current_scholar"] = scholar_index + 1
                    status["current_scholar_id"] = scholar_id
                    status["progress"] = int((scholar_index + 1) / len(config['scholar_ids']) * 100)
                    status["debug_info"] = f"Processing scholar {scholar_index + 1}/{len(config['scholar_ids'])}: {scholar_id}"
                    
                    try:
                        with open(status_file, 'w') as f:
                            json.dump(status, f)
                        logger.info(f"Progress: {status['progress']}% - Processing scholar {scholar_index + 1}/{len(config['scholar_ids'])}: {scholar_id}")
                    except Exception as e:
                        logger.error(f"Error updating status file: {str(e)}")
                
                # Run the analysis with progress tracking
                try:
                    # Run the analysis with progress tracking
                    _, result_paths = run_analysis(
                        config['courses'], 
                        config['scholar_ids'], 
                        method=method,
                        output_dir=RESULTS_DIR,
                        progress_callback=progress_callback
                    )
                    
                    # Update status to completed
                    status = {
                        "status": "completed",
                        "start_time": datetime.now().isoformat(),
                        "end_time": datetime.now().isoformat(),
                        "method": method,
                        "progress": 100,
                        "total_scholars": len(config['scholar_ids']),
                        "current_scholar": len(config['scholar_ids']),
                        "result_paths": result_paths,
                        "error": None,
                        "debug_info": "Analysis completed successfully"
                    }
                    with open(status_file, 'w') as f:
                        json.dump(status, f)
                    
                    logger.info(f"Analysis completed successfully: {result_paths}")
                    
                except Exception as e:
                    logger.error(f"Error during analysis: {str(e)}")
                    logger.error(traceback.format_exc())
                    status = {
                        "status": "error",
                        "start_time": datetime.now().isoformat(),
                        "end_time": datetime.now().isoformat(),
                        "method": method,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                        "debug_info": f"Error during analysis: {str(e)}"
                    }
                    with open(status_file, 'w') as f:
                        json.dump(status, f)
                
            except Exception as e:
                logger.error(f"Background analysis error: {str(e)}")
                logger.error(traceback.format_exc())
                
                # Update status to error
                status = {
                    "status": "error",
                    "start_time": datetime.now().isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "method": method,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "debug_info": f"Error: {str(e)}"
                }
                with open(status_file, 'w') as f:
                    json.dump(status, f)
        
        # Start the analysis in a background thread
        thread = threading.Thread(target=run_analysis_task)
        thread.daemon = True
        thread.start()
        
        # Return immediately with a message
        flash('تحلیل شروع شد. این فرآیند ممکن است چند دقیقه طول بکشد. لطفاً صبر کنید و صفحه را رفرش کنید.', 'info')
        return redirect(url_for('check_status'))
        
    except Exception as e:
        logger.error(f"Error in analyze route: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f'خطا در اجرای تحلیل: {str(e)}', 'error')
        return redirect(url_for('index'))

# Add a new route to check analysis status
# Add these changes to your app.py file

@app.route('/check_status')
def check_status():
    """Check the status of the analysis"""
    try:
        status_file = os.path.join(RESULTS_DIR, "analysis_status.json")
        
        if os.path.exists(status_file):
            try:
                with open(status_file, 'r') as f:
                    status = json.load(f)
                
                if status["status"] == "completed":
                    flash('تحلیل با موفقیت انجام شد.', 'success')
                    return redirect(url_for('check_results'))
                elif status["status"] == "error":
                    flash(f'خطا در اجرای تحلیل: {status.get("error", "خطای نامشخص")}', 'error')
                    return redirect(url_for('index'))
                else:
                    # Still running
                    flash('تحلیل در حال اجرا است. لطفاً صبر کنید و صفحه را رفرش کنید.', 'info')
                    return render_template('status.html', status=status)
            except json.JSONDecodeError:
                # Handle corrupted status file
                logger.error("Status file is corrupted")
                return render_template('status.html', status={})
        else:
            # No status file yet, but analysis might be starting
            return render_template('status.html', status={})
            
    except Exception as e:
        logger.error(f"Error checking status: {str(e)}")
        logger.error(traceback.format_exc())
        # Return a minimal status page instead of redirecting
        return render_template('status.html', status={})

@app.route('/check_results')
def check_results():
    """Check if results are available"""
    try:
        # Check if any result files exist
        if not os.path.exists(RESULTS_DIR):
            flash('پوشه نتایج وجود ندارد.', 'error')
            return redirect(url_for('index'))
            
        result_files = os.listdir(RESULTS_DIR)
        logger.debug(f"Files in results directory: {result_files}")
        
        png_files = [f for f in result_files if f.endswith('.png')]
        logger.debug(f"PNG files found: {png_files}")
        
        if png_files:
            # Sort by modification time (newest first)
            png_files.sort(key=lambda x: os.path.getmtime(os.path.join(RESULTS_DIR, x)), reverse=True)
            latest_file = png_files[0]
            logger.debug(f"Latest PNG file: {latest_file}")
            
            # Extract method from filename
            method = "unknown"
            if "_sum_" in latest_file:
                method = "sum"
            elif "_max_" in latest_file:
                method = "max"
            # elif "_mean_" in latest_file:
            #     method = "mean"
            
            # Construct result paths
            base_name = latest_file.replace("_heatmap.png", "")
            result_paths = {
                'png': latest_file
            }
            
            # Only add files that actually exist
            pdf_file = base_name + "_heatmap.pdf"
            if pdf_file in result_files:
                result_paths['pdf'] = pdf_file
                
            csv_file = base_name + ".csv"
            if csv_file in result_files:
                result_paths['csv'] = csv_file
            
            logger.debug(f"Result paths: {result_paths}")
            return render_template('results.html', 
                                  result_paths=result_paths,
                                  method=method)
        else:
            flash('هنوز نتیجه‌ای موجود نیست. لطفاً ابتدا تحلیل را اجرا کنید.', 'info')
            return redirect(url_for('index'))
            
    except Exception as e:
        logger.error(f"Error checking results: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f'خطا در بررسی نتایج: {str(e)}', 'error')
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
# Remove or comment out this line since we've moved it above
# app.secret_key = os.environ.get('SECRET_KEY', 'your_default_secret_key')

if __name__ == '__main__':
    logger.info("Starting Flask application")
    app.run(debug=True)