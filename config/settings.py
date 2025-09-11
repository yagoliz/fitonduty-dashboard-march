"""Configuration settings for FitonDuty March Dashboard"""

import os
from datetime import timedelta


class Config:
    """Base configuration"""
    
    # Flask/Dash settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database
    DATABASE_URL = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres:password@localhost:5432/fitonduty_march'
    )
    
    # Session settings
    SESSION_COOKIE_SECURE = os.environ.get('ENV', 'development') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # Dashboard settings
    DASHBOARD_TITLE = "FitonDuty March Dashboard"
    BOOTSTRAP_THEME = "bootstrap"  # or "cerulean", "flatly", etc.
    
    # Data refresh settings
    DATA_REFRESH_INTERVAL = 30  # seconds for auto-refresh (if implemented)


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