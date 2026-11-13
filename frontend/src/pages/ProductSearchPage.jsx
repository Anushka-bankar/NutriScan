import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { searchProducts } from '../api/products.js';

function errorText(error) {
  return error.response?.data?.message || 'Product search failed. Please try again.';
}

export default function ProductSearchPage() {
  const [params, setParams] = useSearchParams();
  const query = params.get('q') || '';
  const [input, setInput] = useState(query);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    setInput(query);
    if (!query) {
      setProducts([]);
      setSearched(false);
      setError('');
      return undefined;
    }

    let active = true;
    setLoading(true);
    setError('');
    setSearched(true);
    searchProducts(query)
      .then(({ data }) => {
        if (active) setProducts(data.products);
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
  }, [query]);

  function submit(event) {
    event.preventDefault();
    const term = input.trim();
    if (term.length < 2) {
      setError('Enter at least 2 characters to search.');
      return;
    }
    if (term.length > 100) {
      setError('Search must be 100 characters or fewer.');
      return;
    }
    setError('');
    setParams({ q: term });
  }

  return (
    <main className="product-page">
      <header className="dashboard__header">
        <Link className="brand" to="/" aria-label="NutriScan dashboard">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <Link className="button button--primary" to="/products/new">Scan a product</Link>
      </header>

      <section className="product-content">
        <div className="product-page__intro">
          <p className="eyebrow">Make informed choices</p>
          <h1>Product nutrition</h1>
          <p>Scan a barcode or package label to capture product ingredients and nutrition automatically.</p>
        </div>

        <form className="product-search" onSubmit={submit}>
          <label className="sr-only" htmlFor="product-search-input">Search products by name</label>
          <span className="product-search__icon" aria-hidden="true">⌕</span>
          <input
            id="product-search-input"
            maxLength="100"
            onChange={(event) => {
              setInput(event.target.value);
              setError('');
            }}
            placeholder="Search a product name..."
            value={input}
          />
          <button className="button button--primary" disabled={loading} type="submit">
            {loading ? 'Searching...' : 'Search'}
          </button>
        </form>

        <p className="data-note">
          Barcode data comes from a community-maintained database. Label scans use on-device OCR.
          Review source details and confirm package values before relying on them.
        </p>

        {error && <p className="form-message form-message--error" role="alert">{error}</p>}
        {loading && <div className="product-state">Searching your products...</div>}
        {!loading && searched && !error && products.length === 0 && (
          <div className="product-state product-state--empty">
            <span className="empty-mark" aria-hidden="true">⌕</span>
            <h2>No saved products found</h2>
            <p>Try another search or scan a barcode or nutrition label to add the product.</p>
            <Link className="text-link" to="/products/new">Scan a product</Link>
            <Link className="text-link" to="/products/manual">Enter details manually</Link>
          </div>
        )}
        {!loading && !searched && (
          <div className="product-state product-state--empty">
            <span className="empty-mark" aria-hidden="true">＋</span>
            <h2>Start your product library</h2>
            <p>Scan a barcode or take a clear photo of the nutrition and ingredients panels.</p>
            <Link className="text-link" to="/products/new">Scan your first product</Link>
            <Link className="text-link" to="/products/manual">Enter details manually</Link>
          </div>
        )}
        {!loading && products.length > 0 && (
          <div className="product-results" aria-live="polite">
            <p className="results-count">{products.length} saved {products.length === 1 ? 'product' : 'products'}</p>
            {products.map((product) => (
              <Link className="product-result" key={product.id} to={`/products/${product.id}`}>
                <span className="product-result__mark" aria-hidden="true">N</span>
                <span className="product-result__main">
                  <strong>{product.name}</strong>
                  <span>{product.brand || 'Brand not specified'}</span>
                </span>
                <span className="product-result__facts">
                  {product.nutrition_per_100g.calories_kcal == null
                    ? 'Calories unavailable'
                    : `${product.nutrition_per_100g.calories_kcal} kcal`}
                  <small>per 100 g</small>
                </span>
                <span className="source-badge">{product.source_label}</span>
                <span className="product-result__arrow" aria-hidden="true">›</span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
