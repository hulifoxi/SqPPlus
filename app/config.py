import os

# Find the absolute path of the project directory
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) # Go up one level from app dir

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'sqp_plus.db') # Store DB in project root
    SQLALCHEMY_TRACK_MODIFICATIONS = False # Disable modification tracking
    # Add other configurations like database URI later 