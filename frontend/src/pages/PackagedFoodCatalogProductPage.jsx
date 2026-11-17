import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  getCatalogAlternatives,
  getCatalogProduct,
} from '../api/catalog.js';
import {
  catalogErrorMessage,
  CATALOG_NUTRIENTS,
  formatCatalogValue,
} from '../utils/catalog.js';
import '../styles/catalog.css';

function sourceValue(value) {
  if (value == null || value === '') return 'Blank in source';
  return typeof value === 'string' ? value : JSON.stringify(value);
}

export default function PackagedFoodCatalogProductPage() {
  const { productId } = useParams();
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [alternatives, setAlternatives] = useState(null);
  const [alternativesLoading, setAlternativesLoading] = useState(false);
  const [alternativesError, setAlternativesError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    setProduct(null);
    getCatalogProduct(productId)
      .then(({ data }) => {
        if (active) setProduct(data.product);
      })
      .catch((requestError) => {
        if (active) {
          setError(
            requestError.response?.status === 404
              ? 'This catalog product was not found.'
              : catalogErrorMessage(
                requestError,
                'Could not load catalog product details. Please try again.',
              ),
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [productId]);

  useEffect(() => {
    if (!product) return undefined;
    let active = true;
    setAlternativesLoading(true);
    setAlternativesError('');
    getCatalogAlternatives(product.id)
      .then(({ data }) => {
        if (active) setAlternatives(data);
      })
      .catch((requestError) => {
        if (active) {
          setAlternativesError(
            catalogErrorMessage(
              requestError,
              'Could not load alternative products.',
            ),
          );
        }
      })
      .finally(() => {
        if (active) setAlternativesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [product]);

  return (
    <main className="product-page catalog-page">
      <header className="dashboard__header">
        <Link className="brand" to="/catalog" aria-label="Packaged food catalog">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <Link className="button button--quiet" to="/catalog">Back to catalog</Link>
      </header>

      <section className="product-content catalog-content catalog-detail-content">
        <Link className="product-back-link" to="/catalog">
          <span aria-hidden="true">←</span> Back to packaged food catalog
        </Link>
        {loading && <div className="product-state" role="status">Loading product details...</div>}
        {!loading && error && (
          <div className="product-state product-state--empty">
            <h1>Product details unavailable</h1>
            <p role="alert">{error}</p>
            <Link className="button button--outline" to="/catalog">Return to catalog</Link>
          </div>
        )}
        {!loading && product && (
          <>
            <div className="product-page__intro">
              <p className="eyebrow">Packaged food catalog</p>
              <h1>{product.name}</h1>
              <p>
                {product.brand || 'Brand not specified'}
                {product.category ? ` · ${product.category}` : ''}
                {product.subcategory ? ` · ${product.subcategory}` : ''}
              </p>
            </div>

            <div className="catalog-data-note">
              Dataset information is not independently verified. Nutrition values are
              shown on the stored <strong>{product.nutrition_basis || 'unavailable'}</strong>
              {' '}basis; missing values are not interpreted as zero.
            </div>

            <section className="catalog-detail-panel" aria-labelledby="catalog-nutrition-title">
              <div className="catalog-section-heading">
                <div>
                  <p className="eyebrow">Available information</p>
                  <h2 id="catalog-nutrition-title">Nutrition per inferred serving</h2>
                </div>
                <span className="catalog-serving">
                  Serving size: {formatCatalogValue(product.serving_size_g, 'g')}
                </span>
              </div>
              <dl className="catalog-nutrition-grid">
                {CATALOG_NUTRIENTS.map(([field, label, unit]) => (
                  <div className="catalog-nutrient" key={field}>
                    <dt>{label}</dt>
                    <dd>{formatCatalogValue(product.nutrition_per_serving[field], unit)}</dd>
                  </div>
                ))}
              </dl>
              {product.vitamin_details && (
                <div className="catalog-detail-text">
                  <h3>Additional vitamin information</h3>
                  <p>{sourceValue(product.vitamin_details)}</p>
                </div>
              )}
            </section>

            <section className="catalog-detail-panel" aria-labelledby="catalog-ingredients-title">
              <div className="catalog-section-heading">
                <div>
                  <p className="eyebrow">Product information</p>
                  <h2 id="catalog-ingredients-title">Ingredients</h2>
                </div>
              </div>
              <p className="catalog-ingredients">
                {product.ingredients || 'Ingredients not available in the source dataset.'}
              </p>
            </section>

            <section className="catalog-detail-panel" aria-labelledby="catalog-alternatives-title">
              <div className="catalog-section-heading">
                <div>
                  <p className="eyebrow">Rules-based comparison</p>
                  <h2 id="catalog-alternatives-title">Similar catalog products</h2>
                </div>
              </div>
              {alternativesLoading && (
                <p className="catalog-muted" role="status">Finding comparable catalog products...</p>
              )}
              {alternativesError && <p className="form-message form-message--error" role="alert">{alternativesError}</p>}
              {!alternativesLoading && alternatives && (
                <>
                  <p className="catalog-muted">{alternatives.message}</p>
                  {alternatives.recommendations.length === 0 && (
                    <p className="catalog-muted">No alternatives met the comparison rules with the available data.</p>
                  )}
                  <div className="catalog-alternative-list">
                    {alternatives.recommendations.map((recommendation) => (
                      <article className="catalog-alternative-card" key={recommendation.product.id}>
                        <div className="catalog-alternative-card__heading">
                          <div>
                            <h3>{recommendation.product.name}</h3>
                            <p>{recommendation.product.brand || 'Brand not specified'}</p>
                          </div>
                          <Link
                            className="button button--outline"
                            to={`/catalog/${recommendation.product.id}`}
                          >
                            View product
                          </Link>
                        </div>
                        <ul className="catalog-reasons">
                          {recommendation.why_suggested.map((reason) => (
                            <li key={reason}>{reason}</li>
                          ))}
                        </ul>
                        <div className="catalog-tradeoffs">
                          {recommendation.nutrient_changes.map((change) => (
                            <span
                              className={`catalog-tradeoff catalog-tradeoff--${change.interpretation}`}
                              key={change.nutrient}
                            >
                              {change.nutrient}: {formatCatalogValue(change.alternative_value_per_100g_comparable, change.unit)} per 100 g
                            </span>
                          ))}
                        </div>
                        <p className="catalog-muted">{recommendation.data_note}</p>
                      </article>
                    ))}
                  </div>
                  {alternatives.logic?.disclaimer && (
                    <p className="catalog-disclaimer">{alternatives.logic.disclaimer}</p>
                  )}
                </>
              )}
            </section>

            <details className="catalog-source-details">
              <summary>Source and data-quality details</summary>
              <dl className="catalog-provenance">
                <div><dt>Source</dt><dd>{product.provenance.source_name}</dd></div>
                <div><dt>Source row</dt><dd>{product.provenance.source_row_id}</dd></div>
                <div><dt>Source file SHA-256</dt><dd>{product.provenance.source_file_sha256 || 'Not available'}</dd></div>
                <div><dt>Source row SHA-256</dt><dd>{product.provenance.source_row_sha256 || 'Not available'}</dd></div>
                <div><dt>Source notes</dt><dd>{product.provenance.remarks || 'Not available'}</dd></div>
              </dl>
              {product.quality_flags?.length > 0 && (
                <div className="catalog-detail-text">
                  <h3>Data-quality flags</h3>
                  <ul className="catalog-reasons">
                    {product.quality_flags.map((flag, index) => (
                      <li key={`${flag}-${index}`}>{sourceValue(flag)}</li>
                    ))}
                  </ul>
                </div>
              )}
              {product.source_row_raw && (
                <div className="catalog-source-table-wrap">
                  <table className="catalog-source-table">
                    <caption>Original CSV cell values</caption>
                    <tbody>
                      {Object.entries(product.source_row_raw).map(([field, value]) => (
                        <tr key={field}>
                          <th scope="row">{field}</th>
                          <td>{sourceValue(value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </details>
          </>
        )}
      </section>
    </main>
  );
}
