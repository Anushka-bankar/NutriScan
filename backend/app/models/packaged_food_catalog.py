from sqlalchemy import UniqueConstraint, func

from app.extensions import db


class PackagedFoodCatalog(db.Model):
    __tablename__ = "packaged_food_catalog"
    __table_args__ = (
        UniqueConstraint(
            "source_name",
            "source_row_id",
            name="uq_packaged_food_catalog_source_row",
        ),
        db.Index("ix_packaged_food_catalog_product_name", "product_name"),
        db.Index("ix_packaged_food_catalog_brand_name", "brand_name"),
        db.Index("ix_packaged_food_catalog_category", "category"),
        db.Index("ix_packaged_food_catalog_sub_category", "sub_category"),
    )

    id = db.Column(db.Integer, primary_key=True)
    source_name = db.Column(db.String(64), nullable=False)
    source_row_id = db.Column(db.Integer, nullable=False)
    source_file_sha256 = db.Column(db.String(64), nullable=False)
    source_row_sha256 = db.Column(db.String(64), nullable=False)

    product_name = db.Column(db.String(255), nullable=False)
    brand_name = db.Column(db.String(150), nullable=True)
    category = db.Column(db.String(100), nullable=True)
    sub_category = db.Column(db.String(150), nullable=True)
    ingredients = db.Column(db.Text, nullable=True)
    serving_size_g = db.Column(db.Numeric(10, 2), nullable=True)

    calories_kcal_per_serving = db.Column(db.Numeric(18, 6), nullable=True)
    carbohydrates_g_per_serving = db.Column(db.Numeric(18, 6), nullable=True)
    protein_g_per_serving = db.Column(db.Numeric(18, 6), nullable=True)
    total_fat_g_per_serving = db.Column(db.Numeric(18, 6), nullable=True)
    saturated_fat_g_per_serving = db.Column(db.Numeric(18, 6), nullable=True)
    trans_fat_g_per_serving = db.Column(db.Numeric(18, 6), nullable=True)
    sugar_g_per_serving = db.Column(db.Numeric(18, 6), nullable=True)
    sodium_mg_per_serving = db.Column(db.Numeric(18, 6), nullable=True)
    dietary_fiber_g_per_serving = db.Column(db.Numeric(18, 6), nullable=True)
    cholesterol_mg_per_serving = db.Column(db.Numeric(18, 6), nullable=True)
    calcium_mg_per_serving = db.Column(db.Numeric(18, 6), nullable=True)
    iron_mg_per_serving = db.Column(db.Numeric(18, 6), nullable=True)

    vitamin_details = db.Column(db.Text, nullable=True)
    price_inr = db.Column(db.Numeric(10, 2), nullable=True)
    source_of_data = db.Column(db.String(255), nullable=True)
    collection_date = db.Column(db.Date, nullable=True)
    collected_by = db.Column(db.String(255), nullable=True)
    remarks = db.Column(db.Text, nullable=True)

    nutrition_basis = db.Column(
        db.String(32), nullable=False, default="per_serving_inferred"
    )
    source_row_raw = db.Column(db.JSON, nullable=False)
    quality_flags = db.Column(db.JSON, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
