import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import {
  addToWatchlist,
  classifyProduct,
  getProduct,
  getWatchlistStatus,
  recordProductAnalysis,
  removeWatchlistEntry,
} from '../api/products.js';

const NUTRIENTS = [
  ['calories_kcal', 'Calories', 'kcal'],
  ['energy_kj', 'Energy', 'kJ'],
  ['carbohydrates_g', 'Carbohydrates', 'g'],
  ['sugars_g', 'Total sugar', 'g'],
  ['protein_g', 'Protein', 'g'],
  ['total_fat_g', 'Total fat', 'g'],
  ['saturated_fat_g', 'Saturated fat', 'g'],
  ['fibre_g', 'Fibre', 'g'],
  ['sodium_mg', 'Sodium', 'mg'],
];

const MACRO_COLORS = ['#648b72', '#9cb7a1', '#c4d2c5'];
const GRAM_NUTRIENTS = new Set([
  'carbohydrates_g',
  'sugars_g',
  'protein_g',
  'total_fat_g',
  'saturated_fat_g',
  'fibre_g',
]);
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

function errorText(error) {
  return error.response?.status === 404
    ? 'This product could not be found in your saved products.'
    : error.response?.data?.message || 'Could not load product details. Please try again.';
}

function MacroChart({ nutrition }) {
  const macros = useMemo(() => {
    const required = [
      nutrition.carbohydrates_g,
      nutrition.protein_g,
      nutrition.total_fat_g,
    ];
    if (required.some((value) => value == null)) return null;
    const values = [
      nutrition.carbohydrates_g == null ? null : { name: 'Carbohydrates', value: nutrition.carbohydrates_g * 4 },
      nutrition.protein_g == null ? null : { name: 'Protein', value: nutrition.protein_g * 4 },
      nutrition.total_fat_g == null ? null : { name: 'Fat', value: nutrition.total_fat_g * 9 },
    ].filter(Boolean);
    const total = values.reduce((sum, item) => sum + item.value, 0);
    return { values: values.filter((item) => item.value > 0), total };
  }, [nutrition]);

  if (!macros || !macros.total) {
    return (
      <p className="chart-empty">
        Macro breakdown is unavailable because one or more macro values are missing.
      </p>
    );
  }

  return (
    <div className="macro-chart">
      <div className="macro-chart__visual">
        <ResponsiveContainer width="100%" height={190}>
          <PieChart>
            <Pie
              data={macros.values}
              dataKey="value"
              cx="50%"
              cy="50%"
              innerRadius={53}
              outerRadius={76}
              paddingAngle={3}
              stroke="none"
            >
              {macros.values.map((entry, index) => (
                <Cell fill={MACRO_COLORS[index]} key={entry.name} />
              ))}
            </Pie>
            <Tooltip formatter={(value, name) => [`${Number(value).toFixed(0)} kcal`, name]} />
          </PieChart>
        </ResponsiveContainer>
        <div className="macro-chart__center" aria-hidden="true">
          <strong>{Math.round(macros.total)}</strong>
          <span>macro kcal</span>
        </div>
      </div>
      <div className="macro-legend">
        {macros.values.map((item, index) => (
          <div className="macro-legend__row" key={item.name}>
            <span className="macro-legend__dot" style={{ backgroundColor: MACRO_COLORS[index] }} />
            <span>{item.name}</span>
            <strong>{Math.round((item.value / macros.total) * 100)}%</strong>
          </div>
        ))}
      </div>
      <p className="result-note">
        Estimated macro energy uses 4 kcal/g for carbohydrates and protein, and 9 kcal/g for fat.
        This is a calculation, not a nutrition score; fibre is not counted separately.
      </p>
    </div>
  );
}

export default function ProductDetailPage() {
  const { productId } = useParams();
  const recordedProductIds = useRef(new Set());
  const [product, setProduct] = useState(null);
  const [serving, setServing] = useState(false);
  const [customAmount, setCustomAmount] = useState('');
  const [customActive, setCustomActive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [classification, setClassification] = useState({ category: '', dietary_tags: [] });
  const [savingClassification, setSavingClassification] = useState(false);
  const [classificationMessage, setClassificationMessage] = useState('');
  const [classificationError, setClassificationError] = useState('');
  const [watchlistEntryId, setWatchlistEntryId] = useState(null);
  const [watchlistBusy, setWatchlistBusy] = useState(false);
  const [watchlistMessage, setWatchlistMessage] = useState('');
  const [watchlistError, setWatchlistError] = useState('');
  const [historyError, setHistoryError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    getProduct(productId)
      .then(({ data }) => {
        if (active) {
          setProduct(data.product);
          setServing(false);
          setCustomActive(false);
          setCustomAmount('');
          setClassification({
            category: data.product.category || '',
            dietary_tags: data.product.dietary_tags || [],
          });
          getWatchlistStatus(data.product.id)
            .then(({ data: status }) => {
              if (active) setWatchlistEntryId(status.entry_id);
            })
            .catch((requestError) => {
              if (active) {
                setWatchlistError(
                  requestError.response?.data?.message || 'Could not load watchlist status.',
                );
              }
            });
          if (!recordedProductIds.current.has(data.product.id)) {
            recordedProductIds.current.add(data.product.id);
            recordProductAnalysis(data.product.id).catch((requestError) => {
              if (active) {
                setHistoryError(
                  requestError.response?.data?.message || 'This view could not be added to history.',
                );
              }
            });
          }
        }
      })
      .catch((requestError) => {
        if (active) setError(errorText(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [productId]);

  async function toggleWatchlist() {
    if (!product) return;
    setWatchlistBusy(true);
    setWatchlistError('');
    setWatchlistMessage('');
    try {
      if (watchlistEntryId) {
        await removeWatchlistEntry(watchlistEntryId);
        setWatchlistEntryId(null);
        setWatchlistMessage('Removed from your watchlist.');
      } else {
        const { data } = await addToWatchlist(product.id);
        setWatchlistEntryId(data.watchlist_entry.id);
        setWatchlistMessage('Saved to your watchlist.');
      }
    } catch (requestError) {
      setWatchlistError(
        requestError.response?.data?.message || 'Could not update your watchlist.',
      );
    } finally {
      setWatchlistBusy(false);
    }
  }

  function toggleTag(tag) {
    setClassification((current) => ({
      ...current,
      dietary_tags: current.dietary_tags.includes(tag)
        ? current.dietary_tags.filter((value) => value !== tag)
        : [...current.dietary_tags, tag],
    }));
    setClassificationMessage('');
  }

  async function saveClassification(event) {
    event.preventDefault();
    if (!classification.category) {
      setClassificationError('Choose a product category first.');
      return;
    }
    setSavingClassification(true);
    setClassificationError('');
    setClassificationMessage('');
    try {
      const { data } = await classifyProduct(product.id, classification);
      setProduct(data.product);
      setClassificationMessage('Category and suitability tags saved.');
    } catch (requestError) {
      setClassificationError(
        requestError.response?.data?.message || 'Could not save product classification.',
      );
    } finally {
      setSavingClassification(false);
    }
  }

  if (loading) {
    return <main className="app-loading">Loading product nutrition...</main>;
  }

  return (
    <main className="product-page">
      <header className="dashboard__header">
        <Link className="brand" to="/products" aria-label="Product nutrition search">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <Link className="button button--quiet" to="/products">Back to products</Link>
      </header>
      <section className="product-content product-content--detail">
        {error && (
          <div className="product-state product-state--empty">
            <h1>Product unavailable</h1>
            <p role="alert">{error}</p>
            <Link className="text-link" to="/products">Return to product search</Link>
          </div>
        )}
        {product && (
          <>
            <div className="product-detail-heading">
              <div>
                <p className="eyebrow">Nutrition analysis</p>
                <h1>{product.name}</h1>
                <p>{product.brand || 'Brand not specified'} · {product.category_label}</p>
              </div>
              <span className="source-badge source-badge--large">{product.source_label}</span>
            </div>
            <div className="product-activity-actions">
              <button
                className={`button ${watchlistEntryId ? 'button--saved' : 'button--outline'}`}
                disabled={watchlistBusy}
                onClick={toggleWatchlist}
                type="button"
              >
                {watchlistBusy
                  ? 'Updating...'
                  : watchlistEntryId
                    ? '♥ Saved to watchlist · Remove'
                    : '♡ Add to watchlist'}
              </button>
              <Link className="button button--outline" to="/history">View analysis history</Link>
            </div>
            {watchlistError && <p className="form-message form-message--error" role="alert">{watchlistError}</p>}
            {watchlistMessage && <p className="form-message form-message--success" role="status">{watchlistMessage}</p>}
            {historyError && <p className="form-message form-message--error" role="alert">{historyError}</p>}
            <div className="data-warning data-warning--compact">
              {product.source_type === 'open_food_facts'
                ? 'Nutrition and ingredients came from Open Food Facts, a community-maintained database. Data may be incomplete or unverified; compare it with the package.'
                : product.source_type === 'label_ocr'
                  ? 'Nutrition and ingredients were extracted from a package photo using OCR and confirmed by the user. Check the original label; extraction can be inaccurate.'
                  : 'Nutrition values are user-entered and not independently verified. Check the original package label before relying on these values.'}
              {product.source_type === 'open_food_facts' && product.barcode && (
                <> <a href={`https://world.openfoodfacts.org/product/${encodeURIComponent(product.barcode)}`} rel="noreferrer" target="_blank">View Open Food Facts source (ODbL)</a></>
              )}
            </div>

            <div className="nutrition-layout">
              <section className="nutrition-panel">
                <div className="nutrition-panel__heading">
                  <div>
                    <p className="eyebrow">Nutrition facts</p>
                    <h2>
                      {customActive
                        ? `For ${customAmount} g`
                        : serving
                          ? `Per serving (${product.serving_size_g} g)`
                          : 'Per 100 g'}
                    </h2>
                  </div>
                  {product.nutrition_per_serving && (
                    <div className="nutrition-toggle" role="group" aria-label="Nutrition amount">
                      <button
                        aria-pressed={!serving && !customActive}
                        className={!serving && !customActive ? 'is-selected' : ''}
                        onClick={() => { setServing(false); setCustomActive(false); }}
                        type="button"
                      >
                        Per 100 g
                      </button>
                      <button
                        aria-pressed={serving && !customActive}
                        className={serving && !customActive ? 'is-selected' : ''}
                        onClick={() => { setServing(true); setCustomActive(false); }}
                        type="button"
                      >
                        Per serving
                      </button>
                    </div>
                  )}
                </div>
                <form
                  className="portion-calculator"
                  onSubmit={(event) => {
                    event.preventDefault();
                    const amount = Number(customAmount);
                    if (!Number.isFinite(amount) || amount <= 0 || amount > 5000) return;
                    setServing(false);
                    setCustomActive(true);
                  }}
                >
                  <label className="field">
                    <span>Calculate for your amount</span>
                    <div className="input-with-unit">
                      <input
                        max="5000"
                        min="0.01"
                        onChange={(event) => {
                          setCustomAmount(event.target.value);
                          setCustomActive(false);
                        }}
                        placeholder={product.serving_size_g || 'e.g. 50'}
                        step="0.01"
                        type="number"
                        value={customAmount}
                      />
                      <span>g</span>
                    </div>
                  </label>
                  <button className="button button--outline" disabled={!customAmount} type="submit">Calculate</button>
                </form>
                <div className="nutrition-facts">
                  {NUTRIENTS.map(([key, label, unit], index) => {
                    const per100Amount = product.nutrition_per_100g[key];
                    const multiplier = customActive
                      ? Number(customAmount) / 100
                      : serving
                        ? Number(product.serving_size_g) / 100
                        : 1;
                    const amount = per100Amount == null
                      ? null
                      : Math.round(per100Amount * multiplier * 100) / 100;
                    const gramAmount = GRAM_NUTRIENTS.has(key)
                      ? amount
                      : null;
                    const massScale = customActive
                      ? Number(customAmount)
                      : serving
                        ? Number(product.serving_size_g)
                        : 100;
                    const massPercent = gramAmount === null
                      ? 0
                      : Math.max(0, Math.min(100, (gramAmount / massScale) * 100));
                    return (
                      <div className={`nutrition-fact${index < 2 ? ' nutrition-fact--energy' : ''}`} key={key}>
                        <div className="nutrition-fact__main">
                          <span>{label}</span>
                          <strong>
                            {amount == null
                              ? 'Unavailable'
                              : `${amount.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit}`}
                          </strong>
                        </div>
                        {gramAmount !== null && (
                          <div
                            className="nutrition-fact__track"
                            role="meter"
                            aria-label={`${label} as a share of product weight`}
                            aria-valuemin="0"
                            aria-valuemax="100"
                            aria-valuenow={Number(massPercent.toFixed(1))}
                          >
                            <span style={{ width: `${massPercent}%` }} />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
                <p className="result-note">
                  Nutrient bars show grams as a share of the product weight; they are visual
                  indicators only, not daily-value or health ratings.
                </p>
                {!product.nutrition_per_serving && (
                  <p className="result-note">Serving-size data was not entered for this product.</p>
                )}
              </section>

              <section className="nutrition-panel macro-panel">
                <p className="eyebrow">Macro breakdown</p>
                <h2>Estimated energy share</h2>
                <MacroChart nutrition={product.nutrition_per_100g} />
              </section>
            </div>
            {product.ingredients && (
              <section className="ingredients-panel">
                <p className="eyebrow">Package ingredients</p>
                <h2>Ingredients</h2>
                <p>{product.ingredients}</p>
              </section>
            )}
            <section className="classification-panel">
              <div>
                <p className="eyebrow">Help find comparable foods</p>
                <h2>Product category and suitability</h2>
                <p>
                  Categories and suitability tags are user-entered. Select them only when
                  supported by the product label; recommendations depend on this information.
                </p>
              </div>
              <form onSubmit={saveClassification}>
                <label className="field">
                  <span>Food category</span>
                  <select
                    onChange={(event) => {
                      setClassification((current) => ({ ...current, category: event.target.value }));
                      setClassificationMessage('');
                    }}
                    value={classification.category}
                  >
                    <option value="">Select a category</option>
                    {CATEGORIES.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </label>
                <fieldset className="product-tags-field">
                  <legend>Dietary suitability tags</legend>
                  <div className="preference-grid">
                    {DIETARY_TAGS.map(([value, label]) => (
                      <label className="check-option" key={value}>
                        <input
                          checked={classification.dietary_tags.includes(value)}
                          onChange={() => toggleTag(value)}
                          type="checkbox"
                        />
                        <span>{label}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
                {classificationError && (
                  <p className="form-message form-message--error" role="alert">{classificationError}</p>
                )}
                {classificationMessage && (
                  <p className="form-message form-message--success" role="status">{classificationMessage}</p>
                )}
                <button className="button button--primary classification-save" disabled={savingClassification} type="submit">
                  {savingClassification ? 'Saving...' : 'Save classification'}
                </button>
              </form>
            </section>
            <div className="recommendations-cta">
              <div>
                <h2>Looking for a better fit?</h2>
                <p>Compare this product with similar products in your saved collection.</p>
              </div>
              <Link className="button button--primary" to={`/products/${product.id}/recommendations`}>
                Find alternatives
              </Link>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
