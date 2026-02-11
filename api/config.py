import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "postgresql://localhost/leadgen")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ACCESS_EXPIRY = 3600  # 1 hour
    JWT_REFRESH_EXPIRY = 7 * 24 * 3600  # 7 days
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
