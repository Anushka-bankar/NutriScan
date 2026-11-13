import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { createProduct } from '../api/products.js';

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

const DIETARY_TAGS = [
  ['vegetarian', 'Vegetarian'],
  ['vegan', 'Vegan'],
  ['pescatarian', 'Pescatarian'],
  ['gluten_free', 'Gluten-free'],
  ['dairy_free', 'Dairy-free'],
  ['halal', 'Halal'],
  ['kosher', 'Kosher'],
];

const NUTRIENTS = [
  ['energy_kj', 'Energy', 'kJ', 0, 3766, 1],
  ['calories_kcal', 'Calories', 'kcal', 0, 900, 1],
  ['carbohydrates_g', 'Carbohydrates', 'g', 0, 100, 2],
  ['sugars_g', 'Total sugar', 'g', 0, 100, 2],
  ['protein_g', 'Protein', 'g', 0, 100, 2],
  ['total_fat_g', 'Total fat', 'g', 0, 100, 2],
  ['saturated_fat_g', 'Saturated fat', 'g', 0, 100, 2],
  ['fibre_g', 'Fibre', 'g', 0, 100, 2],
  ['sodium_mg', 'Sodium', 'mg', 0, 100000, 2],
];

const INITIAL = {
  name: '',
  brand: '',
  category: '',
  dietary_tags: [],
  serving_size_g: '',
  energy_kj: '',
  calories_kcal: '',
  carbohydrates_g: '',
  sugars_g: '',
  protein_g: '',
  total_fat_g: '',
  saturated_fat_g: '',
  fibre_g: '',
  sodium_mg: '',
};

function errorText(error) {
  return error.response?.data?.message || 'Could not save product. Please try again.';
}

export default function ProductEntryPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState(INITIAL);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  function update(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
    setError('');
  }

  function toggleDietaryTag(tag) {
    setForm((current) => ({
      ...current,
      dietary_tags: current.dietary_tags.includes(tag)
        ? current.dietary_tags.filter((value) => value !== tag)
        : [...current.dietary_tags, tag],
    }));
    setError('');
  }

  function validate() {
    if (!form.name.trim()) return 'Product name is required.';
    if (!form.category) return 'Choose a food category so recommendations can compare similar products.';
    let hasNutritionValue = false;
    for (const [field, label, , min, max] of NUTRIENTS) {
      if (form[field] === '') continue;
      hasNutritionValue = true;
      const value = Number(form[field]);
      if (!Number.isFinite(value) || value < min || value > max) {
        return `${label} must be between ${min} and ${max}.`;
      }
    }
    if (!hasNutritionValue) return 'Enter at least one available nutrition value.';
    if (form.serving_size_g !== '') {
      const serving = Number(form.serving_size_g);
      if (!Number.isFinite(serving) || serving <= 0 || serving > 5000) {
        return 'Serving size must be greater than 0 and no more than 5000 g.';
      }
    }
    if (Number(form.sugars_g) > Number(form.carbohydrates_g)) {
      return 'Total sugar cannot exceed carbohydrates.';
    }
    if (Number(form.saturated_fat_g) > Number(form.total_fat_g)) {
      return 'Saturated fat cannot exceed total fat.';
    }
    return '';
  }

  async function submit(event) {
    event.preventDefault();
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setSaving(true);
    setError('');
    try {
      const payload = Object.fromEntries(
        Object.entries(form).map(([key, value]) => [
          key,
          value === ''
            ? null
            : ['name', 'brand', 'category', 'dietary_tags'].includes(key)
              ? value
              : Number(value),
        ]),
      );
      const { data } = await createProduct(payload);
      navigate(`/products/${data.product.id}`, { replace: true });
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="product-page">
      <header className="dashboard__header">
        <Link className="brand" to="/products" aria-label="Product nutrition search">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <Link className="button button--quiet" to="/products">Cancel</Link>
      </header>

      <section className="product-content product-content--form">
        <div className="product-page__intro">
          <p className="eyebrow">From the package label</p>
          <h1>Add product nutrition</h1>
          <p>Enter the nutrition facts per 100 g as printed on the product label. Leave unavailable values blank.</p>
        </div>
        <div className="data-warning" role="note">
          <strong>Not independently verified</strong>
          <span>These values will be saved as user-entered data. NutriScan does not validate them against a manufacturer or external database.</span>
        </div>

        <form className="product-entry-form" onSubmit={submit} noValidate>
          <div className="entry-fields entry-fields--identity">
            <label className="field">
              <span>Product name</span>
              <input
                maxLength="160"
                name="name"
                onChange={update}
                placeholder="e.g. Rolled oats"
                required
                value={form.name}
              />
            </label>
            <label className="field">
              <span>Brand <em>Optional</em></span>
              <input
                maxLength="120"
                name="brand"
                onChange={update}
                placeholder="Brand name"
                value={form.brand}
              />
            </label>
            <label className="field">
              <span>Food category</span>
              <select name="category" onChange={update} required value={form.category}>
                <option value="">Select a category</option>
                {CATEGORIES.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Serving size <em>Optional</em></span>
              <div className="input-with-unit">
                <input
                  max="5000"
                  min="0.01"
                  name="serving_size_g"
                  onChange={update}
                  placeholder="e.g. 40"
                  step="0.01"
                  type="number"
                  value={form.serving_size_g}
                />
                <span>g</span>
              </div>
            </label>
          </div>

          <fieldset className="product-tags-field">
            <legend>
              Dietary suitability
              <em>Optional; select only if supported by the label</em>
            </legend>
            <div className="preference-grid">
              {DIETARY_TAGS.map(([value, label]) => (
                <label className="check-option" key={value}>
                  <input
                    checked={form.dietary_tags.includes(value)}
                    onChange={() => toggleDietaryTag(value)}
                    type="checkbox"
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <h2 className="entry-section-title">Nutrition per 100 g</h2>
          <p className="entry-help">Leave a value blank if it is not shown on the label. Missing values are treated as unavailable, never as zero.</p>
          <div className="entry-fields entry-fields--nutrients">
            {NUTRIENTS.map(([name, label, unit, min, max, step]) => (
              <label className="field" key={name}>
                <span>{label} <small>({unit})</small></span>
                <input
                  max={max}
                  min={min}
                  name={name}
                  onChange={update}
                  step={step}
                  type="number"
                  value={form[name]}
                />
              </label>
            ))}
          </div>
          {error && <p className="form-message form-message--error" role="alert">{error}</p>}
          <button className="button button--primary entry-submit" disabled={saving} type="submit">
            {saving ? 'Saving product...' : 'Save nutrition details'}
          </button>
        </form>
      </section>
    </main>
  );
}
