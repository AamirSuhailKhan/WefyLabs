"""
BeetleLabs Config Module
Re-exports settings from app.common.config.validated_settings for backward compatibility.
"""
from app.common.config.validated_settings import EnterpriseSettings, load_settings

Settings = EnterpriseSettings
settings = load_settings()
