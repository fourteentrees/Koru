"""
koru_settings.py

This file will be loaded by settings.py, and will override any default settings defined there. This is where you should be defining custom configuration options for your instance.

PRODUCTION_DEFAULTS will be loaded when KORU_ENVIRON is set to "production" - likewise, DEVELOPMENT_DEFAULTS will be loaded when KORU_ENVIRON is set to "development".
This allows you to have different settings for development and production environments, which is especially useful for things like database configuration, debug mode, etc.

You can set the environment in .env or just export it in your shell.

WARNING: If it is not set, KORU_ENVIRON will default to "development"
"""

KORU_PRODUCTION_DEFAULTS = {
    
}