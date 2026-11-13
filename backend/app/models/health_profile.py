from sqlalchemy import JSON, func

from app.extensions import db


class HealthProfile(db.Model):
    __tablename__ = "health_profiles"

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    date_of_birth = db.Column(db.Date, nullable=True)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(50), nullable=True)
    height_cm = db.Column(db.Numeric(5, 2), nullable=True)
    weight_kg = db.Column(db.Numeric(5, 2), nullable=True)
    activity_level = db.Column(db.String(30), nullable=True)
    dietary_preferences = db.Column(JSON, nullable=True)
    health_goal = db.Column(db.String(100), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = db.relationship("User", back_populates="health_profile")
