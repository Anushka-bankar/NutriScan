import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  analyzeIngredients,
  getLatestIngredientAnalysis,
  getProduct,
} from '../api/products.js';

function messageFrom(error) {
  return error.response?.data?.message || 'Could not load ingredient analysis. Please try again.';
}

function AnalysisEntry({ entry }) {
  return (
    <article className="ingredient-result-card">
      <header className="ingredient-result-card__header">
        <div>
          {entry.parent_name && <p className="ingredient-result-card__parent">Part of {entry.parent_name}</p>}
          <h3>{entry.name}</h3>
        </div>
        <span className={`ingredient-label ingredient-label--${entry.category}`}>
          {entry.category_label}
        </span>
      </header>
      <p className="ingredient-evidence">{entry.evidence_label}</p>
      <dl className="ingredient-facts">
        <div>
          <dt>What it is</dt>
          <dd>{entry.what_it_is}</dd>
        </div>
        <div>
          <dt>Common purpose</dt>
          <dd>{entry.common_purpose}</dd>
        </div>
        <div>
          <dt>Health considerations</dt>
          <dd>{entry.health_considerations}</dd>
        </div>
      </dl>
      {entry.dietary_considerations.length > 0 && (
        <div className="ingredient-considerations">
          <h4>Dietary considerations</h4>
          {entry.dietary_considerations.map((item, index) => (
            <p
              className={`ingredient-consideration ingredient-consideration--${item.status}`}
              key={`${item.preference}-${index}`}
            >
              <strong>{item.preference === 'all' ? 'Label note' : item.preference.replace('_', ' ')}</strong>
              <span>{item.message}</span>
            </p>
          ))}
        </div>
      )}
      {entry.references.length > 0 && (
        <div className="ingredient-references">
          <h4>References</h4>
          <ul>
            {entry.references.map((reference) => (
              <li key={reference.url}>
                <a href={reference.url} rel="noreferrer" target="_blank">{reference.title}</a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

function AnalysisResults({ analysis }) {
  const { summary } = analysis;
  return (
    <section className="ingredient-analysis-results" aria-live="polite">
      <div className="ingredient-analysis-results__heading">
        <div>
          <p className="eyebrow">Saved analysis</p>
          <h2>Ingredient-by-ingredient review</h2>
        </div>
        <time dateTime={analysis.analyzed_at}>
          {new Date(analysis.analyzed_at).toLocaleString()}
        </time>
      </div>
      <div className="ingredient-summary-grid">
        <div><strong>{summary.ingredient_count}</strong><span>ingredients reviewed</span></div>
        <div><strong>{summary.unmatched_count}</strong><span>not in the reference set</span></div>
        <div><strong>{summary.dietary_conflict_count}</strong><span>preference conflicts</span></div>
      </div>
      <p className="ingredient-goal-context">{summary.health_goal_context}</p>
      {summary.dietary_preferences.length === 0 && (
        <p className="result-note">No dietary preferences are saved in your health profile; only general ingredient matches are shown.</p>
      )}
      <p className="result-note">
        Method: {analysis.method}. This is reference matching, not a generative AI diagnosis or a safety certification.
      </p>
      <div className="ingredient-results-list">
        {analysis.entries.map((entry, index) => (
          <AnalysisEntry entry={entry} key={`${entry.name}-${index}`} />
        ))}
      </div>
      <p className="data-warning ingredient-disclaimer">{analysis.disclaimer}</p>
    </section>
  );
}

export default function IngredientAnalysisPage() {
  const { productId } = useParams();
  const [product, setProduct] = useState(null);
  const [ingredients, setIngredients] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    Promise.all([
      getProduct(productId),
      getLatestIngredientAnalysis(productId),
    ])
      .then(([productResponse, analysisResponse]) => {
        if (!active) return;
        const latest = analysisResponse.data.analysis;
        setProduct(productResponse.data.product);
        setAnalysis(latest);
        setIngredients(
          latest?.ingredients_text
          ?? analysisResponse.data.ingredients_text
          ?? productResponse.data.product.ingredients
          ?? '',
        );
      })
      .catch((requestError) => {
        if (active) setError(messageFrom(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [productId]);

  async function submitAnalysis(event) {
    event.preventDefault();
    if (!ingredients.trim()) {
      setError('Enter the ingredient list from the package before analyzing it.');
      return;
    }
    if (ingredients.length > 10000) {
      setError('Ingredient list must be at most 10000 characters.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const { data } = await analyzeIngredients(productId, ingredients);
      setAnalysis(data.analysis);
      setIngredients(data.analysis.ingredients_text);
    } catch (requestError) {
      setError(messageFrom(requestError));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <main className="app-loading">Loading ingredient analysis...</main>;
  }

  return (
    <main className="product-page">
      <header className="dashboard__header">
        <Link className="brand" to="/products" aria-label="Product nutrition search">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <Link
          className="button button--outline"
          to={`/ingredient-history?productId=${productId}`}
        >
          Compare saved analyses
        </Link>
        <Link className="button button--quiet" to={product ? `/products/${product.id}` : '/products'}>
          Back to product
        </Link>
      </header>
      <section className="product-content ingredient-page">
        {error && !product && (
          <div className="product-state product-state--empty">
            <h1>Ingredient analysis unavailable</h1>
            <p role="alert">{error}</p>
            <Link className="text-link" to="/products">Return to product search</Link>
          </div>
        )}
        {product && (
          <>
            <div className="product-page__intro">
              <p className="eyebrow">Ingredient analysis</p>
              <h1>{product.name}</h1>
              <p>Review known ingredient roles, cited food-allergen notes, and potential conflicts with your saved dietary preferences.</p>
            </div>
            <div className="data-warning ingredient-method-note" role="note">
              <strong>Evidence-limited NLP matching</strong>
              <span>
                Ingredient names are matched locally to a small reviewed reference set. The system does not generate facts for unmatched terms; this is not medical advice or a substitute for the package label.
              </span>
            </div>
            <form className="ingredient-input-panel" onSubmit={submitAnalysis} noValidate>
              <label className="field">
                <span>Ingredients from the package</span>
                <textarea
                  maxLength="10000"
                  onChange={(event) => {
                    setIngredients(event.target.value);
                    setError('');
                  }}
                  placeholder="Paste or edit the ingredient list here. Separate items with commas or semicolons."
                  rows="6"
                  value={ingredients}
                />
              </label>
              <p className="entry-help">
                Pre-filled from this product when available. Edit OCR or Open Food Facts text to match the package; your submitted list is saved with this analysis.
              </p>
              {error && <p className="form-message form-message--error" role="alert">{error}</p>}
              <button className="button button--primary" disabled={saving} type="submit">
                {saving ? 'Analyzing ingredients...' : analysis ? 'Analyze updated list' : 'Analyze ingredients'}
              </button>
            </form>
            {analysis
              ? <AnalysisResults analysis={analysis} />
              : <div className="product-state product-state--empty">
                <h2>No ingredient analysis yet</h2>
                <p>Enter the ingredient list and start an analysis. Unmatched terms will be clearly marked as unknown.</p>
              </div>}
          </>
        )}
      </section>
    </main>
  );
}
