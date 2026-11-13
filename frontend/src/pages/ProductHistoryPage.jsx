import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getProductHistory } from '../api/products.js';

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

function formatDate(value) {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function ProductSummary({ entry }) {
  const product = entry.product;
  const kcal = product.nutrition_per_100g?.calories_kcal;
  const href = entry.product_available && entry.product_id
    ? `/products/${entry.product_id}`
    : null;

  return (
    <article className="activity-card">
      <div className="activity-card__top">
        <div className="activity-card__identity">
          <span className="product-result__mark" aria-hidden="true">N</span>
          <div>
            <h2>{product.name}</h2>
            <p>{product.brand || 'Brand not specified'} · {product.category_label || 'Uncategorized'}</p>
          </div>
        </div>
        <span className="source-badge">{product.source_label || 'User-entered; not independently verified'}</span>
      </div>
      <div className="activity-card__facts">
        <span>{kcal == null ? 'Calories unavailable' : `${kcal} kcal`}<small>per 100 g</small></span>
        <span>{product.nutrition_per_100g?.protein_g == null ? 'Protein unavailable' : `${product.nutrition_per_100g.protein_g} g`}<small>per 100 g</small></span>
        <span>{product.nutrition_per_100g?.sugars_g == null ? 'Sugar unavailable' : `${product.nutrition_per_100g.sugars_g} g`}<small>per 100 g</small></span>
      </div>
      <div className="activity-card__footer">
        <span>Analyzed {formatDate(entry.analyzed_at)}</span>
        {href
          ? <Link className="text-link" to={href}>Open product details</Link>
          : <span className="removed-product-note">Product deleted · saved snapshot shown</span>}
      </div>
    </article>
  );
}

export default function ProductHistoryPage() {
  const [history, setHistory] = useState([]);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [order, setOrder] = useState('newest');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    getProductHistory({ q: query.trim(), category, order, limit: 100 })
      .then(({ data }) => {
        if (active) setHistory(data.history);
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.response?.data?.message || 'Could not load product history.');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [query, category, order]);

  return (
    <main className="product-page">
      <header className="dashboard__header">
        <Link className="brand" to="/" aria-label="NutriScan dashboard">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <Link className="button button--quiet" to="/products">Product search</Link>
      </header>
      <section className="product-content product-content--detail">
        <div className="product-page__intro">
          <p className="eyebrow">Your recent analyses</p>
          <h1>Product history</h1>
          <p>Each product detail analysis is saved here with a snapshot of its nutrition at that time.</p>
        </div>

        <div className="activity-filters">
          <label className="field">
            <span>Search history</span>
            <input
              maxLength="100"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search product names"
              value={query}
            />
          </label>
          <label className="field">
            <span>Category</span>
            <select onChange={(event) => setCategory(event.target.value)} value={category}>
              <option value="">All categories</option>
              {CATEGORIES.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Sort by</span>
            <select onChange={(event) => setOrder(event.target.value)} value={order}>
              <option value="newest">Most recent</option>
              <option value="oldest">Oldest first</option>
            </select>
          </label>
        </div>

        <p className="data-note">
          Nutrition values are user-entered and not independently verified. Past analyses retain
          their saved snapshot if a product changes or is deleted.
        </p>
        {error && <p className="form-message form-message--error" role="alert">{error}</p>}
        {loading && <div className="product-state">Loading your product history...</div>}
        {!loading && !error && history.length === 0 && (
          <div className="product-state product-state--empty">
            <span className="empty-mark" aria-hidden="true">◷</span>
            <h2>No product analyses yet</h2>
            <p>Open a saved product to analyze it and add it to your history.</p>
            <Link className="text-link" to="/products">Explore products</Link>
          </div>
        )}
        {!loading && !error && history.length > 0 && (
          <div className="activity-list">
            {history.map((entry) => <ProductSummary entry={entry} key={entry.id} />)}
          </div>
        )}
      </section>
    </main>
  );
}
