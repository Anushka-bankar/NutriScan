from sqlalchemy import UniqueConstraint, func

from app.extensions import db


class ProductAnalysisHistory(db.Model):
    __tablename__ = "product_analysis_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_snapshot = db.Column(db.JSON, nullable=False)
    analyzed_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user = db.relationship("User", back_populates="product_history")
    product = db.relationship("Product", back_populates="analysis_history")


class ProductWatchlist(db.Model):
    __tablename__ = "product_watchlist"
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_watchlist_user_product"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_snapshot = db.Column(db.JSON, nullable=False)
    added_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user = db.relationship("User", back_populates="watchlist")
    product = db.relationship("Product", back_populates="watchlist_entries")
