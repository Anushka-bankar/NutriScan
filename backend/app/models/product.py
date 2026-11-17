from sqlalchemy import func

from app.extensions import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(160), nullable=False, index=True)
    brand = db.Column(db.String(120), nullable=True)
    barcode = db.Column(db.String(14), nullable=True, index=True)
    ingredients = db.Column(db.Text, nullable=True)
    packaging_text = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    category = db.Column(db.String(50), nullable=True, index=True)
    dietary_tags = db.Column(db.JSON, nullable=True)
    serving_size_g = db.Column(db.Numeric(7, 2), nullable=True)
    energy_kj = db.Column(db.Numeric(8, 2), nullable=True)
    calories_kcal = db.Column(db.Numeric(7, 2), nullable=True)
    carbohydrates_g = db.Column(db.Numeric(7, 2), nullable=True)
    sugars_g = db.Column(db.Numeric(7, 2), nullable=True)
    protein_g = db.Column(db.Numeric(7, 2), nullable=True)
    total_fat_g = db.Column(db.Numeric(7, 2), nullable=True)
    saturated_fat_g = db.Column(db.Numeric(7, 2), nullable=True)
    fibre_g = db.Column(db.Numeric(7, 2), nullable=True)
    sodium_mg = db.Column(db.Numeric(9, 2), nullable=True)
    source_type = db.Column(db.String(30), nullable=False, default="user_entered")
    source_label = db.Column(
        db.String(120), nullable=False, default="User-entered; not independently verified"
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner = db.relationship("User", back_populates="products")
    analysis_history = db.relationship("ProductAnalysisHistory", back_populates="product")
    watchlist_entries = db.relationship("ProductWatchlist", back_populates="product")
    ingredient_analyses = db.relationship(
        "ProductIngredientAnalysis",
        back_populates="product",
        passive_deletes=True,
    )
    food_claim_analyses = db.relationship(
        "ProductFoodClaimAnalysis",
        back_populates="product",
        passive_deletes=True,
    )

    __table_args__ = (
        db.Index(
            "uq_products_user_barcode",
            "created_by",
            "barcode",
            unique=True,
        ),
    )
