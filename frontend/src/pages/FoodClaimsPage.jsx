import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { analyzeFoodClaims, getFoodClaimHistory, getProduct } from '../api/products.js';

const STATUS_LABELS = {
  supported: 'Appears supported',
  potentially_inconsistent: 'Potentially inconsistent',
  unverifiable: 'Unable to verify',
};

function messageFrom(error) {
  return error.response?.data?.message || 'Could not load claim analysis. Please try again.';
}

function displayEvidenceValue(value) {
  if (value == null) return 'Unavailable';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function ClaimResult({ claim }) {
  return (
    <article className="food-claim-card">
      <header className="food-claim-card__header">
        <div>
          <p className="eyebrow">{claim.category}</p>
          <h3>“{claim.text}”</h3>
        </div>
        <span className={`food-claim-status food-claim-status--${claim.status}`}>
          {STATUS_LABELS[claim.status]}
        </span>
      </header>
      <p className="food-claim-card__explanation">{claim.explanation}</p>
      {claim.criteria && (
        <p className="food-claim-card__criteria"><strong>Reference criterion:</strong> {claim.criteria}</p>
      )}
      {claim.evidence.length > 0 && (
        <dl className="food-claim-evidence">
          {claim.evidence.map((item, index) => (
            <div key={`${item.field || item.label}-${index}`}>
              <dt>{item.label}</dt>
              <dd>
                {displayEvidenceValue(item.value)}
                {item.value != null && item.unit ? ` ${item.unit}` : ''}
                {item.basis ? ` (${item.basis})` : ''}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {claim.references.length > 0 && (
        <ul className="food-claim-references">
          {claim.references.map((reference) => (
            <li key={reference.url}>
              <a href={reference.url} rel="noreferrer" target="_blank">{reference.title}</a>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function AnalysisResults({ analysis }) {
  const { summary } = analysis;
  return (
    <section className="food-claims-results" aria-live="polite">
      <div className="food-claims-results__heading">
        <div>
          <p className="eyebrow">Saved analysis</p>
          <h2>Packaging claim review</h2>
        </div>
        <time dateTime={analysis.analyzed_at}>{new Date(analysis.analyzed_at).toLocaleString()}</time>
      </div>
      <p className="result-note">
        Claim text source: {analysis.input_source === 'ocr' ? 'Saved package OCR' : 'Manual or edited text'}.
        Product evidence was saved as a snapshot at this time.
      </p>
      <div className="food-claim-summary">
        <div><strong>{summary.supported_count}</strong><span>Appears supported</span></div>
        <div><strong>{summary.potentially_inconsistent_count}</strong><span>Potentially inconsistent</span></div>
        <div><strong>{summary.unverifiable_count}</strong><span>Unable to verify</span></div>
      </div>
      {analysis.personal_context.length > 0 && (
        <div className="food-claim-context">
          {analysis.personal_context.map((item) => <p key={item}>{item}</p>)}
        </div>
      )}
      {analysis.claims.length === 0 ? (
        <div className="product-state product-state--empty">
          <h3>No supported claim patterns detected</h3>
          <p>Review the supplied text or enter a claim exactly as it appears on the package.</p>
        </div>
      ) : (
        <div className="food-claim-list">
          {analysis.claims.map((claim, index) => (
            <ClaimResult claim={claim} key={`${claim.code}-${claim.start}-${index}`} />
          ))}
        </div>
      )}
      <p className="data-warning ingredient-disclaimer">{analysis.disclaimer}</p>
    </section>
  );
}

export default function FoodClaimsPage() {
  const { productId } = useParams();
  const [product, setProduct] = useState(null);
  const [claimText, setClaimText] = useState('');
  const [history, setHistory] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    setProduct(null);
    setAnalysis(null);
    setHistory([]);
    Promise.all([getProduct(productId), getFoodClaimHistory(productId)])
      .then(([productResponse, historyResponse]) => {
        if (!active) return;
        const savedProduct = productResponse.data.product;
        const entries = historyResponse.data.history || [];
        setProduct(savedProduct);
        setHistory(entries);
        setClaimText(
          savedProduct.packaging_text
          || entries[0]?.claim_text
          || '',
        );
        setAnalysis(entries[0] || null);
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
    if (!claimText.trim()) {
      setError('Enter one or more packaging claims or use the saved OCR text.');
      return;
    }
    if (claimText.length > 20000) {
      setError('Claim text must be at most 20000 characters.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const { data } = await analyzeFoodClaims(productId, claimText);
      setAnalysis(data.analysis);
      setHistory((current) => [data.analysis, ...current]);
    } catch (requestError) {
      setError(messageFrom(requestError));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <main className="app-loading">Loading packaging claim analysis...</main>;
  }

  return (
    <main className="product-page">
      <header className="dashboard__header">
        <Link className="brand" to="/products" aria-label="Product nutrition search">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <Link className="button button--quiet" to={product ? `/products/${product.id}` : '/products'}>
          Back to product
        </Link>
      </header>
      <section className="product-content product-content--detail food-claims-page">
        {error && !product ? (
          <div className="product-state product-state--empty">
            <h1>Claims unavailable</h1>
            <p role="alert">{error}</p>
            <Link className="text-link" to="/products">Return to product search</Link>
          </div>
        ) : product && (
          <>
            <div className="product-page__intro">
              <p className="eyebrow">Preliminary label-data review</p>
              <h1>Packaging claims</h1>
              <p>{product.name}{product.brand ? ` · ${product.brand}` : ''}</p>
              <p>Compare recognizable package claims with the saved nutrition facts and ingredient list.</p>
            </div>
            <div className="data-warning">
              <strong>Not official verification</strong>
              <span>
                Saved product data can be user-entered, OCR-extracted, or community-sourced.
                NutriScan does not independently verify packaging claims or determine legal compliance.
              </span>
            </div>
            <form className="food-claims-input" onSubmit={submitAnalysis}>
              <label className="field" htmlFor="food-claims-text">
                <span>Packaging text or claims</span>
                <textarea
                  id="food-claims-text"
                  maxLength={20000}
                  onChange={(event) => {
                    setClaimText(event.target.value);
                    setError('');
                  }}
                  placeholder="Paste or type claims as they appear on the package."
                  rows={7}
                  value={claimText}
                />
              </label>
              {product.packaging_text && (
                <p className="result-note">
                  Prefilled with text extracted from the package photo. Correct OCR mistakes before analysis.
                </p>
              )}
              <button className="button button--primary" disabled={saving} type="submit">
                {saving ? 'Checking claims...' : 'Analyze claims'}
              </button>
              {error && <p className="form-message form-message--error" role="alert">{error}</p>}
            </form>

            {analysis && <AnalysisResults analysis={analysis} />}

            {history.length > 1 && (
              <section className="food-claim-history">
                <h2>Earlier saved analyses</h2>
                <ul>
                  {history.slice(1).map((entry) => (
                    <li key={entry.id}>
                      <time dateTime={entry.analyzed_at}>{new Date(entry.analyzed_at).toLocaleString()}</time>
                      <span>{entry.summary.claim_count} claims · {entry.product_name}</span>
                      <button
                        className="text-link"
                        onClick={() => {
                          setAnalysis(entry);
                          setClaimText(entry.claim_text);
                        }}
                        type="button"
                      >
                        View saved result
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}
      </section>
    </main>
  );
}
