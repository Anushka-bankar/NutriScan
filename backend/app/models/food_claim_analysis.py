from sqlalchemy import func

from app.extensions import db


class ProductFoodClaimAnalysis(db.Model):
    __tablename__ = "product_food_claim_analyses"

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
    product_identity_snapshot = db.Column(db.Integer, nullable=True, index=True)
    product_name_snapshot = db.Column(db.String(160), nullable=False)
    claim_text = db.Column(db.Text, nullable=False)
    input_source = db.Column(db.String(30), nullable=False)
    product_snapshot = db.Column(db.JSON, nullable=False)
    analysis_result = db.Column(db.JSON, nullable=False)
    analyzed_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user = db.relationship("User", back_populates="food_claim_analyses")
    product = db.relationship("Product", back_populates="food_claim_analyses")
