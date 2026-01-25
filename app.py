import os
from datetime import datetime, timezone
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response, send_file
import mysql.connector
import bcrypt
from werkzeug.utils import secure_filename
import csv
import io
import base64
import math
from PIL import Image as PILImage
import google.generativeai as genai
import json
import qrcode
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas

import logging
from logging.handlers import RotatingFileHandler

# -----------------------------------------------------------------------------
# App Configuration
# -----------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.urandom(24)
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER



# --- Database Configuration ---
db_config = {
    'host': "localhost",
    'user': "root",
    'password': "Vijay@123", # Replace with your actual Mysql database password.
    'database': "civicsense_ai"  # Replace with your actual Mysql database schema name.
}

# --- ADD THIS BLOCK FOR FILE LOGGING ---
log_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
log_handler = RotatingFileHandler('app.log', maxBytes=10240, backupCount=10)
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.INFO)
app.logger.addHandler(log_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Civicsense AI application starting up...')


# -----------------------------------------------------------------------------
# Database and Helper Functions
# -----------------------------------------------------------------------------

def get_db_connection():
    """Establishes and returns a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

def allowed_file(filename):
    """Checks if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_tables():
    """Creates all necessary database tables if they do not already exist."""
    conn = get_db_connection()
    if not conn:
        print("Could not connect to the database. Table creation skipped.")
        return

    cursor = conn.cursor()
    try:
        # Users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                first_name VARCHAR(100) NOT NULL,
                last_name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                mobile VARCHAR(20),
                age INT,
                gender VARCHAR(10),
                address VARCHAR(255),
                city VARCHAR(100),
                pincode VARCHAR(20),
                state VARCHAR(100),
                country VARCHAR(100),
                profile_photo_filename VARCHAR(255),
                status VARCHAR(50) NOT NULL DEFAULT 'active'

            )
        """)
        print("Users table checked/created successfully.")

        # Admins Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Admins table checked/created successfully.")
        
        # Add a default admin if one doesn't exist
        cursor.execute("SELECT * FROM admins WHERE username = 'admin'")
        if not cursor.fetchone():
            default_password = 'admin'
            hashed_password = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt())
            cursor.execute("INSERT INTO admins (username, password) VALUES (%s, %s)", ('admin', hashed_password))
            conn.commit()
            print("Default admin user created with username 'admin' and password 'admin'.")

        # Issues Table with unique issue_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id INT AUTO_INCREMENT PRIMARY KEY,
                issue_id VARCHAR(255) UNIQUE,
                fullName VARCHAR(255) NOT NULL,
                age INT,
                gender VARCHAR(50),
                mobile VARCHAR(20) NOT NULL,
                email VARCHAR(255) NOT NULL,
                pincode VARCHAR(10),
                city VARCHAR(100),
                district VARCHAR(100),
                state VARCHAR(100),
                country VARCHAR(100),
                residentialAddress TEXT,
                workAddress TEXT,
                issueCategory VARCHAR(100) NOT NULL,
                customIssueType VARCHAR(255),
                issueDescription TEXT NOT NULL,
                latitude DECIMAL(10, 8),
                longitude DECIMAL(11, 8),
                locationAddress TEXT,
                priority VARCHAR(50) NOT NULL,
                image_filename VARCHAR(255),
                status VARCHAR(50) DEFAULT 'Submitted',
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        print("Issues table checked/created successfully.")

        # Status History Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS issue_status_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                issue_id_ref VARCHAR(255),
                status VARCHAR(50) NOT NULL,
                notes TEXT,
                updated_by VARCHAR(255) DEFAULT 'System',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (issue_id_ref) REFERENCES issues(issue_id) ON DELETE CASCADE
            )
        """)
        print("Issue Status History table checked/created successfully.")

        # Feedback Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                rating INT NOT NULL,
                category VARCHAR(100),
                comments TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        print("Feedback table checked/created successfully.")


        # NEW: Developers Table (for the team members)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS developers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                role VARCHAR(255) NOT NULL,
                year VARCHAR(100),
                department VARCHAR(255),
                reg_no VARCHAR(100),
                institute_name VARCHAR(255),
                photo_filename VARCHAR(255),
                linkedin_url VARCHAR(255),
                github_url VARCHAR(255),
                email VARCHAR(255),
                is_leader BOOLEAN DEFAULT FALSE,
                display_order INT DEFAULT 100
            )
        """)
        print("Developers table checked/created successfully.")

        # NEW: Guide Table (for the project guide)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guides (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                role TEXT NOT NULL,
                bio_quote TEXT,
                photo_filename VARCHAR(255),
                linkedin_url VARCHAR(255),
                email VARCHAR(255)
            )
        """)
        print("Guides table checked/created successfully.")

        # ADD THIS TO your create_tables() function in app.py

        # NEW: Announcements Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS announcements (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Announcements table checked/created successfully.")


    except mysql.connector.Error as err:
        print(f"Error during table creation: {err}")
    finally:
        cursor.close()
        conn.close()



# -----------------------------------------------------------------------------
# User Authentication Routes
# -----------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = get_db_connection()
        if not conn:
            flash('Database connection error.', 'danger')
            return redirect(url_for('login'))
        
        cursor = conn.cursor(dictionary=True)
        try:
            # Fetch the user's status along with other details
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            # 1. Check if user exists and password is correct
            if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                
                # 2. NEW: Check if the user's status is 'active'
                if user.get('status') == 'active':
                    session['user_id'] = user['id']
                    session['user_first_name'] = user['first_name']
                    session['user_email'] = user['email']
                    #flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    # If status is not 'active' (e.g., 'suspended'), deny login
                    flash('Your account has been suspended. Please contact support.', 'danger')
                    return redirect(url_for('login'))
            else:
                # If user does not exist or password is wrong
                flash('Invalid email or password.', 'danger')
                return redirect(url_for('login'))

        except mysql.connector.Error as err:
            print(f"Database error on login: {err}")
            flash('An error occurred during login.', 'danger')
            return redirect(url_for('login'))
        finally:
            cursor.close()
            conn.close()
            
    return render_template('login.html')



# Add these routes to your app.py file (insert them after your existing API routes)

# =============================================================================
# DASHBOARD API ROUTES
# =============================================================================

@app.route('/api/dashboard/stats')
def api_dashboard_stats():
    """Get dashboard statistics for the current user"""
    if 'user_id' not in session or 'user_email' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        user_email = session['user_email']
        
        # Total submissions by user
        cursor.execute("SELECT COUNT(*) as count FROM issues WHERE email = %s", (user_email,))
        total_submissions = cursor.fetchone()['count']
        
        # Pending issues (Submitted status)
        cursor.execute("SELECT COUNT(*) as count FROM issues WHERE email = %s AND status = 'Submitted'", (user_email,))
        pending_issues = cursor.fetchone()['count']
        
        # In Progress issues
        cursor.execute("SELECT COUNT(*) as count FROM issues WHERE email = %s AND status = 'In Progress'", (user_email,))
        in_progress_issues = cursor.fetchone()['count']
        
        # Resolved issues
        cursor.execute("SELECT COUNT(*) as count FROM issues WHERE email = %s AND status IN ('Resolved', 'Completed')", (user_email,))
        resolved_issues = cursor.fetchone()['count']
        
        # Additional stats
        cursor.execute("SELECT COUNT(*) as count FROM issues WHERE email = %s AND DATE(submitted_at) = CURDATE()", (user_email,))
        today_submissions = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM issues WHERE email = %s AND submitted_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)", (user_email,))
        week_submissions = cursor.fetchone()['count']
        
        return jsonify({
            'status': 'success',
            'total_submissions': total_submissions,
            'pending_issues': pending_issues,
            'in_progress_issues': in_progress_issues,
            'resolved_issues': resolved_issues,
            'today_submissions': today_submissions,
            'week_submissions': week_submissions,
            'timestamp': datetime.now().isoformat()
        })
        
    except mysql.connector.Error as err:
        print(f"Database error on dashboard stats: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# =============================================================================
# === PASTE THIS ENTIRE CORRECTED FUNCTION INTO YOUR APP.PY FILE =============
# =============================================================================

@app.route('/api/dashboard/recent-submissions')
def api_dashboard_recent_submissions():
    """Get recent submissions for the current user with pagination"""
    if 'user_id' not in session or 'user_email' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
    except ValueError:
        page = 1
        limit = 10
    
    offset = (page - 1) * limit
    user_email = session['user_email']
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # --- FIX #1: Handle the count result safely ---
        # This prevents an error if a user has zero submissions.
        cursor.execute("SELECT COUNT(*) as total FROM issues WHERE email = %s", (user_email,))
        count_result = cursor.fetchone()
        total_submissions = count_result['total'] if count_result else 0
        total_pages = math.ceil(total_submissions / limit) if limit > 0 else 0
        
        # The f-string query for LIMIT/OFFSET remains correct
        query = f"""
            SELECT 
                issue_id,
                CASE 
                    WHEN customIssueType IS NOT NULL AND customIssueType != '' 
                    THEN customIssueType 
                    ELSE issueCategory 
                END as category,
                status,
                submitted_at
            FROM issues 
            WHERE email = %s 
            ORDER BY submitted_at DESC 
            LIMIT {limit} OFFSET {offset}
        """
        cursor.execute(query, (user_email,))
        submissions = cursor.fetchall()
        
        formatted_submissions = []
        for submission in submissions:
            if isinstance(submission['submitted_at'], datetime):
                formatted_date = submission['submitted_at'].strftime('%b %d, %Y')
            else:
                formatted_date = 'N/A'
            
            formatted_submissions.append({
                'issue_id': submission['issue_id'],
                'category': submission['category'][:25] + '...' if len(submission['category']) > 25 else submission['category'],
                'status': submission['status'],
                'date': formatted_date
            })
        
        return jsonify({
            'status': 'success',
            'submissions': formatted_submissions,
            'pagination': {
                'currentPage': page,
                'totalPages': total_pages,
                'totalSubmissions': total_submissions,
                'limit': limit
            },
            'timestamp': datetime.now().isoformat()
        })
        
    # --- FIX #2: Broaden the exception to catch all errors ---
    except Exception as err:
        print(f"Database or other error on recent submissions: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/dashboard/category-stats')
def api_dashboard_category_stats():
    """Get issue category statistics for the current user"""
    if 'user_id' not in session or 'user_email' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        user_email = session['user_email']
        
        # Get category distribution
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN customIssueType IS NOT NULL AND customIssueType != '' 
                    THEN customIssueType 
                    ELSE issueCategory 
                END as category,
                COUNT(*) as count
            FROM issues 
            WHERE email = %s 
            GROUP BY category
            ORDER BY count DESC
            LIMIT 10
        """, (user_email,))
        
        categories = cursor.fetchall()
        
        return jsonify({
            'status': 'success',
            'categories': categories,
            'timestamp': datetime.now().isoformat()
        })
        
    except mysql.connector.Error as err:
        print(f"Database error on category stats: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# =============================================================================
# UPDATE THE DASHBOARD ROUTE
# =============================================================================

# Replace your existing dashboard route with this updated version:
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('You must be logged in to view this page.', 'warning')
        return redirect(url_for('login'))
    return render_template('dashboard.html', first_name=session.get('user_first_name'))

# =============================================================================
# ADDITIONAL HELPER ROUTES (Optional but recommended)
# =============================================================================

@app.route('/api/dashboard/overview')
def api_dashboard_overview():
    """Get comprehensive dashboard overview"""
    if 'user_id' not in session or 'user_email' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        user_email = session['user_email']
        
        # Get comprehensive stats
        stats_query = """
            SELECT 
                COUNT(*) as total_submissions,
                SUM(CASE WHEN status = 'Submitted' THEN 1 ELSE 0 END) as pending_issues,
                SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) as in_progress_issues,
                SUM(CASE WHEN status IN ('Resolved', 'Completed') THEN 1 ELSE 0 END) as resolved_issues,
                SUM(CASE WHEN status = 'Rejected' THEN 1 ELSE 0 END) as rejected_issues,
                SUM(CASE WHEN DATE(submitted_at) = CURDATE() THEN 1 ELSE 0 END) as today_submissions,
                SUM(CASE WHEN submitted_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as week_submissions,
                SUM(CASE WHEN submitted_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as month_submissions
            FROM issues 
            WHERE email = %s
        """
        
        cursor.execute(stats_query, (user_email,))
        overview_stats = cursor.fetchone()
        
        # Calculate resolution rate
        total = overview_stats['total_submissions']
        resolved = overview_stats['resolved_issues']
        resolution_rate = round((resolved / total * 100) if total > 0 else 0, 1)
        
        # Get user's most active day
        cursor.execute("""
            SELECT DAYNAME(submitted_at) as day_name, COUNT(*) as count
            FROM issues 
            WHERE email = %s
            GROUP BY DAYNAME(submitted_at), DAYOFWEEK(submitted_at)
            ORDER BY count DESC
            LIMIT 1
        """, (user_email,))
        
        most_active_day = cursor.fetchone()
        
        return jsonify({
            'status': 'success',
            'overview': {
                **overview_stats,
                'resolution_rate': resolution_rate,
                'most_active_day': most_active_day['day_name'] if most_active_day else None,
                'engagement_level': 'High' if total > 10 else 'Medium' if total > 3 else 'Low'
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except mysql.connector.Error as err:
        print(f"Database error on dashboard overview: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/dashboard/activity-timeline')
def api_dashboard_activity_timeline():
    """Get user's activity timeline for the last 30 days"""
    if 'user_id' not in session or 'user_email' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        user_email = session['user_email']
        
        # Get daily activity for last 30 days
        cursor.execute("""
            SELECT 
                DATE(submitted_at) as date,
                COUNT(*) as submissions
            FROM issues 
            WHERE email = %s 
            AND submitted_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(submitted_at)
            ORDER BY date ASC
        """, (user_email,))
        
        activity_data = cursor.fetchall()
        
        # Format dates for JSON
        for item in activity_data:
            if isinstance(item['date'], datetime):
                item['date'] = item['date'].strftime('%Y-%m-%d')
        
        return jsonify({
            'status': 'success',
            'activity_timeline': activity_data,
            'timestamp': datetime.now().isoformat()
        })
    except mysql.connector.Error as err:
        print(f"Database error on activity timeline: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()






@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))
        conn = get_db_connection()
        if not conn:
            flash('Database connection failed.', 'danger')
            return redirect(url_for('register'))
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT email FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash('Email is already registered.', 'danger')
                return redirect(url_for('register'))
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            cursor.execute(
                "INSERT INTO users (first_name, last_name, email, password) VALUES (%s, %s, %s, %s)",
                (first_name, last_name, email, hashed_password)
            )
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            flash('An error occurred during registration.', 'danger')
            return redirect(url_for('register'))
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_first_name', None)
    session.pop('user_email', None)
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('login'))

# -----------------------------------------------------------------------------
# Admin Authentication Routes
# -----------------------------------------------------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = get_db_connection()
        if not conn:
            flash('Database connection error.', 'danger')
            return redirect(url_for('admin_login'))
        
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM admins WHERE username = %s", (username,))
            admin = cursor.fetchone()
            if admin and bcrypt.checkpw(password.encode('utf-8'), admin['password'].encode('utf-8')):
                session['admin_id'] = admin['id']
                session['admin_username'] = admin['username']
                #flash('Admin login successful!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid admin credentials.', 'danger')
                return redirect(url_for('admin_login'))
        except mysql.connector.Error as err:
            print(f"Database error on admin login: {err}")
            flash('An error occurred during admin login.', 'danger')
            return redirect(url_for('admin_login'))
        finally:
            cursor.close()
            conn.close()
            
    return render_template('admin/admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        flash('You must be logged in as an admin to view this page.', 'warning')
        return redirect(url_for('admin_login'))
    return render_template('admin/admin_dashboard.html', username=session.get('admin_username'))

# This endpoint provides the "Total Users" and "Active Users" stats.

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('admin_login'))

# NEW: Route for the Issue Reports page
@app.route('/admin/issue-reports')
def admin_issue_reports():
    if 'admin_id' not in session:
        flash('You must be logged in as an admin to view this page.', 'warning')
        return redirect(url_for('admin_login'))
    return render_template('admin/issue_reports.html', username=session.get('admin_username'))

# NEW: API endpoint for admins to get ALL issues
@app.route('/api/admin/all-issues')
def api_admin_all_issues():
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetches all issues and orders them by submission time
        cursor.execute("SELECT id, issue_id, fullName, issueCategory, locationAddress, priority, status, submitted_at FROM issues ORDER BY submitted_at DESC")
        all_issues = cursor.fetchall()
        
        # Format datetime objects to strings for JSON serialization
        for issue in all_issues:
            if isinstance(issue['submitted_at'], datetime):
                issue['submitted_at'] = issue['submitted_at'].strftime('%d %b %Y, %I:%M %p')
        
        return jsonify(all_issues)
        
    except mysql.connector.Error as err:
        print(f"Database error on fetching all issues: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# -----------------------------------------------------------------------------
# Admin-Specific API Routes
# -----------------------------------------------------------------------------


# NEW: API endpoint for admins to update an issue's status
@app.route('/api/admin/update-status/<int:issue_id>', methods=['POST'])
def api_admin_update_status(issue_id):
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401

    data = request.get_json()
    new_status = data.get('status')
    notes = data.get('notes', f'Status updated to {new_status} by admin.')

    if not new_status:
        return jsonify({'error': 'New status is required.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed.'}), 500
        
    cursor = conn.cursor(dictionary=True)
    try:
        # Update the status in the main issues table
        cursor.execute("UPDATE issues SET status = %s WHERE id = %s", (new_status, issue_id))
        
        # Log the status change in the history table
        cursor.execute("SELECT issue_id FROM issues WHERE id = %s", (issue_id,))
        issue = cursor.fetchone()
        if issue:
            history_sql = "INSERT INTO issue_status_history (issue_id_ref, status, notes, updated_by) VALUES (%s, %s, %s, %s)"
            cursor.execute(history_sql, (issue['issue_id'], new_status, notes, session.get('admin_username', 'Admin')))
        
        conn.commit()
        return jsonify({'status': 'success', 'message': f'Issue status updated to {new_status}.'})

    except mysql.connector.Error as err:
        print(f"Database error updating status: {err}")
        conn.rollback()
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()
# Add these routes to your existing app.py file

# Route for User Feedbacks admin page
@app.route('/admin/user-feedbacks')
def admin_user_feedbacks():
    if 'admin_id' not in session:
        flash('You must be logged in as an admin to view this page.', 'warning')
        return redirect(url_for('admin_login'))
    return render_template('admin/user_feedbacks.html', username=session.get('admin_username'))

# API endpoint for fetching all feedbacks
# In app.py, replace the existing function with this corrected version

@app.route('/admin/api/feedbacks')
def admin_api_feedbacks():
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # --- FIX 1: Added 'u.profile_photo_filename' to the SQL query ---
        # This retrieves the photo file name for the user who left the feedback.
        cursor.execute("""
            SELECT 
                f.id,
                f.rating,
                f.category,
                f.comments,
                f.submitted_at,
                CONCAT(u.first_name, ' ', u.last_name) as user_name,
                u.email as user_email,
                u.profile_photo_filename
            FROM feedback f
            LEFT JOIN users u ON f.user_id = u.id
            ORDER BY f.submitted_at DESC
        """)
        feedbacks = cursor.fetchall()
        
        for feedback in feedbacks:
            # Format datetime objects to strings for JSON serialization
            if isinstance(feedback['submitted_at'], datetime):
                feedback['submitted_at'] = feedback['submitted_at'].strftime('%Y-%m-%d %H:%M:%S')
            
            # --- FIX 2: Construct the full photo URL ---
            # This logic creates the complete image path for the frontend.
            if feedback.get('profile_photo_filename'):
                feedback['photo_url'] = url_for('static', filename=f'uploads/{feedback["profile_photo_filename"]}')
            else:
                # Provide a default avatar if the user has not uploaded a photo
                feedback['photo_url'] = url_for('static', filename='images/female_avatar.png')
        
        return jsonify({
            'status': 'success',
            'feedbacks': feedbacks
        })
        
    except mysql.connector.Error as err:
        print(f"Database error on fetching feedbacks: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()



# API endpoint for feedback statistics
@app.route('/admin/api/feedback-stats')
def admin_api_feedback_stats():
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Total feedbacks
        cursor.execute("SELECT COUNT(*) as total_feedbacks FROM feedback")
        total_feedbacks = cursor.fetchone()['total_feedbacks']
        
        # Average rating
        cursor.execute("SELECT AVG(rating) as avg_rating FROM feedback")
        avg_rating_result = cursor.fetchone()
        avg_rating = round(avg_rating_result['avg_rating'], 1) if avg_rating_result['avg_rating'] else 0
        
        # Rating distribution
        cursor.execute("""
            SELECT rating, COUNT(*) as count 
            FROM feedback 
            GROUP BY rating 
            ORDER BY rating DESC
        """)
        rating_distribution = cursor.fetchall()
        
        # Category distribution
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN category IS NULL OR category = '' THEN 'General'
                    ELSE category 
                END as category,
                COUNT(*) as count 
            FROM feedback 
            GROUP BY category 
            ORDER BY count DESC
        """)
        category_distribution = cursor.fetchall()
        
        # Recent feedbacks (last 7 days)
        cursor.execute("""
            SELECT COUNT(*) as recent_feedbacks 
            FROM feedback 
            WHERE submitted_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """)
        recent_feedbacks = cursor.fetchone()['recent_feedbacks']
        
        return jsonify({
            'status': 'success',
            'stats': {
                'total_feedbacks': total_feedbacks,
                'avg_rating': avg_rating,
                'recent_feedbacks': recent_feedbacks,
                'rating_distribution': rating_distribution,
                'category_distribution': category_distribution
            }
        })
        
    except mysql.connector.Error as err:
        print(f"Database error on fetching feedback stats: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# API endpoint for deleting feedback
@app.route('/admin/api/feedbacks/<int:feedback_id>', methods=['DELETE'])
def admin_delete_feedback(feedback_id):
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed.'}), 500
        
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM feedback WHERE id = %s", (feedback_id,))
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Feedback not found'}), 404
        
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Feedback deleted successfully.'})

    except mysql.connector.Error as err:
        print(f"Database error deleting feedback: {err}")
        conn.rollback()
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# API endpoint for exporting feedbacks
@app.route('/admin/api/feedbacks/export')
def admin_export_feedbacks():
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 
                f.id,
                f.rating,
                f.category,
                f.comments,
                f.submitted_at,
                CONCAT(u.first_name, ' ', u.last_name) as user_name,
                u.email as user_email
            FROM feedback f
            LEFT JOIN users u ON f.user_id = u.id
            ORDER BY f.submitted_at DESC
        """)
        feedbacks = cursor.fetchall()
        
        # Convert to CSV format
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['id', 'user_name', 'user_email', 'rating', 'category', 'comments', 'submitted_at'])
        writer.writeheader()
        for feedback in feedbacks:
            # Convert datetime objects to strings
            row = {}
            for key, value in feedback.items():
                if isinstance(value, datetime):
                    row[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    row[key] = value
            writer.writerow(row)
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=feedbacks_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        return response
        
    except mysql.connector.Error as err:
        print(f"Database error on export: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()
# -----------------------------------------------------------------------------
# Core Application Routes
# -----------------------------------------------------------------------------

@app.route('/')
def index():
    # This route now renders your modern landing page.
    return render_template('Main.html')


@app.route('/report-issue', methods=['GET', 'POST'])
def report_issue():
    if 'user_id' not in session:
        flash('You must be logged in to view this page.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'error', 'message': 'Database connection failed.'}), 500

        cursor = conn.cursor()
        image_filename = None
        try:
            if 'files[]' in request.files:
                file = request.files['files[]']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image_filename = filename

            date_str = datetime.now().strftime('%Y%m%d')
            unique_part = str(uuid.uuid4()).split('-')[0].upper()
            generated_issue_id = f"CS-{date_str}-{unique_part}"

            data = {
                'issue_id': generated_issue_id,
                'fullName': request.form.get('fullName'),
                'age': request.form.get('age'),
                'gender': request.form.get('gender'),
                'mobile': request.form.get('mobile'),
                'email': session['user_email'],
                'pincode': request.form.get('pincode'),
                'city': request.form.get('city'),
                'district': request.form.get('district'),
                'state': request.form.get('state'),
                'country': request.form.get('country'),
                'residentialAddress': request.form.get('residentialAddress'),
                'workAddress': request.form.get('workAddress'),
                'issueCategory': request.form.get('issueCategory'),
                'customIssueType': request.form.get('customIssueType'),
                'issueDescription': request.form.get('issueDescription'),
                'latitude': request.form.get('latitude'),
                'longitude': request.form.get('longitude'),
                'locationAddress': request.form.get('locationAddress'),
                'priority': request.form.get('priority'),
                'image_filename': image_filename,
            }

            sql = """
                INSERT INTO issues (
                    issue_id, fullName, age, gender, mobile, email, pincode, city, district, state, country,
                    residentialAddress, workAddress, issueCategory, customIssueType, issueDescription,
                    latitude, longitude, locationAddress, priority, image_filename
                ) VALUES (
                    %(issue_id)s, %(fullName)s, %(age)s, %(gender)s, %(mobile)s, %(email)s, %(pincode)s, %(city)s,
                    %(district)s, %(state)s, %(country)s, %(residentialAddress)s, %(workAddress)s,
                    %(issueCategory)s, %(customIssueType)s, %(issueDescription)s, %(latitude)s,
                    %(longitude)s, %(locationAddress)s, %(priority)s, %(image_filename)s
                )
            """
            cursor.execute(sql, data)

            history_sql = "INSERT INTO issue_status_history (issue_id_ref, status, notes) VALUES (%s, %s, %s)"
            cursor.execute(history_sql, (generated_issue_id, 'Submitted', 'Issue has been successfully submitted by the user.'))

            conn.commit()

            return jsonify({
                'status': 'success',
                'message': 'Issue reported successfully!',
                'issueId': generated_issue_id
            })

        except mysql.connector.Error as err:
            print(f"Database error on issue submission: {err}")
            conn.rollback()
            return jsonify({'status': 'error', 'message': 'An internal error occurred.'}), 500
        finally:
            cursor.close()
            conn.close()

    return render_template('report-issue.html', first_name=session.get('user_first_name'))

@app.route('/my-submissions')
def my_submissions():
    if 'user_id' not in session:
        flash('You must be logged in to view this page.', 'warning')
        return redirect(url_for('login'))
    return render_template('my-submissions.html', first_name=session.get('user_first_name'))

@app.route('/check-status')
def check_status():
    issue_id = request.args.get('issue_id', '')
    return render_template('check-status.html', first_name=session.get('user_first_name'), issue_id=issue_id)

@app.route('/feedback')
def feedback():
    if 'user_id' not in session:
        flash('You must be logged in to provide feedback.', 'warning')
        return redirect(url_for('login'))
    
    user_info = {
        'name': f"{session.get('user_first_name', '')}",
        'email': session.get('user_email', '')
    }
    return render_template('feedback.html', user_info=user_info)





# -----------------------------------------------------------------------------
# Placeholder Routes to prevent "Not Found" errors
# -----------------------------------------------------------------------------


@app.route('/help-support')
def help_support():
    if 'user_id' not in session:
        flash('You must be logged in to view this page.', 'warning')
        return redirect(url_for('login'))
    return render_template('help-support.html')



# =============================================================================
# 'ABOUT US' PAGE MANAGEMENT ROUTES
# =============================================================================

# --- ADMIN-SIDE ROUTE TO RENDER THE MANAGEMENT PAGE ---
@app.route('/admin/manage-about-us')
def admin_manage_about_us():
    if 'admin_id' not in session:
        flash('You must be logged in as an admin to view this page.', 'warning')
        return redirect(url_for('admin_login'))
    return render_template('admin/manage_about_us.html', username=session.get('admin_username'))


# --- USER-SIDE DYNAMIC 'ABOUT US' PAGE ---
@app.route('/about-us')
def about_us():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Could not load page data. Please try again later.', 'danger')
        return render_template('about-us.html', developers=[], guide=None)
        
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch all developers, team leader first
        cursor.execute("SELECT * FROM developers ORDER BY is_leader DESC, display_order ASC, id ASC")
        developers = cursor.fetchall()
        
        # Fetch the guide (assuming only one guide with id=1)
        cursor.execute("SELECT * FROM guides WHERE id = 1")
        guide = cursor.fetchone()
        
        return render_template('about-us.html', developers=developers, guide=guide)
    except Exception as e:
        print(f"Error fetching about us data: {e}")
        return render_template('about-us.html', developers=[], guide=None)
    finally:
        cursor.close()
        conn.close()


# --- API FOR ADMINS TO GET/ADD DEVELOPERS (REPLACE EXISTING) ---
@app.route('/admin/api/developers', methods=['GET', 'POST'])
def admin_api_developers():
    if 'admin_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    cursor = conn.cursor(dictionary=True)

    # GET all developers
    if request.method == 'GET':
        cursor.execute("SELECT * FROM developers ORDER BY is_leader DESC, display_order ASC, id ASC")
        developers = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'status': 'success', 'developers': developers})

    # POST a new developer
    if request.method == 'POST':
        try:
            data = request.form
            photo = request.files.get('photo')
            photo_filename = None
            
            if photo and allowed_file(photo.filename):
                photo_filename = secure_filename(f"dev_{uuid.uuid4().hex[:8]}_{photo.filename}")
                photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

            sql = """INSERT INTO developers (name, role, year, department, reg_no, institute_name, is_leader, linkedin_url, github_url, email, photo_filename) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            params = (
                data.get('name'), data.get('role'), 
                data.get('year'), data.get('department'), data.get('reg_no'), data.get('institute_name'),
                data.get('is_leader') == 'true',
                data.get('linkedin_url'), data.get('github_url'), data.get('email'),
                photo_filename
            )
            cursor.execute(sql, params)
            conn.commit()
            return jsonify({'status': 'success', 'message': 'Developer added successfully!'})
        except Exception as e:
            conn.rollback()
            print(f"Error adding developer: {e}")
            return jsonify({'status': 'error', 'message': 'Failed to add developer.'}), 500
        finally:
            cursor.close()
            conn.close()


# --- API FOR ADMINS TO UPDATE/DELETE A SPECIFIC DEVELOPER (REPLACE EXISTING) ---
@app.route('/admin/api/developers/<int:dev_id>', methods=['GET', 'POST', 'DELETE'])
def admin_api_manage_developer(dev_id):
    if 'admin_id' not in session: return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    cursor = conn.cursor(dictionary=True)

    # GET specific developer details
    if request.method == 'GET':
        cursor.execute("SELECT * FROM developers WHERE id = %s", (dev_id,))
        developer = cursor.fetchone()
        if not developer: return jsonify({'status': 'error', 'message': 'Developer not found'}), 404
        return jsonify({'status': 'success', 'developer': developer})

    # UPDATE a developer (using POST for simplicity with multipart/form-data)
    # In app.py, inside admin_api_manage_developer...

    if request.method == 'POST':
        try:
            data = request.form
            photo = request.files.get('photo')
            
            cursor.execute("SELECT photo_filename FROM developers WHERE id = %s", (dev_id,))
            current_photo = cursor.fetchone()['photo_filename']
            photo_filename = current_photo

            # --- START: MODIFIED PHOTO LOGIC ---
            if data.get('remove_photo') == 'true':
                photo_filename = None # This will set the photo to NULL
            elif photo and allowed_file(photo.filename):
                # This only runs if we are NOT removing the photo
                photo_filename = secure_filename(f"dev_{uuid.uuid4().hex[:8]}_{photo.filename}")
                photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
            # --- END: MODIFIED PHOTO LOGIC ---

            # The rest of the function (SQL UPDATE) remains the same
    
            sql = """UPDATE developers SET name=%s, role=%s, year=%s, department=%s, reg_no=%s, institute_name=%s, 
                     is_leader=%s, linkedin_url=%s, github_url=%s, email=%s, photo_filename=%s WHERE id=%s"""
            params = (
                data.get('name'), data.get('role'),
                data.get('year'), data.get('department'), data.get('reg_no'), data.get('institute_name'),
                data.get('is_leader') == 'true',
                data.get('linkedin_url'), data.get('github_url'), data.get('email'),
                photo_filename, dev_id
            )
            cursor.execute(sql, params)
            conn.commit()
            return jsonify({'status': 'success', 'message': 'Developer updated successfully!'})
        except Exception as e:
            conn.rollback()
            print(f"Error updating developer: {e}")
            return jsonify({'status': 'error', 'message': 'Failed to update developer.'}), 500
    
    # DELETE a developer
    if request.method == 'DELETE':
        try:
            cursor.execute("DELETE FROM developers WHERE id = %s", (dev_id,))
            conn.commit()
            return jsonify({'status': 'success', 'message': 'Developer deleted successfully.'})
        except Exception as e:
            conn.rollback()
            return jsonify({'status': 'error', 'message': 'Failed to delete developer.'}), 500

    cursor.close()
    conn.close()
    return jsonify({'status': 'error', 'message': 'Invalid request method.'}), 405

# --- API FOR ADMINS TO GET/UPDATE THE GUIDE ---
@app.route('/admin/api/guide', methods=['GET', 'POST'])
def admin_api_guide():
    if 'admin_id' not in session: return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    cursor = conn.cursor(dictionary=True)

    # GET guide details
    if request.method == 'GET':
        cursor.execute("SELECT * FROM guides WHERE id = 1")
        guide = cursor.fetchone()
        return jsonify({'status': 'success', 'guide': guide})


    # In app.py, inside admin_api_guide...

    if request.method == 'POST':
        try:
            data = request.form
            photo = request.files.get('photo')

            cursor.execute("SELECT photo_filename FROM guides WHERE id = 1")
            result = cursor.fetchone()
            current_photo = result['photo_filename'] if result else None
            photo_filename = current_photo

            # --- START: MODIFIED PHOTO LOGIC ---
            if data.get('remove_photo') == 'true':
                photo_filename = None # This will set the photo to NULL
            elif photo and allowed_file(photo.filename):
                # This only runs if we are NOT removing the photo
                photo_filename = secure_filename(f"guide_{uuid.uuid4().hex[:8]}_{photo.filename}")
                photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
            # --- END: MODIFIED PHOTO LOGIC ---

        # The rest of the function (SQL UPDATE/INSERT) remains the same
        # ...

            if result: # If record exists, UPDATE it
                sql = """UPDATE guides SET name=%s, role=%s, bio_quote=%s, linkedin_url=%s, email=%s, photo_filename=%s WHERE id=1"""
            else: # Otherwise, INSERT a new one
                sql = """INSERT INTO guides (name, role, bio_quote, linkedin_url, email, photo_filename, id) VALUES (%s, %s, %s, %s, %s, %s, 1)"""

            params = (data.get('name'), data.get('role'), data.get('bio_quote'), data.get('linkedin_url'), data.get('email'), photo_filename)
            cursor.execute(sql, params)
            conn.commit()
            return jsonify({'status': 'success', 'message': 'Guide details updated successfully!'})
        except Exception as e:
            conn.rollback()
            print(f"Error updating guide: {e}")
            return jsonify({'status': 'error', 'message': 'Failed to update guide details.'}), 500
    
    cursor.close()
    conn.close()
    return jsonify({'status': 'error', 'message': 'Invalid request method.'}), 405

# --- MY PROFILE PAGE ROUTES ---

@app.route('/my-profile')
def my_profile():
    if 'user_id' not in session:
        flash('You must be logged in to view this page.', 'warning')
        return redirect(url_for('login'))
    return render_template('my-profile.html')

# Replace your existing get_user_profile function with this one
@app.route('/api/user/profile', methods=['GET'])
def get_user_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Select all the new columns including country
        cursor.execute(
            "SELECT id, first_name, last_name, email, created_at, profile_photo_filename, "
            "mobile, age, gender, address, city, pincode, state, country "
            "FROM users WHERE id = %s", 
            (session['user_id'],)
        )
        user = cursor.fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # --- Calculate user activity stats (code remains the same) ---
        user_email = user['email']
        cursor.execute("SELECT COUNT(*) as count FROM issues WHERE email = %s", (user_email,))
        user['total_submissions'] = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM issues WHERE email = %s AND status = 'Resolved'", (user_email,))
        user['resolved_issues'] = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM issues WHERE email = %s AND status = 'In Progress'", (user_email,))
        user['in_progress_issues'] = cursor.fetchone()['count']
        
        if isinstance(user['created_at'], datetime):
            user['member_since'] = user['created_at'].strftime('%B %d, %Y')
        
        if user.get('profile_photo_filename'):
            user['photo_url'] = url_for('static', filename=f'uploads/{user["profile_photo_filename"]}')
        else:
            user['photo_url'] = url_for('static', filename='images/female_avatar.png')

        return jsonify(user)
    finally:
        cursor.close()
        conn.close()

# Replace your existing update_user_profile function with this one
@app.route('/api/user/profile', methods=['POST'])
def update_user_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    
    # Collect all fields from the form
    fields_to_update = {
        'first_name': data.get('first_name'),
        'last_name': data.get('last_name'),
        'mobile': data.get('mobile'),
        'age': data.get('age'),
        'gender': data.get('gender'),
        'address': data.get('address'),
        'city': data.get('city'),
        'pincode': data.get('pincode'),
        'state': data.get('state'),
        'country': data.get('country')
    }

    # --- FIX: Convert empty age string to None for the database ---
    if 'age' in fields_to_update and fields_to_update['age'] == '':
        fields_to_update['age'] = None
    # --- END FIX ---

    if not fields_to_update['first_name'] or not fields_to_update['last_name']:
        return jsonify({'status': 'error', 'message': 'First and last names are required.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed.'}), 500
    
    cursor = conn.cursor()
    try:
        sql_query = "UPDATE users SET "
        sql_params = []
        for key, value in fields_to_update.items():
            sql_query += f"{key} = %s, "
            sql_params.append(value)
        
        sql_query = sql_query.rstrip(', ') + " WHERE id = %s"
        sql_params.append(session['user_id'])
        
        cursor.execute(sql_query, tuple(sql_params))
        conn.commit()
        
        session['user_first_name'] = fields_to_update['first_name']
        return jsonify({'status': 'success', 'message': 'Profile updated successfully!'})
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error updating profile: {err}")
        return jsonify({'status': 'error', 'message': 'An error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

        
@app.route('/api/user/password', methods=['POST'])
def update_user_password():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    if not all([current_password, new_password, confirm_password]):
        return jsonify({'status': 'error', 'message': 'All fields are required.'}), 400

    if new_password != confirm_password:
        return jsonify({'status': 'error', 'message': 'New passwords do not match.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed.'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()

        if not user or not bcrypt.checkpw(current_password.encode('utf-8'), user['password'].encode('utf-8')):
            return jsonify({'status': 'error', 'message': 'Incorrect current password.'}), 400
        
        hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_new_password, session['user_id']))
        conn.commit()
        
        return jsonify({'status': 'success', 'message': 'Password changed successfully!'})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'status': 'error', 'message': 'An error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()


# -----------------------------------------------------------------------------
# API Routes for Real-Time Data
# -----------------------------------------------------------------------------

@app.route('/my-submissions-data')
def my_submissions_data():
    if 'user_id' not in session or 'user_email' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, issue_id, issueCategory, customIssueType, locationAddress, priority, status, submitted_at FROM issues WHERE email = %s ORDER BY submitted_at DESC", (session['user_email'],))
        submissions = cursor.fetchall()
        for submission in submissions:
            if isinstance(submission['submitted_at'], datetime):
                submission['submitted_at'] = submission['submitted_at'].strftime('%B %d, %Y %I:%M %p')
        return jsonify(submissions)
    except mysql.connector.Error as err:
        print(f"Database error on fetching submissions: {err}")
        return jsonify({'error': 'An internal error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/get-submission-details/<int:issue_id>')
def get_submission_details(issue_id):
    if 'user_id' not in session or 'user_email' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        # Get main submission details
        cursor.execute("SELECT * FROM issues WHERE id = %s AND email = %s", (issue_id, session['user_email']))
        submission = cursor.fetchone()
        if not submission:
            return jsonify({'error': 'Submission not found or access denied'}), 404

        # Get the status history for that submission
        cursor.execute("SELECT * FROM issue_status_history WHERE issue_id_ref = %s ORDER BY created_at ASC", (submission['issue_id'],))
        history = cursor.fetchall()

        # Format dates for consistency
        if isinstance(submission['submitted_at'], datetime):
            submission['submitted_at'] = submission['submitted_at'].strftime('%B %d, %Y at %I:%M %p')
        for item in history:
            if isinstance(item['created_at'], datetime):
                item['created_at'] = item['created_at'].strftime('%B %d, %Y at %I:%M %p')

        # Return both the main submission details and its history
        return jsonify({'submission': submission, 'history': history})

    except mysql.connector.Error as err:
        print(f"Database error on fetching submission details: {err}")
        return jsonify({'error': 'An internal error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/check-status', methods=['POST'])
def api_check_status():
    data = request.get_json()
    issue_id = data.get('issueId')

    if not issue_id:
        return jsonify({'error': 'Issue ID is required.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT issue_id, issueCategory, customIssueType, locationAddress, priority, status, submitted_at FROM issues WHERE issue_id = %s", (issue_id,))
        issue_details = cursor.fetchone()

        if not issue_details:
            return jsonify({'error': 'Issue ID not found.'}), 404

        cursor.execute("SELECT status, notes, created_at FROM issue_status_history WHERE issue_id_ref = %s ORDER BY created_at ASC", (issue_id,))
        status_history = cursor.fetchall()

        if isinstance(issue_details['submitted_at'], datetime):
            issue_details['submitted_at'] = issue_details['submitted_at'].strftime('%B %d, %Y at %I:%M %p')
        for history_item in status_history:
            if isinstance(history_item['created_at'], datetime):
                history_item['created_at'] = history_item['created_at'].strftime('%B %d, %Y at %I:%M %p')

        return jsonify({
            'details': issue_details,
            'history': status_history
        })

    except mysql.connector.Error as err:
        print(f"Database error on status check: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/submit-feedback', methods=['POST'])
def submit_feedback():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not authenticated.'}), 401

    data = request.get_json()
    if not data or 'rating' not in data:
        return jsonify({'status': 'error', 'message': 'Rating is a required field.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed.'}), 500
    
    cursor = conn.cursor()
    try:
        sql = """
            INSERT INTO feedback (user_id, rating, category, comments)
            VALUES (%s, %s, %s, %s)
        """
        feedback_data = (
            session['user_id'],
            data.get('rating'),
            data.get('category'),
            data.get('comments')
        )
        cursor.execute(sql, feedback_data)
        conn.commit()
        
        return jsonify({'status': 'success', 'message': 'Thank you for your feedback!'})

    except mysql.connector.Error as err:
        print(f"Database error on feedback submission: {err}")
        conn.rollback()
        return jsonify({'status': 'error', 'message': 'An internal error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# Add these routes to your Flask app.py file

# Route to match what the HTML expects
@app.route('/admin/api/issues')
def admin_api_issues():
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch all issues with basic info
        cursor.execute("""
            SELECT id, issue_id, fullName, issueCategory, locationAddress, 
                   priority, status, submitted_at, email, mobile
            FROM issues 
            ORDER BY submitted_at DESC
        """)
        issues = cursor.fetchall()
        
        # Format datetime objects to strings for JSON serialization
        for issue in issues:
            if isinstance(issue['submitted_at'], datetime):
                issue['submitted_at'] = issue['submitted_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'status': 'success',
            'issues': issues
        })
        
    except mysql.connector.Error as err:
        print(f"Database error on fetching issues: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# Route to get individual issue details
# CORRECTED function for app.py
@app.route('/admin/api/issues/<issue_id>')
def admin_api_issue_details(issue_id):
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Step 1: Get the main issue details
        cursor.execute("SELECT * FROM issues WHERE issue_id = %s", (issue_id,))
        issue = cursor.fetchone()
        
        if not issue:
            return jsonify({'error': 'Issue not found'}), 404

        # NEW: Step 2: Get the full status history for that issue
        cursor.execute(
            "SELECT * FROM issue_status_history WHERE issue_id_ref = %s ORDER BY created_at ASC", 
            (issue['issue_id'],)
        )
        history = cursor.fetchall()

        # Step 3: Format all dates for consistency
        for item in [issue] + history:
            for key in ['submitted_at', 'updated_at', 'created_at']:
                if key in item and isinstance(item.get(key), datetime):
                    # Use a more readable format that matches your formatDate function
                    item[key] = item[key].strftime('%Y-%m-%dT%H:%M:%S')
        
        # NEW: Step 4: Return both the issue and its history
        return jsonify({'issue': issue, 'history': history})
        
    except mysql.connector.Error as err:
        print(f"Database error on fetching issue details: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()
# Route to update issue status
@app.route('/admin/api/issues/<issue_id>/status', methods=['PUT'])
def admin_update_issue_status(issue_id):
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401

    data = request.get_json()
    new_status = data.get('status')
    notes = data.get('notes', f'Status updated to {new_status} by admin.')

    if not new_status:
        return jsonify({'error': 'New status is required.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed.'}), 500
        
    cursor = conn.cursor(dictionary=True)
    try:
        # Update the status in the main issues table
        cursor.execute("UPDATE issues SET status = %s WHERE issue_id = %s", (new_status, issue_id))
        
        # Log the status change in the history table
        history_sql = "INSERT INTO issue_status_history (issue_id_ref, status, notes, updated_by) VALUES (%s, %s, %s, %s)"
        cursor.execute(history_sql, (issue_id, new_status, notes, session.get('admin_username', 'Admin')))
        
        conn.commit()
        return jsonify({'status': 'success', 'message': f'Issue status updated to {new_status}.'})

    except mysql.connector.Error as err:
        print(f"Database error updating status: {err}")
        conn.rollback()
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# Route to delete an issue
@app.route('/admin/api/issues/<issue_id>', methods=['DELETE'])
def admin_delete_issue(issue_id):
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed.'}), 500
        
    cursor = conn.cursor()
    try:
        # First delete from status history (due to foreign key constraint)
        cursor.execute("DELETE FROM issue_status_history WHERE issue_id_ref = %s", (issue_id,))
        
        # Then delete the main issue
        cursor.execute("DELETE FROM issues WHERE issue_id = %s", (issue_id,))
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Issue not found'}), 404
        
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Issue deleted successfully.'})

    except mysql.connector.Error as err:
        print(f"Database error deleting issue: {err}")
        conn.rollback()
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# Route to export issues data
@app.route('/admin/api/issues/export')
def admin_export_issues():
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM issues ORDER BY submitted_at DESC")
        issues = cursor.fetchall()
        
        # Convert to CSV format
        import csv
        import io
        from flask import make_response
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=issues[0].keys() if issues else [])
        writer.writeheader()
        for issue in issues:
            # Convert datetime objects to strings
            row = {}
            for key, value in issue.items():
                if isinstance(value, datetime):
                    row[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    row[key] = value
            writer.writerow(row)
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=issues_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        return response
        
    except mysql.connector.Error as err:
        print(f"Database error on export: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# Add these imports at the top of your app.py file
import google.generativeai as genai
import os
from datetime import datetime
import re

# Add this configuration after your existing configurations
# -----------------------------------------------------------------------------
# Gemini AI Configuration
# -----------------------------------------------------------------------------

# Replace with your actual Gemini API key
GEMINI_API_KEY = "AIzaSyCDgvBDfYBO3SyzvGMkuN3R8vLvur78Oi4"
genai.configure(api_key=GEMINI_API_KEY)

# Initialize the Gemini model
model = genai.GenerativeModel('gemini-1.5-flash')

# Function to load the system prompt from a file
def load_system_prompt(file_path='AI_Prompt.txt'):
    """Loads the system prompt from a text file."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: Prompt file not found at {file_path}. Using a default prompt.")
        return "You are a helpful assistant." # A simple fallback

# Load the Civicsense AI system prompt from the file
CIVICSENSE_SYSTEM_PROMPT = load_system_prompt()
# -----------------------------------------------------------------------------
# AI Chatbot Routes
# -----------------------------------------------------------------------------

@app.route('/chatbot')
def ai_chatbot():
    """Render the AI chatbot page"""
    if 'user_id' not in session:
        flash('You must be logged in to access the AI chatbot.', 'warning')
        return redirect(url_for('login'))
    
    return render_template('chatbot.html', first_name=session.get('user_first_name'))



# Replace your existing /api/chat route with this one
@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Handle chat messages, including optional file uploads, and generate AI responses."""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not authenticated'}), 401
    
    try:
        # Handle multipart form data instead of JSON
        user_message = request.form.get('message', '').strip()
        conversation_history_str = request.form.get('conversation_history', '[]')
        conversation_history = json.loads(conversation_history_str)
        uploaded_file = request.files.get('file')

        if not user_message and not uploaded_file:
            return jsonify({'status': 'error', 'message': 'Message or file cannot be empty'}), 400
        
        # Prepare the prompt for the AI, starting with the system instructions
        prompt_parts = [CIVICSENSE_SYSTEM_PROMPT]

        # Add the uploaded file (if any)
        if uploaded_file:
            if not uploaded_file.mimetype.startswith('image/'):
                return jsonify({'status': 'error', 'message': 'Only image files are supported.'}), 400
            
            image_data = {
                'mime_type': uploaded_file.mimetype,
                'data': uploaded_file.read()
            }
            prompt_parts.append(image_data)

        # Add the user's text message (if any)
        if user_message:
            prompt_parts.append(user_message)

        # Generate response using Gemini
        # Note: When sending images, the model uses the prompt directly, not the chat history object
        response = model.generate_content(prompt_parts)
        
        ai_response = response.text.strip()
        
        # Log the text part of the conversation
        log_chat_interaction(session.get('user_id'), user_message, ai_response)
        
        return jsonify({
            'status': 'success',
            'response': ai_response,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"Error in chat API: {str(e)}")
        fallback_response = get_fallback_response(user_message)
        return jsonify({
            'status': 'success',
            'response': fallback_response,
            'timestamp': datetime.now().isoformat()
        })
def log_chat_interaction(user_id, user_message, ai_response):
    """Log chat interactions for analytics (optional)"""
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        # Create chat_logs table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                user_message TEXT,
                ai_response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        
        # Insert the chat log
        cursor.execute("""
            INSERT INTO chat_logs (user_id, user_message, ai_response) 
            VALUES (%s, %s, %s)
        """, (user_id, user_message, ai_response))
        
        conn.commit()
        
    except Exception as e:
        print(f"Error logging chat interaction: {str(e)}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_fallback_response(user_message):
    """Generate a fallback response when AI service is unavailable"""
    
    # Simple keyword-based responses for common queries
    user_message_lower = user_message.lower()
    
    if any(word in user_message_lower for word in ['report', 'issue', 'problem', 'complaint']):
        return """I'd be happy to help you report an issue! Here's how you can do it:

1. Go to the "Report an Issue" section from the main menu
2. Fill out the required details about your issue
3. Add photos if possible - they help authorities understand the problem better
4. Submit your report and you'll receive a tracking ID

You can always check the status of your submission using the "Check Status" feature. Is there a specific type of issue you'd like to report?"""
    
    elif any(word in user_message_lower for word in ['status', 'track', 'check', 'submission']):
        return """To check the status of your submitted issues:

1. Use the "Check Status" feature from the main menu
2. Enter your issue ID (it looks like CS-YYYYMMDD-XXXX)
3. You'll see the current status and any updates from the authorities

You can also view all your submissions in the "My Submissions" section. Do you have a specific issue ID you'd like me to help you track?"""
    
    elif any(word in user_message_lower for word in ['service', 'city', 'municipal', 'government']):
        return """Civicsense AI helps you access various city services including:

• Infrastructure issues (roads, streetlights, drainage)
• Waste management and sanitation
• Water supply problems  
• Public safety concerns
• Environmental issues
• Municipal service requests

You can report issues, track their progress, and stay informed about your community. What specific city service do you need help with?"""
    
    elif any(word in user_message_lower for word in ['help', 'how', 'guide', 'tutorial']):
        return """I'm here to help! Here are the main things I can assist you with:

🏛️ **Report Issues**: Guide you through reporting civic problems
📊 **Track Status**: Help check your submission status  
🗺️ **City Services**: Information about municipal services
⚙️ **Platform Help**: Navigate Civicsense AI features
🤝 **Civic Engagement**: Tips for community involvement

What would you like help with today? Feel free to ask me anything about civic issues or using this platform!"""
    
    else:
        return """Hello! I'm Civicsense AI Assistant, your civic companion for city services and community engagement.

I'm here to help you with:
• Reporting and tracking civic issues
• Understanding city services and processes  
• Navigating the Civicsense AI platform
• General civic engagement questions

I'm currently experiencing some technical difficulties, but I'm still here to help! Could you please rephrase your question or let me know specifically what you'd like assistance with?"""

# -----------------------------------------------------------------------------
# Admin Route for Chat Analytics (Optional)
# -----------------------------------------------------------------------------

@app.route('/admin/chat-analytics')
def admin_chat_analytics():
    """Admin page to view chat analytics"""
    if 'admin_id' not in session:
        flash('You must be logged in as an admin to view this page.', 'warning')
        return redirect(url_for('admin_login'))
    
    return render_template('admin/admin_analytics_page.html', username=session.get('admin_username'))

@app.route('/admin/api/chat-stats')
def admin_api_chat_stats():
    """API endpoint for chat statistics"""
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Total chat interactions
        cursor.execute("SELECT COUNT(*) as total_chats FROM chat_logs")
        total_result = cursor.fetchone()
        total_chats = total_result['total_chats'] if total_result else 0
        
        # Chats today
        cursor.execute("""
            SELECT COUNT(*) as today_chats 
            FROM chat_logs 
            WHERE DATE(created_at) = CURDATE()
        """)
        today_result = cursor.fetchone()
        today_chats = today_result['today_chats'] if today_result else 0
        
        # Active users (users who have chatted)
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as active_users 
            FROM chat_logs
        """)
        active_result = cursor.fetchone()
        active_users = active_result['active_users'] if active_result else 0
        
        # Recent chat activity (last 7 days)
        cursor.execute("""
            SELECT DATE(created_at) as chat_date, COUNT(*) as chat_count
            FROM chat_logs 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(created_at)
            ORDER BY chat_date DESC
        """)
        recent_activity = cursor.fetchall()
        
        return jsonify({
            'status': 'success',
            'stats': {
                'total_chats': total_chats,
                'today_chats': today_chats,
                'active_users': active_users,
                'recent_activity': recent_activity
            }
        })
        
    except Exception as e:
        print(f"Error fetching chat stats: {str(e)}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# Add this to your create_tables() function
def create_chat_tables():
    """Create chat-related tables"""
    conn = get_db_connection()
    if not conn:
        print("Could not connect to the database. Chat table creation skipped.")
        return

    cursor = conn.cursor()
    try:
        # Chat logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                user_message TEXT,
                ai_response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        print("Chat logs table checked/created successfully.")
        
    except mysql.connector.Error as err:
        print(f"Error during chat table creation: {err}")
    finally:
        cursor.close()
        conn.close()

@app.route('/api/user/profile', methods=['DELETE'])
def delete_user_account():
    """Permanently deletes the currently authenticated user's account."""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401

    user_id_to_delete = session['user_id']
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed.'}), 500
    
    cursor = conn.cursor()
    try:
        # The `feedback` table has ON DELETE SET NULL for the user_id foreign key.
        # Other records like issues are linked by email and will be orphaned, which is acceptable.
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id_to_delete,))
        
        if cursor.rowcount == 0:
            return jsonify({'status': 'error', 'message': 'User not found.'}), 404
            
        conn.commit()
        
        # Clear the session to log the user out completely
        session.clear()
        
        return jsonify({'status': 'success', 'message': 'Account permanently deleted.'})
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error deleting user account: {err}")
        return jsonify({'status': 'error', 'message': 'An error occurred while deleting your account.'}), 500
    finally:
        cursor.close()
        conn.close()

# Add these routes to your app.py file

# -----------------------------------------------------------------------------
# Analytics and Trends Routes
# -----------------------------------------------------------------------------

@app.route('/analytics')
def analytics():
    """Analytics and trends page"""
    if 'user_id' not in session:
        flash('You must be logged in to view this page.', 'warning')
        return redirect(url_for('login'))
    return render_template('analytics.html', first_name=session.get('user_first_name'))

@app.route('/api/analytics/overview')
def api_analytics_overview():
    """Get overall analytics data"""
    if 'user_id' not in session and 'admin_id' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Total issues
        cursor.execute("SELECT COUNT(*) as total_issues FROM issues")
        total_issues = cursor.fetchone()['total_issues']
        
        # Issues by status
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM issues 
            GROUP BY status
        """)
        status_data = cursor.fetchall()
        
        # Issues this month
        cursor.execute("""
            SELECT COUNT(*) as monthly_issues 
            FROM issues 
            WHERE MONTH(submitted_at) = MONTH(CURRENT_DATE()) 
            AND YEAR(submitted_at) = YEAR(CURRENT_DATE())
        """)
        monthly_issues = cursor.fetchone()['monthly_issues']
        
        # Issues by category
        cursor.execute("""
            SELECT issueCategory, COUNT(*) as count 
            FROM issues 
            GROUP BY issueCategory 
            ORDER BY count DESC 
            LIMIT 10
        """)
        category_data = cursor.fetchall()
        
        # Issues by priority
        cursor.execute("""
            SELECT priority, COUNT(*) as count 
            FROM issues 
            GROUP BY priority
        """)
        priority_data = cursor.fetchall()
        
        # Recent trends (last 30 days)
        cursor.execute("""
            SELECT DATE(submitted_at) as date, COUNT(*) as count
            FROM issues 
            WHERE submitted_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
            GROUP BY DATE(submitted_at)
            ORDER BY date ASC
        """)
        trend_data = cursor.fetchall()
        
        # Format dates for JSON serialization
        for item in trend_data:
            if isinstance(item['date'], datetime):
                item['date'] = item['date'].strftime('%Y-%m-%d')
        
        # Response time analysis
        cursor.execute("""
            SELECT 
                AVG(DATEDIFF(updated_at, submitted_at)) as avg_response_days,
                MIN(DATEDIFF(updated_at, submitted_at)) as min_response_days,
                MAX(DATEDIFF(updated_at, submitted_at)) as max_response_days
            FROM issues 
            WHERE status != 'Submitted' AND updated_at IS NOT NULL
        """)
        response_time = cursor.fetchone()
        
        # Top locations by issue count
        cursor.execute("""
            SELECT city, COUNT(*) as count 
            FROM issues 
            WHERE city IS NOT NULL AND city != ''
            GROUP BY city 
            ORDER BY count DESC 
            LIMIT 10
        """)
        location_data = cursor.fetchall()
        
        return jsonify({
            'status': 'success',
            'data': {
                'overview': {
                    'total_issues': total_issues,
                    'monthly_issues': monthly_issues,
                    'avg_response_time': round(response_time['avg_response_days'] or 0, 1)
                },
                'status_distribution': status_data,
                'category_distribution': category_data,
                'priority_distribution': priority_data,
                'trend_data': trend_data,
                'response_time': response_time,
                'location_data': location_data
            }
        })
        
    except mysql.connector.Error as err:
        print(f"Database error on analytics: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/analytics/user-stats')
def api_user_analytics():
    """Get user-specific analytics"""
    if 'user_id' not in session or 'user_email' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        user_email = session['user_email']
        
        # User's total submissions
        cursor.execute("SELECT COUNT(*) as total_submissions FROM issues WHERE email = %s", (user_email,))
        total_submissions = cursor.fetchone()['total_submissions']
        
        # User's submissions by status
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM issues 
            WHERE email = %s 
            GROUP BY status
        """, (user_email,))
        user_status_data = cursor.fetchall()
        
        # User's submissions by category
        cursor.execute("""
            SELECT issueCategory, COUNT(*) as count 
            FROM issues 
            WHERE email = %s 
            GROUP BY issueCategory 
            ORDER BY count DESC
        """, (user_email,))
        user_category_data = cursor.fetchall()
        
        # User's submission trend (last 6 months)
        cursor.execute("""
            SELECT 
                DATE_FORMAT(submitted_at, '%Y-%m') as month,
                COUNT(*) as count
            FROM issues 
            WHERE email = %s 
            AND submitted_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(submitted_at, '%Y-%m')
            ORDER BY month ASC
        """, (user_email,))
        user_trend_data = cursor.fetchall()
        
        return jsonify({
            'status': 'success',
            'data': {
                'total_submissions': total_submissions,
                'status_distribution': user_status_data,
                'category_distribution': user_category_data,
                'trend_data': user_trend_data
            }
        })
        
    except mysql.connector.Error as err:
        print(f"Database error on user analytics: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/analytics/predictions')
def api_analytics_predictions():
    """Get AI-based predictions and insights"""
    if 'user_id' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Busiest day of week
        cursor.execute("""
            SELECT 
                DAYNAME(submitted_at) as day_name,
                COUNT(*) as count 
            FROM issues 
            GROUP BY DAYNAME(submitted_at), DAYOFWEEK(submitted_at)
            ORDER BY count DESC 
            LIMIT 1
        """)
        busiest_day = cursor.fetchone()
        
        # Peak hours
        cursor.execute("""
            SELECT 
                HOUR(submitted_at) as hour,
                COUNT(*) as count 
            FROM issues 
            GROUP BY HOUR(submitted_at)
            ORDER BY count DESC 
            LIMIT 3
        """)
        peak_hours = cursor.fetchall()
        
        # Seasonal trends
        cursor.execute("""
            SELECT 
                MONTH(submitted_at) as month,
                COUNT(*) as count 
            FROM issues 
            GROUP BY MONTH(submitted_at)
            ORDER BY count DESC
        """)
        seasonal_data = cursor.fetchall()
        
        # Generate insights
        insights = []
        
        if busiest_day:
            insights.append({
                'type': 'peak_day',
                'title': f"Peak Activity Day: {busiest_day['day_name']}",
                'description': f"Most issues are reported on {busiest_day['day_name']} with {busiest_day['count']} submissions.",
                'icon': 'calendar_today'
            })
        
        if peak_hours:
            peak_hour = peak_hours[0]['hour']
            time_str = f"{peak_hour:02d}:00"
            insights.append({
                'type': 'peak_time',
                'title': f"Peak Hour: {time_str}",
                'description': f"Highest activity occurs around {time_str} with {peak_hours[0]['count']} submissions.",
                'icon': 'schedule'
            })
        
        # Resolution rate insight
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM issues WHERE status IN ('Resolved', 'Completed')) * 100.0 / COUNT(*) as resolution_rate
            FROM issues
        """)
        resolution_rate = cursor.fetchone()['resolution_rate'] or 0
        
        insights.append({
            'type': 'resolution_rate',
            'title': f"Resolution Rate: {resolution_rate:.1f}%",
            'description': f"Current issue resolution rate is {resolution_rate:.1f}%. " + 
                          ("Excellent performance!" if resolution_rate > 80 else 
                           "Good progress!" if resolution_rate > 60 else 
                           "Room for improvement."),
            'icon': 'task_alt'
        })
        
        return jsonify({
            'status': 'success',
            'data': {
                'busiest_day': busiest_day,
                'peak_hours': peak_hours,
                'seasonal_data': seasonal_data,
                'insights': insights,
                'resolution_rate': round(resolution_rate, 1)
            }
        })
        
    except mysql.connector.Error as err:
        print(f"Database error on predictions: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# Update your main create_tables() function to include chat tables
# Add this line at the end of your existing create_tables() function:
# create_chat_tables()

# -----------------------------------------------------------------------------
# Environment Variables Setup (Add this to the top of your file)
# -----------------------------------------------------------------------------

# For production, set your Gemini API key as an environment variable
# GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'your-default-key-here')

# Example of how to set environment variable in different environments:
# 
# Linux/Mac: export GEMINI_API_KEY="your-api-key-here"
# Windows: set GEMINI_API_KEY=your-api-key-here
# 
# Or create a .env file with:
# GEMINI_API_KEY=your-api-key-here
#
# Then use python-dotenv package to load it:
# from dotenv import load_dotenv
# load_dotenv()

# =============================================================================
# NEW: USER REPORT VIEWING ROUTES (Replaces old PDF download)
# =============================================================================

# IMPORTANT: Make sure this key is defined near the top of your app.py
Maps_API_KEY = "AIzaSyCDgvBDfYBO3SyzvGMkuN3R8vLvur78Oi4" # Replace with your actual key

# In app.py, REPLACE the existing view_report_page function with this one

@app.route('/report/view/<int:issue_id>')
def view_report_page(issue_id):
    # FIX: This now checks for either an admin OR the correct user
    if 'admin_id' not in session and 'user_id' not in session:
        flash('You must be logged in to view this page.', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    if not conn:
        flash('Database connection failed.', 'danger')
        return redirect(url_for('my_submissions'))

    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch the issue regardless of who submitted it first
        cursor.execute("SELECT * FROM issues WHERE id = %s", (issue_id,))
        issue = cursor.fetchone()
        
        if not issue:
            flash('Issue not found.', 'danger')
            return redirect(url_for('admin_issue_reports' if 'admin_id' in session else 'my_submissions'))

        # If a regular user is logged in, make sure they own the report
        if 'user_id' in session and issue['email'] != session.get('user_email'):
            flash('You do not have permission to view this report.', 'danger')
            return redirect(url_for('my_submissions'))

        # --- QR Code Generation (remains the same) ---
        qr_data_string = (
            f"Issue ID: {issue.get('issue_id', 'N/A')}\n"
            f"Status: {issue.get('status', 'N/A')}\n"
            f"Category: {issue.get('customIssueType') or issue.get('issueCategory', 'N/A')}"
        )
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(qr_data_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qr_code_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        logo_path = 'static/images/Civicsense.png'
        logo_data = None
        try:
            with open(logo_path, "rb") as image_file:
                logo_data = base64.b64encode(image_file.read()).decode('utf-8')
        except FileNotFoundError:
            print(f"Warning: Logo file not found at {logo_path}")

        static_map_url = get_static_map_url(issue.get('latitude'), issue.get('longitude'), Maps_API_KEY)

        return render_template(
            "report_view.html",
            issue=issue,
            logo_base64=logo_data,
            maps_api_key=Maps_API_KEY,
            static_map_url=static_map_url,
            qr_code_base64=qr_code_base64
        )

    except Exception as e:
        print(f"Error viewing report page: {repr(e)}")
        flash('An error occurred while trying to load the report.', 'danger')
        return redirect(url_for('admin_issue_reports' if 'admin_id' in session else 'my_submissions'))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()



# In app.py, REPLACE the existing api_report_data function with this one

@app.route('/api/report/data/<int:issue_id>')
def api_report_data(issue_id):
    """API endpoint to get the latest data for a specific issue report."""
    # FIX: This now checks for EITHER a user OR an admin session
    if 'user_id' not in session and 'admin_id' not in session:
        return jsonify({'error': 'User not authenticated'}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        # The query now fetches the issue by its primary 'id'
        cursor.execute("SELECT * FROM issues WHERE id = %s", (issue_id,))
        issue = cursor.fetchone()

        if not issue:
            return jsonify({'error': 'Issue not found or access denied'}), 404
        
        # If a regular user is logged in, double-check they own the report
        if 'user_id' in session and issue['email'] != session.get('user_email'):
             return jsonify({'error': 'Access denied'}), 403

        cursor.execute("SELECT * FROM issue_status_history WHERE issue_id_ref = %s ORDER BY created_at ASC", (issue['issue_id'],))
        status_history = cursor.fetchall()

        # Format all dates into a readable string format for JSON
        for item in [issue] + status_history:
            for key in ['submitted_at', 'updated_at', 'created_at']:
                if key in item and isinstance(item.get(key), datetime):
                    item[key + '_formatted'] = item[key].strftime('%B %d, %Y at %I:%M %p')
        
        return jsonify({
            'issue': issue,
            'status_history': status_history,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error in API report data: {repr(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

        
def get_static_map_url(latitude, longitude, api_key):
    """Generates a URL for a Google Maps Static API image."""
    # This is the corrected check. It only stops if the key is missing.
    if not api_key:
        return None
    
    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    params = {
        'center': f"{latitude},{longitude}",
        'zoom': '16',
        'size': '640x400',
        'maptype': 'roadmap',
        'markers': f"color:0xFE4A49|{latitude},{longitude}",
        'key': api_key
    }
    # This creates a URL like: https://maps.googleapis.com/...
    return f"{base_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"

@app.route('/api/user/profile/photo', methods=['POST'])
def upload_profile_photo():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    if 'photo' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file uploaded'}), 400

    file = request.files['photo']
    if file and allowed_file(file.filename):
        # Ensure upload folder exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        filename = secure_filename(f"user_{session['user_id']}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'error', 'message': 'Database connection failed.'}), 500
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET profile_photo_filename=%s WHERE id=%s",
                (filename, session['user_id'])
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error updating profile photo: {e}")
            return jsonify({'status': 'error', 'message': 'Error updating profile photo'}), 500
        finally:
            cursor.close()
            conn.close()

        return jsonify({
            'status': 'success',
            'message': 'Profile photo updated!',
            'photo_url': url_for('static', filename=f'uploads/{filename}')
        })
    else:
        return jsonify({'status': 'error', 'message': 'Invalid file type'}), 400


# In app.py

# ... (keep all your existing imports and routes) ...

# =============================================================================
# FINAL ADMIN USER MANAGEMENT ROUTES
# =============================================================================

# In app.py, REPLACE all of your user management routes with this block

# =============================================================================
# CORRECTED ADMIN USER MANAGEMENT ROUTES
# =============================================================================

# Route to render the User Management HTML page
@app.route('/admin/user-management')
def admin_user_management():
    if 'admin_id' not in session:
        flash('You must be logged in as an admin to view this page.', 'warning')
        return redirect(url_for('admin_login'))
    return render_template('admin/user_management.html', username=session.get('admin_username'))

# API endpoint for fetching user statistics
@app.route('/admin/api/user-stats')
def admin_api_user_stats():
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) as total_users FROM users")
        total_users = cursor.fetchone()['total_users']
        
        cursor.execute("SELECT COUNT(*) as new_users FROM users WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)")
        new_users = cursor.fetchone()['new_users']

        cursor.execute("SELECT COUNT(DISTINCT email) as users_with_submissions FROM issues")
        users_with_submissions = cursor.fetchone()['users_with_submissions']
        
        cursor.execute("SELECT COUNT(*) as active_users FROM users WHERE status = 'active'")
        active_users = cursor.fetchone()['active_users']
        
        return jsonify({
            'status': 'success',
            'stats': {
                'total_users': total_users,
                'new_users_last_7_days': new_users,
                'active_users': active_users,
                'users_with_submissions': users_with_submissions
            }
        })
    except mysql.connector.Error as err:
        print(f"Database error on fetching user stats: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# API endpoint to GET all users OR CREATE a new user
@app.route('/admin/api/users', methods=['GET', 'POST'])
def admin_api_users():
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401

    # Handle POST request to create a new user
    if request.method == 'POST':
        data = request.get_json()
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        email = data.get('email')
        password = data.get('password')

        if not all([first_name, last_name, email, password]):
            return jsonify({'status': 'error', 'message': 'All fields including password are required.'}), 400

        conn = get_db_connection()
        if not conn: return jsonify({'error': 'Database connection failed.'}), 500
        
        cursor = conn.cursor()
        try:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            cursor.execute(
                "INSERT INTO users (first_name, last_name, email, password) VALUES (%s, %s, %s, %s)",
                (first_name, last_name, email, hashed_password)
            )
            conn.commit()
            return jsonify({'status': 'success', 'message': 'User created successfully!'}), 201
        except mysql.connector.Error as err:
            conn.rollback()
            if err.errno == 1062:
                return jsonify({'status': 'error', 'message': 'This email is already registered.'}), 409
            print(f"Database error creating user: {err}")
            return jsonify({'error': 'An internal server error occurred.'}), 500
        finally:
            cursor.close()
            conn.close()

    # Handle GET request to fetch all users
    if request.method == 'GET':
        conn = get_db_connection()
        if not conn: return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(dictionary=True)
        try:
            sql = """
                SELECT 
                    u.id, u.first_name, u.last_name, u.email, u.created_at, u.profile_photo_filename, u.status,
                    u.mobile, u.age, u.gender, u.address, u.city, u.pincode, u.state, u.country,
                    COALESCE(i.issue_count, 0) as issue_count
                FROM users u
                LEFT JOIN (
                    SELECT email, COUNT(*) as issue_count 
                    FROM issues 
                    GROUP BY email
                ) i ON u.email = i.email
                ORDER BY u.created_at DESC
            """
            cursor.execute(sql)
            users = cursor.fetchall()
            
            for user in users:
                if isinstance(user['created_at'], datetime):
                    user['created_at'] = user['created_at'].strftime('%Y-%m-%d %H:%M:%S')
                if user.get('profile_photo_filename'):
                    user['photo_url'] = url_for('static', filename=f'uploads/{user["profile_photo_filename"]}')
                else:
                    user['photo_url'] = url_for('static', filename='images/female_avatar.png') 

            return jsonify({'status': 'success', 'users': users})
        except mysql.connector.Error as err:
            print(f"Database error fetching users: {err}")
            return jsonify({'error': 'An internal server error occurred.'}), 500
        finally:
            cursor.close()
            conn.close()

# =============================================================================
# === PASTE THIS CORRECTED FUNCTION INTO YOUR APP.PY FILE =====================
# =============================================================================

# API endpoint for a single user: GET details, UPDATE details, or DELETE
@app.route('/admin/api/users/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
def admin_api_manage_user(user_id):
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401

    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Database connection failed'}), 500

    # Handle DELETE request
    if request.method == 'DELETE':
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            if cursor.rowcount == 0: return jsonify({'error': 'User not found'}), 404
            conn.commit()
            return jsonify({'status': 'success', 'message': 'User permanently deleted.'})
        except mysql.connector.Error as err:
            conn.rollback()
            print(f"Database error deleting user: {err}")
            return jsonify({'error': 'An internal server error occurred.'}), 500
        finally:
            cursor.close()
            conn.close()

    # Handle PUT request (update details)
    if request.method == 'PUT':
        data = request.get_json()
        
        # --- FIX: Sanitize integer fields before saving ---
        # If 'age' is sent as an empty string, convert it to None (which becomes SQL NULL).
        if 'age' in data and data['age'] == '':
            data['age'] = None
        # --- END FIX ---

        fields_to_update = ['first_name', 'last_name', 'email', 'mobile', 'age', 'gender', 'address', 'city', 'pincode', 'state', 'country']
        sql_set_parts = [f"{field} = %s" for field in fields_to_update if field in data]
        sql_params = [data[field] for field in fields_to_update if field in data]
        
        if not sql_set_parts: return jsonify({'status': 'error', 'message': 'No fields to update.'}), 400

        sql_params.append(user_id)
        sql_query = f"UPDATE users SET {', '.join(sql_set_parts)} WHERE id = %s"
        
        cursor = conn.cursor()
        try:
            cursor.execute(sql_query, tuple(sql_params))
            conn.commit()
            return jsonify({'status': 'success', 'message': 'User details updated successfully.'})
        except mysql.connector.Error as err:
            conn.rollback()
            if err.errno == 1062: return jsonify({'status': 'error', 'message': 'Email is already in use.'}), 409
            print(f"Database error updating user details: {err}")
            return jsonify({'error': 'An internal server error occurred.'}), 500
        finally:
            cursor.close()
            conn.close()
    
    # Handle GET request (get full details)
    if request.method == 'GET':
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if not user: return jsonify({'error': 'User not found'}), 404
            user.pop('password', None)
            if isinstance(user.get('created_at'), datetime):
                user['created_at_formatted'] = user['created_at'].strftime('%B %d, %Y')
            if user.get('profile_photo_filename'):
                user['photo_url'] = url_for('static', filename=f'uploads/{user["profile_photo_filename"]}')
            else:
                user['photo_url'] = url_for('static', filename='images/female_avatar.png')
            return jsonify({'status': 'success', 'user': user})
        except mysql.connector.Error as err:
            print(f"Database error fetching user details: {err}")
            return jsonify({'error': 'An internal server error occurred.'}), 500
        finally:
            cursor.close()
            conn.close()
# API endpoint to update a user's status (suspend/reactivate)
@app.route('/admin/api/users/<int:user_id>/status', methods=['PUT'])
def admin_api_update_user_status(user_id):
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401
    
    data = request.get_json()
    new_status = data.get('status')
    if new_status not in ['active', 'suspended']:
        return jsonify({'status': 'error', 'message': 'Invalid status provided.'}), 400

    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Database connection failed.'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET status = %s WHERE id = %s", (new_status, user_id))
        if cursor.rowcount == 0: return jsonify({'error': 'User not found'}), 404
        conn.commit()
        message = f"User has been {'suspended' if new_status == 'suspended' else 'reactivated'}."
        return jsonify({'status': 'success', 'message': message})
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error updating user status: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# API endpoint to reset a user's password
@app.route('/admin/api/users/<int:user_id>/password', methods=['PUT'])
def admin_api_reset_password(user_id):
    if 'admin_id' not in session:
        return jsonify({'error': 'Admin not authenticated'}), 401
    
    data = request.get_json()
    new_password = data.get('password')
    if not new_password or len(new_password) < 4:
        return jsonify({'status': 'error', 'message': 'Password must be at least 4 characters long.'}), 400

    conn = get_db_connection()
    if not conn: return jsonify({'error': 'Database connection failed.'}), 500
    
    cursor = conn.cursor()
    try:
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, user_id))
        if cursor.rowcount == 0: return jsonify({'error': 'User not found'}), 404
        conn.commit()
        return jsonify({'status': 'success', 'message': 'User password updated successfully.'})
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Database error resetting password: {err}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# Add this new, consolidated API endpoint to your app.py file

# Add this consolidated API endpoint to your app.py file.
# It corresponds to the 'admin_analytics_page_fixed' HTML file.

@app.route('/admin/api/comprehensive-analytics')
def admin_api_comprehensive_analytics():
    """
    Provides a comprehensive dataset for the admin analytics page,
    filterable by a time range in days.
    """
    if 'admin_id' not in session:
        return jsonify({'status': 'error', 'message': 'Admin not authenticated'}), 401

    try:
        # Get the 'days' parameter from the URL, default to 30 if not provided or invalid
        days_str = request.args.get('days', '30')
        if days_str == 'all':
            days = None # Represents all time
        else:
            days = int(days_str)
    except (ValueError, TypeError):
        days = 30 # Fallback to 30 days on error

    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # --- Build the WHERE clause for date filtering ---
        where_clause = ""
        params = []
        if days is not None:
            where_clause = "WHERE submitted_at >= DATE_SUB(NOW(), INTERVAL %s DAY)"
            params.append(days)

        # --- Fetch all data in one go ---
        
        # 1. Overview Stats
        cursor.execute(f"SELECT COUNT(*) as total_issues FROM issues {where_clause}", tuple(params))
        total_issues = cursor.fetchone()['total_issues']
        
        resolved_query = f"SELECT COUNT(*) as resolved_count FROM issues {where_clause + ' AND' if where_clause else 'WHERE'} status = 'Resolved'"
        cursor.execute(resolved_query, tuple(params))
        resolved_count = cursor.fetchone()['resolved_count']
        resolution_rate = (resolved_count / total_issues * 100) if total_issues > 0 else 0

        cursor.execute(f"SELECT AVG(DATEDIFF(updated_at, submitted_at)) as avg_response_days FROM issues {where_clause + ' AND' if where_clause else 'WHERE'} status != 'Submitted'", tuple(params))
        avg_response_days_result = cursor.fetchone()
        avg_response_days = float(avg_response_days_result['avg_response_days']) if avg_response_days_result and avg_response_days_result['avg_response_days'] is not None else 0.0

        # 2. Distributions
        cursor.execute(f"SELECT status, COUNT(*) as count FROM issues {where_clause} GROUP BY status", tuple(params))
        status_distribution = cursor.fetchall()

        cursor.execute(f"SELECT priority, COUNT(*) as count FROM issues {where_clause} GROUP BY priority", tuple(params))
        priority_distribution = cursor.fetchall()
        
        category_query = f"""
            SELECT 
                CASE WHEN customIssueType IS NOT NULL AND customIssueType != '' THEN customIssueType ELSE issueCategory END as issueCategory, 
                COUNT(*) as count 
            FROM issues {where_clause} 
            GROUP BY 1
            ORDER BY count DESC LIMIT 10
        """
        cursor.execute(category_query, tuple(params))
        category_distribution = cursor.fetchall()

        cursor.execute(f"SELECT city, COUNT(*) as count FROM issues {where_clause + ' AND' if where_clause else 'WHERE'} city IS NOT NULL AND city != '' GROUP BY city ORDER BY count DESC LIMIT 10", tuple(params))
        location_data = cursor.fetchall()

        # 3. Trend Data
        trend_query = f"""
            SELECT DATE(submitted_at) as date, COUNT(*) as count 
            FROM issues {where_clause} 
            GROUP BY DATE(submitted_at) 
            ORDER BY date ASC
        """
        cursor.execute(trend_query, tuple(params))
        trend_data = cursor.fetchall()
        for item in trend_data:
            if isinstance(item.get('date'), datetime):
                item['date'] = item['date'].strftime('%Y-%m-%d')

        # 4. Other Stats (not time-bound)
        cursor.execute("SELECT COUNT(DISTINCT email) as users_with_submissions FROM issues")
        user_stats = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) as total_chats FROM chat_logs")
        chat_stats = cursor.fetchone()

        cursor.execute("SELECT AVG(rating) as avg_rating FROM feedback")
        feedback_stats_result = cursor.fetchone()
        feedback_stats = {'avg_rating': float(feedback_stats_result['avg_rating']) if feedback_stats_result and feedback_stats_result['avg_rating'] is not None else 0.0}

        # --- Assemble the final response ---
        response_data = {
            'status': 'success',
            'data': {
                'overview': {
                    'total_issues': total_issues,
                    'resolution_rate': resolution_rate,
                    'avg_response_days': avg_response_days
                },
                'status_distribution': status_distribution,
                'priority_distribution': priority_distribution,
                'category_distribution': category_distribution,
                'location_data': location_data,
                'trend_data': trend_data,
                'user_stats': user_stats,
                'chat_stats': chat_stats,
                'feedback_stats': feedback_stats
            }
        }
        return jsonify(response_data)

    except mysql.connector.Error as err:
        print(f"Database error on comprehensive analytics: {err}")
        return jsonify({'status': 'error', 'message': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()


# Add these NEW functions to your app.py file.

# In app.py, replace the existing admin_api_user_engagement function with this corrected version.

@app.route('/admin/api/detailed-analytics/user-engagement')
def admin_api_user_engagement():
    if 'admin_id' not in session: return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        # CORRECTED QUERY (V3): This version is fully compliant with 'only_full_group_by'
        # by grouping by all non-aggregated columns from the 'users' table.
        query = """
            SELECT 
                u.email,
                CONCAT(u.first_name, ' ', u.last_name) as fullName,
                COUNT(i.id) as total_issues,
                SUM(CASE WHEN i.status = 'Resolved' THEN 1 ELSE 0 END) as resolved_issues,
                MAX(i.submitted_at) as last_activity,
                COALESCE(cl.chat_sessions, 0) as chat_sessions
            FROM users u
            LEFT JOIN issues i ON u.email = i.email
            LEFT JOIN (
                SELECT user_id, COUNT(DISTINCT DATE(created_at)) as chat_sessions 
                FROM chat_logs GROUP BY user_id
            ) cl ON u.id = cl.user_id
            GROUP BY u.id, u.email, u.first_name, u.last_name, cl.chat_sessions
            ORDER BY total_issues DESC;
        """
        cursor.execute(query)
        data = cursor.fetchall()
        for row in data:
            if isinstance(row.get('last_activity'), datetime):
                row['last_activity'] = row['last_activity'].strftime('%Y-%m-%d')
        return jsonify({'status': 'success', 'data': data})
    except Exception as e:
        print(f"Error in user engagement analytics: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500
    finally:
        cursor.close()
        conn.close()

# Add these NEW functions to your app.py file for the detailed analytics tables.

@app.route('/admin/api/detailed-analytics/resolution')
def admin_api_resolution_analysis():
    if 'admin_id' not in session: return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT 
                issue_id,
                CASE WHEN customIssueType IS NOT NULL AND customIssueType != '' THEN customIssueType ELSE issueCategory END as category,
                priority,
                status,
                submitted_at,
                DATEDIFF(NOW(), submitted_at) as days_pending,
                city,
                fullName as submitter
            FROM issues
            ORDER BY submitted_at DESC
            LIMIT 50;
        """
        cursor.execute(query)
        data = cursor.fetchall()
        for row in data:
            if isinstance(row.get('submitted_at'), datetime):
                row['submitted_at'] = row['submitted_at'].strftime('%Y-%m-%d')
        return jsonify({'status': 'success', 'data': data})
    except Exception as e:
        print(f"Error in resolution analytics: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/api/detailed-analytics/geographic')
def admin_api_geographic_analysis():
    if 'admin_id' not in session: return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT
                city as location,
                COUNT(*) as total_issues,
                (SELECT issueCategory FROM issues i2 WHERE i2.city = i.city GROUP BY issueCategory ORDER BY COUNT(*) DESC LIMIT 1) as top_category,
                AVG(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) * 100 as resolution_rate,
                AVG(DATEDIFF(updated_at, submitted_at)) as response_time
            FROM issues i
            WHERE city IS NOT NULL AND city != ''
            GROUP BY city
            ORDER BY total_issues DESC
            LIMIT 20;
        """
        cursor.execute(query)
        data = cursor.fetchall()
        return jsonify({'status': 'success', 'data': data})
    except Exception as e:
        print(f"Error in geographic analytics: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/api/detailed-analytics/feedback')
def admin_api_feedback_analysis():
    if 'admin_id' not in session: return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) as total_feedbacks FROM feedback")
        total_feedbacks = cursor.fetchone()['total_feedbacks']
        
        cursor.execute("SELECT AVG(rating) as avg_rating FROM feedback")
        avg_rating_result = cursor.fetchone()
        avg_rating = float(avg_rating_result['avg_rating']) if avg_rating_result and avg_rating_result['avg_rating'] is not None else 0.0

        # For simplicity, response rate and satisfaction score are mocked here.
        # In a real app, these would require more complex logic.
        response_rate = 95.2 
        satisfaction_score = (avg_rating / 5.0) * 100

        return jsonify({
            'status': 'success',
            'data': {
                'total_feedbacks': total_feedbacks,
                'avg_rating': avg_rating,
                'response_rate': response_rate,
                'satisfaction_score': satisfaction_score
            }
        })
    except Exception as e:
        print(f"Error in feedback analytics: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/admin/api/detailed-analytics/category-analysis')
def admin_api_category_analysis():
    if 'admin_id' not in session: return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT 
                CASE WHEN customIssueType IS NOT NULL AND customIssueType != '' THEN customIssueType ELSE issueCategory END as category,
                COUNT(*) as total_issues,
                SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) as resolved,
                SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
                SUM(CASE WHEN status = 'Submitted' THEN 1 ELSE 0 END) as pending,
                AVG(DATEDIFF(updated_at, submitted_at)) as avg_response_time
            FROM issues
            GROUP BY category
            ORDER BY total_issues DESC;
        """
        cursor.execute(query)
        data = cursor.fetchall()
        return jsonify({'status': 'success', 'data': data})
    except Exception as e:
        print(f"Error in category analysis: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/admin/api/detailed-analytics/activity-patterns')
def admin_api_activity_patterns():
    if 'admin_id' not in session: return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        # Hourly Pattern
        cursor.execute("SELECT HOUR(submitted_at) as hour, COUNT(*) as count FROM issues GROUP BY hour ORDER BY hour ASC;")
        hourly_data = cursor.fetchall()

        # Weekly Pattern
        cursor.execute("SELECT DAYNAME(submitted_at) as day, DAYOFWEEK(submitted_at) as day_num, COUNT(*) as count FROM issues GROUP BY day, day_num ORDER BY day_num ASC;")
        weekly_data = cursor.fetchall()
        
        return jsonify({
            'status': 'success', 
            'hourly': hourly_data,
            'weekly': weekly_data
        })
    except Exception as e:
        print(f"Error in activity patterns: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500
    finally:
        cursor.close()
        conn.close()

# ADD THIS NEW ROUTE FOR DELETING THE GUIDE
@app.route('/admin/api/guide', methods=['DELETE'])
def admin_api_delete_guide():
    if 'admin_id' not in session: 
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    if not conn: 
        return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        # We assume the guide has ID=1, or we can delete all guides if there should only ever be one.
        cursor.execute("DELETE FROM guides WHERE id = 1")
        conn.commit()
        if cursor.rowcount > 0:
            return jsonify({'status': 'success', 'message': 'Guide details deleted successfully.'})
        else:
            return jsonify({'status': 'error', 'message': 'Guide not found or already deleted.'}), 404
    except Exception as e:
        conn.rollback()
        print(f"Error deleting guide: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to delete guide.'}), 500
    finally:
        cursor.close()
        conn.close()

# REPLACE your existing team_details function with this
@app.route('/team-details')
def team_details():
    conn = get_db_connection()
    if not conn:
        # If the database fails, render the page with an empty list
        flash('Could not load team details at this time.', 'danger')
        return render_template('team-details.html', developers=[])

    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch all developers from the database, ensuring the team leader appears first
        cursor.execute("SELECT * FROM developers ORDER BY is_leader DESC, display_order ASC, id ASC")
        developers = cursor.fetchall()
        return render_template('team-details.html', developers=developers)
    except Exception as e:
        print(f"Error fetching team details: {e}")
        return render_template('team-details.html', developers=[])
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# =============================================================================
# ADMIN PROFILE SECTION
# =============================================================================

# Route to render the admin profile page
@app.route('/admin/profile')
def admin_profile():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    return render_template('admin/admin_profile.html', username=session.get('admin_username'))

# API to get admin profile data
@app.route('/admin/api/profile', methods=['GET'])
def get_admin_profile():
    if 'admin_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, username, created_at FROM admins WHERE id = %s", (session['admin_id'],))
        admin = cursor.fetchone()
        if not admin:
            return jsonify({'status': 'error', 'message': 'Admin not found'}), 404
        return jsonify({'status': 'success', 'admin': admin})
    finally:
        cursor.close()
        conn.close()

# API to update admin username
@app.route('/admin/api/profile', methods=['POST'])
def update_admin_profile():
    if 'admin_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    new_username = data.get('username')

    if not new_username:
        return jsonify({'status': 'error', 'message': 'Username cannot be empty.'}), 400

    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE admins SET username = %s WHERE id = %s", (new_username, session['admin_id']))
        conn.commit()
        
        # Update the session with the new username
        session['admin_username'] = new_username
        
        return jsonify({'status': 'success', 'message': 'Username updated successfully!'})
    except mysql.connector.Error as err:
        conn.rollback()
        if err.errno == 1062: # Duplicate entry error
            return jsonify({'status': 'error', 'message': 'That username is already taken.'}), 409
        return jsonify({'status': 'error', 'message': 'An error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# API to update admin password
@app.route('/admin/api/password', methods=['POST'])
def update_admin_password():
    if 'admin_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')

    if not all([current_password, new_password, confirm_password]):
        return jsonify({'status': 'error', 'message': 'All password fields are required.'}), 400
    if new_password != confirm_password:
        return jsonify({'status': 'error', 'message': 'New passwords do not match.'}), 400

    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT password FROM admins WHERE id = %s", (session['admin_id'],))
        admin = cursor.fetchone()

        if not admin or not bcrypt.checkpw(current_password.encode('utf-8'), admin['password'].encode('utf-8')):
            return jsonify({'status': 'error', 'message': 'Incorrect current password.'}), 400
        
        hashed_new_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute("UPDATE admins SET password = %s WHERE id = %s", (hashed_new_password, session['admin_id']))
        conn.commit()
        
        return jsonify({'status': 'success', 'message': 'Password changed successfully!'})
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({'status': 'error', 'message': 'An error occurred during password update.'}), 500
    finally:
        cursor.close()
        conn.close()


# --- ADD THIS NEW ROUTE FOR DOWNLOADING LOGS ---
@app.route('/admin/download-logs')
def admin_download_logs():
    if 'admin_id' not in session:
        flash('You must be an admin to perform this action.', 'danger')
        return redirect(url_for('admin_login'))
    try:
        # The log file is created in the root directory of your project
        log_path = os.path.join(app.root_path, 'app.log')
        if os.path.exists(log_path):
            return send_file(log_path, as_attachment=True)
        else:
            flash('Log file not found. It will be created once the app logs an event.', 'warning')
            return redirect(url_for('admin_profile'))
    except Exception as e:
        app.logger.error(f"Error downloading log file: {e}")
        flash('An error occurred while trying to download the log file.', 'danger')
        return redirect(url_for('admin_profile'))

# =============================================================================
# API FOR HELP & SUPPORT PAGE
# =============================================================================

# NEW: API to provide developer emails for the help & support page
@app.route('/api/developers')
def api_developers():
    """Provides a public list of developer names and emails."""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetches name and email of all developers, ordered for consistency
        cursor.execute("SELECT name, email FROM developers ORDER BY is_leader DESC, display_order ASC, id ASC")
        developers = cursor.fetchall()
        
        # Filter out developers who do not have an email
        developers_with_email = [dev for dev in developers if dev.get('email')]
        
        return jsonify(developers_with_email)

    except Exception as e:
        print(f"Error fetching developer emails: {e}")
        return jsonify({'error': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# ADD THIS ENTIRE BLOCK for Announcement Management to app.py

# =============================================================================
# ANNOUNCEMENTS API ROUTES
# =============================================================================

# API for Admins to GET and POST announcements
# =============================================================================
# ANNOUNCEMENTS API ROUTES
# =============================================================================

# API for Admins to GET and POST announcements
@app.route('/admin/api/announcements', methods=['GET', 'POST'])
def admin_api_announcements():
    if 'admin_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        if request.method == 'GET':
            cursor.execute("SELECT * FROM announcements ORDER BY created_at DESC")
            announcements = cursor.fetchall()
            
            # --- START: FIX ---
            # Correctly handle timezone conversion
            for ann in announcements:
                if isinstance(ann.get('created_at'), datetime):
                    # 1. Assume the DB time is local (server time) and make it timezone-aware.
                    local_time = ann['created_at'].astimezone() 
                    # 2. Convert the local time to UTC.
                    utc_time = local_time.astimezone(timezone.utc)
                    # 3. Format the correct UTC time into an ISO string with the 'Z' designator.
                    ann['created_at'] = utc_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            # --- END: FIX ---
            
            return jsonify({'status': 'success', 'announcements': announcements})

        if request.method == 'POST':
            data = request.get_json()
            title = data.get('title')
            content = data.get('content')
            if not title or not content:
                return jsonify({'status': 'error', 'message': 'Title and content are required.'}), 400
            
            cursor.execute("INSERT INTO announcements (title, content) VALUES (%s, %s)", (title, content))
            conn.commit()
            return jsonify({'status': 'success', 'message': 'Announcement posted successfully!'}), 201
            
    except Exception as e:
        print(f"Error in announcements API: {e}")
        conn.rollback()
        return jsonify({'status': 'error', 'message': 'An internal server error occurred.'}), 500
    finally:
        cursor.close()
        conn.close()

# API for Admins to DELETE an announcement
@app.route('/admin/api/announcements/<int:announcement_id>', methods=['DELETE'])
def admin_api_delete_announcement(announcement_id):
    if 'admin_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({'status': 'error', 'message': 'Announcement not found.'}), 404
        return jsonify({'status': 'success', 'message': 'Announcement deleted successfully.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': 'Failed to delete announcement.'}), 500
    finally:
        cursor.close()
        conn.close()

# In app.py

# =============================================================================
# === PASTE THIS CORRECTED FUNCTION INTO YOUR APP.PY FILE =====================
# =============================================================================

# API for USERS to fetch announcements (to be used on user-side pages)
@app.route('/api/announcements')
def api_get_announcements():
    if 'user_id' not in session: # Ensure user is logged in
        return jsonify({'error': 'User not authenticated'}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch the 5 most recent announcements
        cursor.execute("SELECT title, content, created_at FROM announcements ORDER BY created_at DESC LIMIT 5")
        announcements = cursor.fetchall()
        
        # --- START: FIX ---
        # Add the same timezone conversion logic from the admin route
        for ann in announcements:
            if isinstance(ann.get('created_at'), datetime):
                # 1. Assume the DB time is local and make it timezone-aware.
                local_time = ann['created_at'].astimezone() 
                # 2. Convert the local time to proper UTC.
                utc_time = local_time.astimezone(timezone.utc)
                # 3. Format into the standard ISO string that JavaScript expects.
                ann['created_at'] = utc_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        # --- END: FIX ---

        return jsonify(announcements)
    except Exception as e:
        print(f"Error fetching announcements for user: {e}")
        return jsonify({'error': 'Could not retrieve announcements.'}), 500
    finally:
        cursor.close()
        conn.close()

# ADD THIS NEW ROUTE to app.py for updating announcements

@app.route('/admin/api/announcements/<int:announcement_id>', methods=['POST'])
def admin_api_update_announcement(announcement_id):
    if 'admin_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    
    try:
        data = request.get_json()
        title = data.get('title')
        content = data.get('content')

        if not title or not content:
            return jsonify({'status': 'error', 'message': 'Title and content are required.'}), 400
        
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE announcements SET title = %s, content = %s WHERE id = %s",
            (title, content, announcement_id)
        )
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({'status': 'error', 'message': 'Announcement not found.'}), 404
            
        return jsonify({'status': 'success', 'message': 'Announcement updated successfully!'})

    except Exception as e:
        conn.rollback()
        print(f"Error updating announcement: {e}")
        return jsonify({'status': 'error', 'message': 'An internal server error occurred.'}), 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# In app.py

# ADD THIS NEW ROUTE for deleting a profile photo
@app.route('/api/user/profile/photo', methods=['DELETE'])
def delete_profile_photo():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed.'}), 500
    
    cursor = conn.cursor()
    try:
        # Set the photo filename to NULL in the database
        cursor.execute(
            "UPDATE users SET profile_photo_filename = NULL WHERE id = %s",
            (session['user_id'],)
        )
        conn.commit()
        
        # The frontend needs the URL for the default avatar to update the UI
        default_photo_url = url_for('static', filename='images/female_avatar.png')
        
        return jsonify({
            'status': 'success',
            'message': 'Profile photo removed!',
            'default_photo_url': default_photo_url
        })
    except Exception as e:
        conn.rollback()
        print(f"Error removing profile photo: {e}")
        return jsonify({'status': 'error', 'message': 'Error removing profile photo'}), 500
    finally:
        cursor.close()
        conn.close()
    





# -----------------------------------------------------------------------------
# Main Execution Block
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    create_tables()
    create_chat_tables() # Ensure chat tables are created on startup
    app.run(debug=True)

