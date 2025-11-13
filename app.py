from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['SECRET_KEY'] = 'your-secret-key'  # Replace with a secure key
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # Limit file size to 100MB
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'mp4', 'webm'}

# *** UPDATED: Set database path for Vercel ***
DB_PATH = '/tmp/database.db'

# Ensure upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Database setup
def init_db():
    try:
        # *** UPDATED: Use the DB_PATH variable ***
        with sqlite3.connect(DB_PATH) as conn:
            # Original media table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    type TEXT NOT NULL,  -- 'image' or 'video'
                    filename TEXT NOT NULL,
                    upload_date TEXT NOT NULL
                )
            ''')
            
            # Table to store reactions (likes)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    media_id INTEGER NOT NULL,
                    likes INTEGER DEFAULT 0,
                    FOREIGN KEY (media_id) REFERENCES media (id)
                )
            ''')
            conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

# Check if file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    init_db() # Ensure DB is created on Vercel's cold start
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_media():
    if request.method == 'POST':
        title = request.form.get('title')
        file = request.files.get('file')

        if not title or not file:
            flash('Title and file are required!', 'error')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Only JPG, PNG, MP4, or WebM files are allowed!', 'error')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        try:
            file.save(file_path)
            file_ext = filename.rsplit('.', 1)[1].lower()
            media_type = 'image' if file_ext in {'jpg', 'jpeg', 'png'} else 'video'

            # *** UPDATED: Use the DB_PATH variable ***
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO media (title, type, filename, upload_date) VALUES (?, ?, ?, ?)',
                    (title, media_type, unique_filename, datetime.now().strftime('%Y-%m-%d'))
                )
                new_media_id = cursor.lastrowid
                cursor.execute(
                    'INSERT INTO reactions (media_id, likes) VALUES (?, 0)',
                    (new_media_id,)
                )
                conn.commit()

            flash('Media uploaded successfully!', 'success')
            return redirect(url_for('media'))

        except (sqlite3.Error, OSError) as e:
            flash(f'Error uploading media: {str(e)}', 'error')
            return redirect(request.url)

    return render_template('upload_media.html')

@app.route('/media')
def media():
    try:
        # *** UPDATED: Use the DB_PATH variable ***
        with sqlite3.connect(DB_PATH) as conn:
            sql_query = '''
                SELECT m.id, m.title, m.type, m.filename, m.upload_date, COALESCE(r.likes, 0) as likes
                FROM media m
                LEFT JOIN reactions r ON m.id = r.media_id
                ORDER BY m.upload_date DESC, m.id DESC
            '''
            cursor = conn.execute(sql_query)
            media_items = cursor.fetchall()
            
        return render_template('media.html', media_items=media_items)
    except sqlite3.Error as e:
        flash(f'Error fetching media: {str(e)}', 'error')
        return render_template('media.html', media_items=[])

@app.route('/react/like/<int:media_id>', methods=['POST'])
def like_media(media_id):
    try:
        # *** UPDATED: Use the DB_PATH variable ***
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE reactions SET likes = likes + 1 WHERE media_id = ?',
                (media_id,)
            )
            cursor.execute(
                'SELECT likes FROM reactions WHERE media_id = ?',
                (media_id,)
            )
            result = cursor.fetchone()
            new_like_count = result[0] if result else 0
            conn.commit()
            return jsonify({'likes': new_like_count})
            
    except sqlite3.Error as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download/<filename>')
def download(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        flash('File not found!', 'error')
        return redirect(url_for('media'))

@app.route('/delete/<int:id>')
def delete(id):
    try:
        # *** UPDATED: Use the DB_PATH variable ***
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('SELECT filename FROM media WHERE id = ?', (id,))
            result = cursor.fetchone()
            if not result:
                flash('Media not found!', 'error')
                return redirect(url_for('media'))

            filename = result[0]
            conn.execute('DELETE FROM media WHERE id = ?', (id,))
            conn.execute('DELETE FROM reactions WHERE media_id = ?', (id,))
            conn.commit()

            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)

        flash('Media deleted successfully!', 'success')
        return redirect(url_for('media'))

    except (sqlite3.Error, OSError) as e:
        flash(f'Error deleting media: {str(e)}', 'error')
        return redirect(url_for('media'))

# The if __name__ == '__main__': block is not needed for Vercel,
# but it's fine to leave it for local testing.
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
