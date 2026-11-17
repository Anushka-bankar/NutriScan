import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  compareIngredientAnalyses,
  getIngredientAnalysisHistory,
} from '../api/products.js';

function formatDate(value) {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function errorText(error) {
  return error.response?.data?.message || 'Could not load ingredient analysis history.';
}

function ChangeList({ title, items, renderItem }) {
  return (
    <section className="ingredient-diff-section">
      <h2>{title} <span>{items.length}</span></h2>
      {items.length > 0
        ? <ul className="ingredient-diff-list">{items.map(renderItem)}</ul>
        : <p className="ingredient-diff-empty">No changes in this section.</p>}
    </section>
  );
}

function FieldChanges({ changes }) {
  return (
    <ul className="ingredient-field-changes">
      {changes.map((change) => (
        <li key={change.field}>
          <strong>{change.field.replaceAll('_', ' ')}</strong>
          <span>{change.older || 'Unavailable'}</span>
          <span aria-hidden="true">→</span>
          <span>{change.newer || 'Unavailable'}</span>
        </li>
      ))}
    </ul>
  );
}

export default function IngredientHistoryComparisonPage() {
  const [searchParams] = useSearchParams();
  const [history, setHistory] = useState([]);
  const [productIdentity, setProductIdentity] = useState('');
  const [olderId, setOlderId] = useState('');
  const [newerId, setNewerId] = useState('');
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState('');

  const groups = useMemo(() => {
    const grouped = new Map();
    for (const entry of history) {
      if (entry.product_identity_snapshot == null) continue;
      const key = String(entry.product_identity_snapshot);
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(entry);
    }
    return [...grouped.entries()]
      .map(([identity, entries]) => ({ identity, entries }))
      .sort((a, b) => new Date(b.entries[0].analyzed_at) - new Date(a.entries[0].analyzed_at));
  }, [history]);

  const selectedGroup = groups.find((group) => group.identity === productIdentity);
  const selectedEntries = selectedGroup?.entries || [];
  const legacyEntries = history.filter(
    (entry) => entry.product_identity_snapshot == null,
  );

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    getIngredientAnalysisHistory()
      .then(({ data }) => {
        if (!active) return;
        const entries = data.history || [];
        setHistory(entries);
        const grouped = new Map();
        entries.forEach((entry) => {
          if (entry.product_identity_snapshot == null) return;
          const key = String(entry.product_identity_snapshot);
          if (!grouped.has(key)) grouped.set(key, []);
          grouped.get(key).push(entry);
        });
        const requestedIdentity = searchParams.get('productId');
        const initialGroup = grouped.has(requestedIdentity)
          ? requestedIdentity
          : [...grouped.entries()].find(([, values]) => values.length > 1)?.[0]
            || [...grouped.keys()][0]
            || '';
        setProductIdentity(initialGroup);
        const initialEntries = grouped.get(initialGroup) || [];
        setOlderId(initialEntries.length > 1 ? String(initialEntries[1].id) : '');
        setNewerId(initialEntries.length > 1 ? String(initialEntries[0].id) : '');
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
  }, [searchParams]);

  function chooseProduct(identity) {
    setProductIdentity(identity);
    setComparison(null);
    setError('');
    const entries = groups.find((group) => group.identity === identity)?.entries || [];
    setOlderId(entries.length > 1 ? String(entries[1].id) : '');
    setNewerId(entries.length > 1 ? String(entries[0].id) : '');
  }

  async function submitComparison(event) {
    event.preventDefault();
    if (!olderId || !newerId || olderId === newerId) {
      setError('Choose two different historical analyses to compare.');
      return;
    }
    setComparing(true);
    setComparison(null);
    setError('');
    try {
      const { data } = await compareIngredientAnalyses(Number(olderId), Number(newerId));
      setComparison(data);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setComparing(false);
    }
  }

  if (loading) {
    return <main className="app-loading">Loading ingredient history...</main>;
  }

  return (
    <main className="product-page">
      <header className="dashboard__header">
        <Link className="brand" to="/products" aria-label="Product nutrition search">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <Link className="button button--quiet" to="/history">Product history</Link>
        {selectedGroup?.entries.find((entry) => entry.product_available) && (
          <Link
            className="button button--outline"
            to={`/products/${selectedGroup.entries.find((entry) => entry.product_available).product_id}/ingredients`}
          >
            Back to ingredient analysis
          </Link>
        )}
      </header>
      <section className="product-content product-content--detail ingredient-comparison-page">
        <div className="product-page__intro">
          <p className="eyebrow">Saved analysis snapshots</p>
          <h1>Ingredient history comparison</h1>
          <p>Compare saved analyses of the same product. Historical results are compared as stored and are never recalculated.</p>
        </div>

        <div className="data-warning ingredient-method-note" role="note">
          <strong>Historical, user-provided information</strong>
          <span>Ingredient lists and explanations reflect what was saved at each analysis time. They are not independently verified; formatting-only name differences are normalized for matching.</span>
        </div>

        {history.length === 0 && !error && (
          <div className="product-state product-state--empty">
            <h2>No saved ingredient analyses</h2>
            <p>Analyze a product's ingredient list to create a timestamped snapshot that can be compared later.</p>
            <Link className="text-link" to="/products">Find a product</Link>
          </div>
        )}
        {history.length > 0 && groups.length === 0 && (
          <div className="product-state product-state--empty">
            <h2>These older snapshots cannot be grouped safely</h2>
            <p>They were saved before product identity snapshots were available, and their products have since been deleted. NutriScan will not guess which records belong together.</p>
          </div>
        )}
        {history.length > 0 && groups.length > 0 && (
          <form className="ingredient-comparison-form" onSubmit={submitComparison}>
            <label className="field">
              <span>Product</span>
              <select onChange={(event) => chooseProduct(event.target.value)} value={productIdentity}>
                {groups.map((group) => (
                  <option key={group.identity} value={group.identity}>
                    {group.entries[0].product_name}
                    {!group.entries[0].product_available ? ' · deleted product' : ''}
                    {` · ${group.entries.length} analyses`}
                  </option>
                ))}
              </select>
            </label>
            {selectedEntries.length < 2
              ? <div className="product-state product-state--empty">
                <h2>Not enough history to compare</h2>
                <p>This product has {selectedEntries.length} saved analysis. Save another analysis of the same product to compare versions.</p>
              </div>
              : (
                <>
                  <div className="ingredient-comparison-selectors">
                    <label className="field">
                      <span>Older analysis</span>
                      <select
                        onChange={(event) => {
                          setOlderId(event.target.value);
                          setComparison(null);
                          setError('');
                        }}
                        value={olderId}
                      >
                        {selectedEntries.map((entry) => (
                          <option key={entry.id} value={entry.id}>
                            {formatDate(entry.analyzed_at)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span>Newer analysis</span>
                      <select
                        onChange={(event) => {
                          setNewerId(event.target.value);
                          setComparison(null);
                          setError('');
                        }}
                        value={newerId}
                      >
                        {selectedEntries.map((entry) => (
                          <option key={entry.id} value={entry.id}>
                            {formatDate(entry.analyzed_at)}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <button className="button button--primary" disabled={comparing} type="submit">
                    {comparing ? 'Comparing saved analyses...' : 'Compare analyses'}
                  </button>
                </>
              )}
          </form>
        )}
        {legacyEntries.length > 0 && (
          <section className="ingredient-diff-section ingredient-legacy-history">
            <h2>Older snapshots that cannot be grouped safely <span>{legacyEntries.length}</span></h2>
            <p className="ingredient-diff-empty">
              These analyses were saved before product identity snapshots were available, and
              the products have since been deleted. They are preserved but cannot be compared
              without guessing.
            </p>
            <ul className="ingredient-diff-list">
              {legacyEntries.map((entry) => (
                <li key={entry.id}>
                  <strong>{entry.product_name} · {formatDate(entry.analyzed_at)}</strong>
                  <span>{entry.ingredients_text}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {error && <p className="form-message form-message--error" role="alert">{error}</p>}

        {comparison && (
          <section className="ingredient-comparison-results" aria-live="polite">
            <div className="ingredient-comparison-dates">
              <article>
                <p className="eyebrow">Older analysis</p>
                <h2>{comparison.older.product_name}</h2>
                <time dateTime={comparison.older.analyzed_at}>{formatDate(comparison.older.analyzed_at)}</time>
              </article>
              <article>
                <p className="eyebrow">Newer analysis</p>
                <h2>{comparison.newer.product_name}</h2>
                <time dateTime={comparison.newer.analyzed_at}>{formatDate(comparison.newer.analyzed_at)}</time>
              </article>
            </div>
            <div className="ingredient-comparison-grid">
              <ChangeList
                title="Added ingredients"
                items={comparison.added}
                renderItem={(item) => <li key={`${item.position}-${item.name}`}><strong>{item.name}</strong><span>Position {item.position}</span></li>}
              />
              <ChangeList
                title="Removed ingredients"
                items={comparison.removed}
                renderItem={(item) => <li key={`${item.position}-${item.name}`}><strong>{item.name}</strong><span>Was at position {item.position}</span></li>}
              />
              <ChangeList
                title="Ingredient order changes"
                items={comparison.order_changes}
                renderItem={(item) => <li key={`${item.older_position}-${item.name}`}><strong>{item.name}</strong><span>Position {item.older_position} → {item.newer_position}</span></li>}
              />
              <ChangeList
                title="Unchanged ingredients"
                items={comparison.unchanged}
                renderItem={(item) => (
                  <li key={`${item.older_position}-${item.newer_position}-${item.name}`}>
                    <strong>{item.name}</strong>
                    <span>
                      {item.older_position === item.newer_position
                        ? `Position ${item.newer_position}`
                        : `Position ${item.older_position} → ${item.newer_position}`}
                    </span>
                    {item.older_name !== item.name && (
                      <span>
                        Label spelling/formatting matched: {item.older_name} → {item.name}
                      </span>
                    )}
                  </li>
                )}
              />
            </div>
            <ChangeList
              title="Classification changes"
              items={comparison.classification_changes}
              renderItem={(item) => (
                <li className="ingredient-change-detail" key={`${item.older_position}-${item.name}`}>
                  <strong>{item.name}</strong>
                  <FieldChanges changes={item.changes} />
                </li>
              )}
            />
            <ChangeList
              title="Explanation and evidence changes"
              items={comparison.explanation_changes}
              renderItem={(item) => (
                <li className="ingredient-change-detail" key={`${item.older_position}-${item.name}`}>
                  <strong>{item.name}</strong>
                  <FieldChanges changes={item.changes} />
                </li>
              )}
            />
            <details className="ingredient-comparison-source">
              <summary>Show saved ingredient text</summary>
              <div><h3>Older snapshot</h3><p>{comparison.older.ingredients_text}</p></div>
              <div><h3>Newer snapshot</h3><p>{comparison.newer.ingredients_text}</p></div>
            </details>
          </section>
        )}
      </section>
    </main>
  );
}
