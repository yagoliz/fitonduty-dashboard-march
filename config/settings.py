"""Configuration settings for FitonDuty March Dashboard"""

import os
from datetime import timedelta
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    
    # Load .env file from project root
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed, environment variables must be set manually
    pass


def _get_database_url():
    """Build database URL from individual components or use full URL"""
    # Check if full DATABASE_URL is provided
    if 'DATABASE_URL' in os.environ:
        return os.environ['DATABASE_URL']
    
    # Build from individual components
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_port = os.environ.get('DB_PORT', '5432')
    db_name = os.environ.get('DB_NAME', 'fitonduty_march')
    db_user = os.environ.get('DB_USER', 'fitonduty_march')
    db_password = os.environ.get('DB_PASSWORD', 'password')
    
    return f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'


class Config:
    """Base configuration"""
    
    # Flask/Dash settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database
    DATABASE_URL = _get_database_url()
    
    # Session settings  
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # Dashboard settings
    DASHBOARD_TITLE = os.environ.get('DASHBOARD_TITLE', 'FitonDuty March Dashboard')
    BOOTSTRAP_THEME = os.environ.get('BOOTSTRAP_THEME', 'bootstrap')
    
    # Server settings
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 8050))
    
    # Data refresh settings
    DATA_REFRESH_INTERVAL = int(os.environ.get('DATA_REFRESH_INTERVAL', 30))


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    ENV = 'development'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    ENV = 'production'
    SESSION_COOKIE_SECURE = True


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}