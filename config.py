import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Base configuration
    SECRET_KEY = os.urandom(24)
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    
    # Database configuration (Unified)
    _default_db_path = os.path.join(os.getcwd(), "instance", "kampongkonek.db")
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f"sqlite:///{_default_db_path}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Uploads
    UPLOAD_FOLDER = os.path.join(os.getcwd(), "instance", "uploads")

    # Admin secret key
    ADMIN_SECRET_KEY = os.environ.get('ADMIN_SECRET_KEY', 'ADMIN_SECRET_KEY_2025')
    
    # Forum creation requirements
    FORUM_MIN_ACCOUNT_AGE_DAYS = 7
    FORUM_MAX_PER_USER = 5
    
    # Content limits
    POST_MAX_LENGTH = 280
    COMMENT_MAX_LENGTH = 280
    BIO_MAX_LENGTH = 500
    USERNAME_MIN_LENGTH = 3
    USERNAME_MAX_LENGTH = 50
    PASSWORD_MIN_LENGTH = 6
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024 # 32MB max upload
    
    # Pagination
    POSTS_PER_PAGE = 50
    NOTIFICATIONS_PER_PAGE = 50
    
    # Available interests
    INTERESTS = [
        'Technology', 'Sports', 'Art', 'Gaming', 'Cooking', 
        'Travel', 'Entertainment', 'Identity', 'Music', 'Books', 
        'Fitness', 'Fashion', 'Education', 'Business', 'Science', 
        'Politics', 'Health'
    ]

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    ADMIN_SECRET_KEY = os.environ.get('ADMIN_SECRET_KEY')

class TestingConfig(Config):
    DEBUG = True
    TESTING = True
    DB_NAME = 'kampongkonek'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
