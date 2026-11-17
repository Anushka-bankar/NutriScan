const CATEGORIES = [
  ['grains_cereals', 'Grains & cereals'],
  ['snacks', 'Snacks'],
  ['beverages', 'Beverages'],
  ['dairy', 'Dairy'],
  ['dairy_alternatives', 'Dairy alternatives'],
  ['meat_poultry', 'Meat & poultry'],
  ['seafood', 'Seafood'],
  ['plant_protein', 'Plant proteins'],
  ['fruits_vegetables', 'Fruits & vegetables'],
  ['condiments_sauces', 'Condiments & sauces'],
  ['prepared_meals', 'Prepared meals'],
  ['bakery', 'Bakery'],
  ['other', 'Other'],
];

const NUTRIENTS = [
  ['energy_kj', 'Energy', 'kJ', 3766, 1],
  ['calories_kcal', 'Calories', 'kcal', 900, 1],
  ['carbohydrates_g', 'Carbohydrates', 'g', 100, 2],
  ['sugars_g', 'Total sugar', 'g', 100, 2],
  ['protein_g', 'Protein', 'g', 100, 2],
  ['total_fat_g', 'Total fat', 'g', 100, 2],
  ['saturated_fat_g', 'Saturated fat', 'g', 100, 2],
  ['fibre_g', 'Fibre', 'g', 100, 2],
  ['sodium_mg', 'Sodium', 'mg', 100000, 2],
];

export default function ProductReviewForm({
  form,
  sourceType,
  sourceLabel,
  warnings,
  uncertainFields,
  reviewConfirmed,
  onReviewConfirmed,
  onChange,
  onSubmit,
  loading,
  error,
  imageUrl,
}) {
  const isBarcode = sourceType === 'open_food_facts';

  return (
    <form className="product-entry-form scan-review" onSubmit={onSubmit} noValidate>
      <div className="scan-review__heading">
        <div>
          <p className="eyebrow">Review before saving</p>
          <h2>{form.name || 'Confirm product details'}</h2>
          <p>
            {isBarcode
              ? 'Details came from Open Food Facts. Check them against the package and edit any incorrect fields.'
              : 'OCR can misread text. Check the extracted fields against the package and correct anything needed.'}
          </p>
        </div>
        <span className="source-badge">{sourceLabel}</span>
      </div>

      {imageUrl && (
        <div className="barcode-product-image">
          <img alt={`${form.name || 'Product'} package`} onError={(event) => { event.currentTarget.hidden = true; }} src={imageUrl} />
          <span>Product image from Open Food Facts</span>
        </div>
      )}

      <div className="data-warning" role="note">
        <strong>{isBarcode ? 'Community product data' : 'Image stays on this device'}</strong>
        <span>
          {isBarcode
            ? 'Only the barcode was sent to Open Food Facts. Returned data may be incomplete or incorrect; imported values retain their source attribution.'
            : 'Only the product details you confirm are sent to NutriScan. OCR data is not independently verified.'}
        </span>
      </div>

      {warnings.length > 0 && (
        <div className="ocr-review-alert" role="status">
          <strong>Review needed</strong>
          <ul>{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
          <p>Unavailable facts remain blank; NutriScan does not fill in missing values.</p>
        </div>
      )}

      <div className="entry-fields entry-fields--identity scan-identity">
        <label className="field">
          <span>Product name {uncertainFields.includes('name') && <em>Review</em>}</span>
          <input
            className={uncertainFields.includes('name') ? 'field--needs-review' : ''}
            maxLength="160"
            name="name"
            onChange={onChange}
            required
            value={form.name}
          />
        </label>
        <label className="field">
          <span>Brand <em>{uncertainFields.includes('brand') ? 'Review · optional' : 'Optional'}</em></span>
          <input
            className={uncertainFields.includes('brand') ? 'field--needs-review' : ''}
            maxLength="120"
            name="brand"
            onChange={onChange}
            value={form.brand}
          />
        </label>
        <label className="field">
          <span>Food category {uncertainFields.includes('category') && <em>Review</em>}</span>
          <select
            className={uncertainFields.includes('category') ? 'field--needs-review' : ''}
            name="category"
            onChange={onChange}
            value={form.category}
          >
            <option value="">Select a category</option>
            {CATEGORIES.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Serving size <em>{uncertainFields.includes('serving_size_g') ? 'Review' : 'Optional'}</em></span>
          <div className="input-with-unit">
            <input
              className={uncertainFields.includes('serving_size_g') ? 'field--needs-review' : ''}
              max="5000"
              min="0.01"
              name="serving_size_g"
              onChange={onChange}
              step="0.01"
              type="number"
              value={form.serving_size_g}
            />
            <span>g</span>
          </div>
        </label>
        <label className="field">
          <span>Barcode</span>
          <input
            inputMode="numeric"
            maxLength="14"
            name="barcode"
            onChange={onChange}
            readOnly={isBarcode}
            value={form.barcode}
          />
        </label>
        {!isBarcode && (
          <label className="field scan-basis">
            <span>Nutrition values shown</span>
            <select
              className={uncertainFields.includes('basis') ? 'field--needs-review' : ''}
              name="basis"
              onChange={onChange}
              value={form.basis}
            >
              <option value="100g">Per 100 g</option>
              <option value="serving">Per serving</option>
            </select>
          </label>
        )}
      </div>

      <label className="field scan-ingredients-field">
        <span>Ingredients <em>{uncertainFields.includes('ingredients') ? 'Review · optional' : 'Optional'}</em></span>
        <textarea
          className={uncertainFields.includes('ingredients') ? 'field--needs-review' : ''}
          maxLength="10000"
          name="ingredients"
          onChange={onChange}
          rows="4"
          value={form.ingredients}
        />
      </label>

      <h3 className="entry-section-title">Nutrition values</h3>
      <p className="entry-help">
        {form.basis === 'serving'
          ? 'Confirm the serving size above. Values will be converted to per 100 g before saving.'
          : 'Values are saved per 100 g. Missing values remain unavailable, not zero.'}
      </p>
      <div className="entry-fields entry-fields--nutrients">
        {NUTRIENTS.map(([name, label, unit, max, step]) => (
          <label className="field" key={name}>
            <span>{label} <small>({unit})</small> {uncertainFields.includes(name) && <em>Review</em>}</span>
            <input
              className={uncertainFields.includes(name) ? 'field--needs-review' : ''}
              max={max}
              min="0"
              name={name}
              onChange={onChange}
              step={step}
              type="number"
              value={form[name]}
            />
          </label>
        ))}
      </div>
      {warnings.length > 0 && (
        <label className="ocr-review-confirm">
          <input
            checked={reviewConfirmed}
            onChange={(event) => onReviewConfirmed(event.target.checked)}
            type="checkbox"
          />
          <span>I reviewed the highlighted fields and confirmed any corrections. Missing facts should remain blank.</span>
        </label>
      )}
      {error && <p className="form-message form-message--error" role="alert">{error}</p>}
      <button className="button button--primary entry-submit" disabled={loading} type="submit">
        {loading ? 'Saving product...' : 'Confirm and save product'}
      </button>
    </form>
  );
}
