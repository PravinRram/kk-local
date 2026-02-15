from PIL import Image
import os
from werkzeug.utils import secure_filename
import uuid

# Use absolute path relative to this file's directory (merged/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_filename(original_filename):
    ext = original_filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    return unique_name

def compress_image(image_path, quality=85):
    # Compress image to reduce file size
    img = Image.open(image_path)
    
    # Convert RGBA to RGB if necessary
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    
    # Save with compression
    img.save(image_path, optimize=True, quality=quality)
    return image_path

def create_thumbnail(image_path, thumbnail_path, size=(150, 150)):
    # Create a thumbnail of the image
    img = Image.open(image_path)
    img.thumbnail(size, Image.Resampling.LANCZOS)
    
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    
    img.save(thumbnail_path, optimize=True, quality=85)
    return thumbnail_path

def process_profile_picture(file):
    # Process and save profile picture
    if not file or not allowed_file(file.filename):
        return None
    
    filename = generate_unique_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, 'profiles', filename)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Save file
    file.save(filepath)
    
    # Compress
    compress_image(filepath, quality=90)
    
    # Create thumbnail
    thumb_filename = f"thumb_{filename}"
    thumb_path = os.path.join(UPLOAD_FOLDER, 'profiles', thumb_filename)
    create_thumbnail(filepath, thumb_path, size=(150, 150))
    
    return f"/static/uploads/profiles/{filename}"

def process_post_image(file):
    # Process and save post image
    if not file or not allowed_file(file.filename):
        return None
    
    filename = generate_unique_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, 'posts', filename)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Save file
    file.save(filepath)
    
    # Compress
    compress_image(filepath, quality=85)
    
    return f"/static/uploads/posts/{filename}"

def process_forum_image(file):
    # Process and save forum image
    if not file or not allowed_file(file.filename):
        return None
    
    filename = generate_unique_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, 'forums', filename)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Save file
    file.save(filepath)
    
    # Compress
    compress_image(filepath, quality=85)
    
    return f"/static/uploads/forums/{filename}"