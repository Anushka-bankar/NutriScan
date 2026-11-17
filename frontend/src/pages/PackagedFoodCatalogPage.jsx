import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  filterCatalogProducts,
  getCatalogCategories,
  getCatalogProducts,
} from '../api/catalog.js';
import {
  buildCatalogFilterParams,
  catalogErrorMessage,
  CATALOG_FILTER_RANGES,
  CATALOG_PAGE_SIZE,
  filterCatalogItems,
  formatCatalogValue,
  hasCatalogFilterCriteria,
  paginateCatalogItems,
} from '../utils/catalog.js';
import '../styles/catalog.css';

const EMPTY_FORM = {
  q: '',
  brand: '',
  category: '',
  ...Object.fromEntries(
    CATALOG_FILTER_RANGES.flatMap(({ key }) => [
      [`${key}_min`, ''],
      [`${key}_max`, ''],
    ]),
  ),
};

function responseError(error) {
  return catalogErrorMessage(error, 'Could not load catalog products. Please try again.');
}

async function getAllFilteredProducts(filters) {
  const firstResponse = await filterCatalogProducts({
    ...filters,
    page: 1,
    per_page: 100,
  });
  const firstPage = firstResponse.data;
  const remainingPages = Array.from(
    { length: Math.max(0, firstPage.pagination.pages - 1) },
    (_, index) => index + 2,
  );
  const responses = await Promise.all(
    remainingPages.map((page) =>
      filterCatalogProducts({ ...filters, page, per_page: 100 }),
    ),
  );
  return [
    ...firstPage.products,
    ...responses.flatMap(({ data }) => data.products),
  ];
}

export default function PackagedFoodCatalogPage() {
  const navigate = useNavigate();
  const [draft, setDraft] = useState(EMPTY_FORM);
  const [applied, setApplied] = useState(EMPTY_FORM);
  const [page, setPage] = useState(1);
  const [serverResults, setServerResults] = useState(null);
  const [combinedResults, setCombinedResults] = useState(null);
  const [categories, setCategories] = useState([]);
  const [categoryError, setCategoryError] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selection, setSelection] = useState([]);
  const [selectionError, setSelectionError] = useState('');

  const filterParams = useMemo(() => buildCatalogFilterParams(applied), [applied]);
  const searchParams = useMemo(
    () => Object.fromEntries(
      [['q', applied.q.trim()], ['brand', applied.brand.trim()]]
        .filter(([, value]) => value),
    ),
    [applied.q, applied.brand],
  );
  const hasFilters = hasCatalogFilterCriteria(filterParams);
  const hasSearch = Boolean(searchParams.q || searchParams.brand);
  const combinedSearch = hasFilters && hasSearch;
  const combinedKey = `${JSON.stringify(filterParams)}:${JSON.stringify(searchParams)}`;

  useEffect(() => {
    let active = true;
    getCatalogCategories()
      .then(({ data }) => {
        if (active) setCategories(data.categories);
      })
      .catch((requestError) => {
        if (active) {
          setCategoryError(
            catalogErrorMessage(
              requestError,
              'Product categories could not be loaded.',
            ),
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!combinedSearch) {
      setCombinedResults(null);
      return undefined;
    }

    let active = true;
    setCombinedResults(null);
    setLoading(true);
    setError('');
    getAllFilteredProducts(filterParams)
      .then((products) => {
        if (active) {
          setCombinedResults(filterCatalogItems(products, searchParams));
        }
      })
      .catch((requestError) => {
        if (active) setError(responseError(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [combinedSearch, combinedKey, filterParams, searchParams]);

  useEffect(() => {
    if (combinedSearch) return undefined;

    let active = true;
    setLoading(true);
    setError('');
    const request = hasFilters
      ? filterCatalogProducts({
        ...filterParams,
        page,
        per_page: CATALOG_PAGE_SIZE,
      })
      : getCatalogProducts({
        ...searchParams,
        page,
        per_page: CATALOG_PAGE_SIZE,
      });
    request
      .then(({ data }) => {
        if (active) setServerResults(data);
      })
      .catch((requestError) => {
        if (active) setError(responseError(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [combinedSearch, hasFilters, filterParams, searchParams, page]);

  const results = combinedSearch && combinedResults !== null
    ? paginateCatalogItems(combinedResults, page)
    : serverResults;

  function updateDraft(field, value) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function applyFilters(event) {
    event.preventDefault();
    setPage(1);
    setApplied({ ...draft });
    setSelectionError('');
  }

  function clearFilters() {
    setDraft(EMPTY_FORM);
    setApplied(EMPTY_FORM);
    setPage(1);
    setSelectionError('');
  }

  function toggleSelection(product) {
    setSelectionError('');
    const alreadySelected = selection.some((item) => item.id === product.id);
    if (alreadySelected) {
      setSelection(selection.filter((item) => item.id !== product.id));
    } else if (selection.length >= 2) {
      setSelectionError('Select no more than two products to compare.');
    } else {
      setSelection([...selection, product]);
    }
  }

  function compareSelected() {
    if (selection.length !== 2) return;
    const query = new URLSearchParams({
      product_id_1: String(selection[0].id),
      product_id_2: String(selection[1].id),
    });
    navigate(`/catalog/compare?${query.toString()}`);
  }

  return (
    <main className="product-page catalog-page">
      <header className="dashboard__header">
        <Link className="brand" to="/" aria-label="NutriScan dashboard">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <Link className="button button--quiet" to="/">Dashboard</Link>
      </header>

      <section className="product-content catalog-content">
        <Link className="product-back-link" to="/">
          <span aria-hidden="true">←</span> Back to dashboard
        </Link>
        <div className="product-page__intro">
          <p className="eyebrow">Packaged food dataset</p>
          <h1>Explore packaged foods</h1>
          <p>
            Search and compare products in the NutriScan catalog. Values reflect the
            dataset and are not independently verified.
          </p>
        </div>

        <form className="catalog-filters" onSubmit={applyFilters}>
          <div className="catalog-filter-grid">
            <label className="catalog-field">
              <span>Product name</span>
              <input
                autoComplete="off"
                maxLength={100}
                onChange={(event) => updateDraft('q', event.target.value)}
                placeholder="Search product names"
                value={draft.q}
              />
            </label>
            <label className="catalog-field">
              <span>Brand</span>
              <input
                autoComplete="off"
                maxLength={150}
                onChange={(event) => updateDraft('brand', event.target.value)}
                placeholder="Search brands"
                value={draft.brand}
              />
            </label>
            <label className="catalog-field">
              <span>Category</span>
              <select
                onChange={(event) => updateDraft('category', event.target.value)}
                value={draft.category}
              >
                <option value="">All categories</option>
                {categories.map((category) => (
                  <option key={category.name} value={category.name}>{category.name}</option>
                ))}
              </select>
            </label>
          </div>

          <fieldset className="catalog-range-filters">
            <legend>Nutrition ranges per serving</legend>
            <div className="catalog-range-grid">
              {CATALOG_FILTER_RANGES.map(({ key, label, unit }) => (
                <fieldset className="catalog-range" key={key}>
                  <legend>{label} ({unit})</legend>
                  {['min', 'max'].map((bound) => (
                    <label className="catalog-range__field" key={bound}>
                      <span>{bound === 'min' ? 'Min' : 'Max'}</span>
                      <input
                        aria-label={`${label} ${bound === 'min' ? 'minimum' : 'maximum'}`}
                        min="0"
                        onChange={(event) => updateDraft(`${key}_${bound}`, event.target.value)}
                        step="any"
                        type="number"
                        value={draft[`${key}_${bound}`]}
                      />
                    </label>
                  ))}
                </fieldset>
              ))}
            </div>
          </fieldset>

          {categoryError && <p className="form-message form-message--error" role="alert">{categoryError}</p>}
          {error && <p className="form-message form-message--error" role="alert">{error}</p>}
          <div className="catalog-form-actions">
            <button className="button button--primary" disabled={loading} type="submit">
              {loading ? 'Loading catalog...' : 'Apply search and filters'}
            </button>
            <button className="button button--outline" onClick={clearFilters} type="button">
              Clear filters
            </button>
          </div>
        </form>

        <div className="catalog-data-note">
          Nutrition values use the dataset’s inferred serving basis. Missing values are
          shown as “Not available”; they are never treated as zero.
        </div>

        <section className="catalog-results" aria-label="Packaged food products">
          {loading && (
            <div className="product-state" role="status">Loading catalog products...</div>
          )}
          {!loading && error && (
            <div className="product-state product-state--empty">
              <h2>Catalog unavailable</h2>
              <p role="alert">{error}</p>
              <button
                className="button button--outline"
                onClick={() => setApplied({ ...applied })}
                type="button"
              >
                Try again
              </button>
            </div>
          )}
          {!loading && !error && results && results.products.length === 0 && (
            <div className="product-state product-state--empty" role="status">
              <span className="empty-mark" aria-hidden="true">⌕</span>
              <h2>No catalog products found</h2>
              <p>Try changing the product name, brand, category, or nutrition ranges.</p>
            </div>
          )}
          {!loading && !error && results?.products.length > 0 && (
            <>
              <div className="catalog-results__heading">
                <p className="results-count">
                  {results.pagination.total.toLocaleString()} catalog products
                </p>
                <p className="catalog-results__page">
                  Page {results.pagination.page} of {results.pagination.pages}
                </p>
              </div>
              <div className="catalog-product-list">
                {results.products.map((product) => {
                  const selected = selection.some((item) => item.id === product.id);
                  return (
                    <article className="catalog-product-card" key={product.id}>
                      <div className="catalog-product-card__identity">
                        <span className="product-result__mark" aria-hidden="true">N</span>
                        <div className="catalog-product-card__main">
                          <Link to={`/catalog/${product.id}`}>{product.name}</Link>
                          <span>{product.brand || 'Brand not specified'}</span>
                          <span>{product.category || 'Category not specified'}{product.subcategory ? ` · ${product.subcategory}` : ''}</span>
                        </div>
                      </div>
                      <dl className="catalog-product-card__facts">
                        <div>
                          <dt>Calories</dt>
                          <dd>{formatCatalogValue(product.nutrition_per_serving.calories_kcal, 'kcal')}</dd>
                        </div>
                        <div>
                          <dt>Serving</dt>
                          <dd>{formatCatalogValue(product.serving_size_g, 'g')}</dd>
                        </div>
                      </dl>
                      <div className="catalog-product-card__actions">
                        <Link className="button button--outline" to={`/catalog/${product.id}`}>
                          Details
                        </Link>
                        <label className="catalog-compare-select">
                          <input
                            checked={selected}
                            onChange={() => toggleSelection(product)}
                            type="checkbox"
                          />
                          <span>Select to compare</span>
                        </label>
                      </div>
                    </article>
                  );
                })}
              </div>
              <nav className="catalog-pagination" aria-label="Catalog product pages">
                <button
                  className="button button--outline"
                  disabled={loading || results.pagination.page <= 1}
                  onClick={() => setPage((current) => current - 1)}
                  type="button"
                >
                  Previous
                </button>
                <span>Page {results.pagination.page} of {results.pagination.pages}</span>
                <button
                  className="button button--outline"
                  disabled={loading || results.pagination.page >= results.pagination.pages}
                  onClick={() => setPage((current) => current + 1)}
                  type="button"
                >
                  Next
                </button>
              </nav>
            </>
          )}
        </section>

        <aside className="catalog-compare-bar" aria-live="polite">
          <div>
            <strong>{selection.length} of 2 products selected</strong>
            {selection.length > 0 && (
              <span>{selection.map((item) => item.name).join(' · ')}</span>
            )}
          </div>
          {selectionError && <p className="form-message form-message--error" role="alert">{selectionError}</p>}
          <button
            className="button button--primary"
            disabled={selection.length !== 2}
            onClick={compareSelected}
            type="button"
          >
            Compare selected
          </button>
        </aside>
      </section>
    </main>
  );
}
