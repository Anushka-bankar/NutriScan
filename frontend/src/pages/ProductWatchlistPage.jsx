import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getWatchlist, removeWatchlistEntry } from '../api/products.js';

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

function dateLabel(value) {
  return new Date(value).toLocaleDateString(undefined, { dateStyle: 'medium' });
}

export default function ProductWatchlistPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState([]);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [order, setOrder] = useState('newest');
  const [loading, setLoading] = useState(true);
  const [removingId, setRemovingId] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    getWatchlist({ q: query.trim(), category, order, limit: 100 })
      .then(({ data }) => {
        if (active) {
          setItems(data.watchlist);
          setSelected((current) =>
            current.filter((entryId) => data.watchlist.some((item) => item.id === entryId)),
          );
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.response?.data?.message || 'Could not load your watchlist.');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [query, category, order]);

  const comparableSelected = useMemo(
    () => items.filter((item) => selected.includes(item.id) && item.product_available),
    [items, selected],
  );

  function toggle(entry) {
    if (!entry.product_available) return;
    setSelected((current) => current.includes(entry.id)
      ? current.filter((id) => id !== entry.id)
      : current.length < 4
        ? [...current, entry.id]
        : current);
  }

  async function remove(entry) {
    setRemovingId(entry.id);
    setError('');
    try {
      await removeWatchlistEntry(entry.id);
      setItems((current) => current.filter((item) => item.id !== entry.id));
      setSelected((current) => current.filter((id) => id !== entry.id));
    } catch (requestError) {
      setError(requestError.response?.data?.message || 'Could not remove this product.');
    } finally {
      setRemovingId(null);
    }
  }

  function compare() {
    const ids = comparableSelected.map((item) => item.product_id);
    if (ids.length >= 2 && ids.length <= 4) {
      navigate(`/products/compare?ids=${ids.join(',')}`);
    }
  }

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
          <p className="eyebrow">Saved for later</p>
          <h1>Your watchlist</h1>
          <p>Keep useful products close, review their nutrition, or compare saved products.</p>
        </div>
        <div className="activity-filters">
          <label className="field">
            <span>Search watchlist</span>
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
              {CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Sort by</span>
            <select onChange={(event) => setOrder(event.target.value)} value={order}>
              <option value="newest">Recently saved</option>
              <option value="oldest">Oldest saved</option>
            </select>
          </label>
        </div>
        <div className="watchlist-toolbar">
          <p>{selected.length} selected · select 2–4 available products to compare</p>
          <button
            className="button button--primary"
            disabled={comparableSelected.length < 2}
            onClick={compare}
            type="button"
          >
            Compare selected
          </button>
        </div>
        <p className="data-note">
          Nutrition values are user-entered and not independently verified. Deleted products
          remain as saved snapshots and can be removed from this list.
        </p>
        {error && <p className="form-message form-message--error" role="alert">{error}</p>}
        {loading && <div className="product-state">Loading your watchlist...</div>}
        {!loading && !error && items.length === 0 && (
          <div className="product-state product-state--empty">
            <span className="empty-mark" aria-hidden="true">♡</span>
            <h2>Your watchlist is empty</h2>
            <p>Save a product from its detail page to find it here.</p>
            <Link className="text-link" to="/products">Explore products</Link>
          </div>
        )}
        {!loading && !error && items.length > 0 && (
          <div className="activity-list">
            {items.map((entry) => {
              const product = entry.product;
              const selectedEntry = selected.includes(entry.id);
              const kcal = product.nutrition_per_100g?.calories_kcal;
              return (
                <article className="activity-card" key={entry.id}>
                  <div className="activity-card__top">
                    <label className={`watchlist-select${entry.product_available ? '' : ' watchlist-select--disabled'}`}>
                      <input
                        checked={selectedEntry}
                        disabled={!entry.product_available}
                        onChange={() => toggle(entry)}
                        type="checkbox"
                      />
                      <span className="sr-only">Select {product.name} to compare</span>
                    </label>
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
                    <span>{product.nutrition_per_100g?.fibre_g == null ? 'Fibre unavailable' : `${product.nutrition_per_100g.fibre_g} g`}<small>per 100 g</small></span>
                  </div>
                  <div className="activity-card__footer">
                    <span>Saved {dateLabel(entry.added_at)}</span>
                    <div className="activity-actions">
                      {entry.product_available
                        ? <Link className="text-link" to={`/products/${entry.product_id}`}>Open details</Link>
                        : <span className="removed-product-note">Product deleted · snapshot retained</span>}
                      <button
                        className="text-button"
                        disabled={removingId === entry.id}
                        onClick={() => remove(entry)}
                        type="button"
                      >
                        {removingId === entry.id ? 'Removing...' : 'Remove'}
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}
