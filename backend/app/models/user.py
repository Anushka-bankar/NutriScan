from sqlalchemy import func

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    health_profile = db.relationship(
        "HealthProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    products = db.relationship(
        "Product",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    product_history = db.relationship(
        "ProductAnalysisHistory",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    watchlist = db.relationship(
        "ProductWatchlist",
        back_populates="user",
        cascade="all, delete-orphan",
    )
