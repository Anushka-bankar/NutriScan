import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { compareCatalogProducts } from '../api/catalog.js';
import {
  catalogErrorMessage,
  CATALOG_NUTRIENTS,
  formatCatalogValue,
} from '../utils/catalog.js';
import '../styles/catalog.css';

function ProductHeading({ product }) {
  return (
    <>
      <Link to={`/catalog/${product.id}`}>{product.name}</Link>
      <small>{product.brand || 'Brand not specified'}</small>
      <small>Serving: {formatCatalogValue(product.serving_size_g, 'g')}</small>
      <small>Basis: {product.nutrition_basis || 'Not available'}</small>
    </>
  );
}

export default function PackagedFoodCatalogComparePage() {
  const [params] = useSearchParams();
  const productId1 = params.get('product_id_1') || '';
  const productId2 = params.get('product_id_2') || '';
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setData(null);
    setLoading(true);
    setError('');
    if (!productId1 || !productId2) {
      setError('Choose two catalog products before opening comparison.');
      setLoading(false);
      return () => {
        active = false;
      };
    }
    compareCatalogProducts(productId1, productId2)
      .then(({ data: response }) => {
        if (active) setData(response);
      })
      .catch((requestError) => {
        if (active) {
          setError(
            catalogErrorMessage(
              requestError,
              'Could not compare these catalog products. Please try again.',
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
  }, [productId1, productId2]);

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
        <div className="product-page__intro">
          <p className="eyebrow">Packaged food dataset</p>
          <h1>Compare catalog products</h1>
          <p>Review source values side by side. This comparison does not provide a health score.</p>
        </div>

        {loading && <div className="product-state" role="status">Comparing catalog products...</div>}
        {!loading && error && (
          <div className="product-state product-state--empty">
            <h2>Comparison unavailable</h2>
            <p role="alert">{error}</p>
            <Link className="button button--outline" to="/catalog">Return to catalog</Link>
          </div>
        )}
        {!loading && data && (
          <>
            <div className="catalog-comparison-notes">
              <strong>Serving and measurement basis</strong>
              <ul>
                {data.comparison.notes.map((note) => <li key={note}>{note}</li>)}
              </ul>
              <p>
                Serving sizes: <strong>{data.comparison.serving_size_relation}</strong>
                {' · '}Measurement bases match:{' '}
                <strong>{data.comparison.measurement_bases_match ? 'Yes' : 'No'}</strong>
              </p>
            </div>
            <div className="catalog-comparison-wrap">
              <table className="comparison-table catalog-comparison-table">
                <thead>
                  <tr>
                    <th scope="col">Nutrition</th>
                    <th scope="col"><ProductHeading product={data.product_1} /></th>
                    <th scope="col"><ProductHeading product={data.product_2} /></th>
                    <th scope="col">Per 100 g difference<br /><small>Product 2 − Product 1</small></th>
                  </tr>
                </thead>
                <tbody>
                  {CATALOG_NUTRIENTS.map(([field, label, unit]) => {
                    const nutrient = data.comparison.nutrients[field];
                    return (
                      <tr key={field}>
                        <th scope="row">{label}</th>
                        <td>
                          {formatCatalogValue(nutrient.product_1_per_serving, unit)}
                          <small>per serving{nutrient.per_serving_comparable ? '' : ' · not directly comparable'}</small>
                        </td>
                        <td>
                          {formatCatalogValue(nutrient.product_2_per_serving, unit)}
                          <small>per serving{nutrient.per_serving_comparable ? '' : ' · not directly comparable'}</small>
                        </td>
                        <td>
                          {nutrient.per_100g_comparable
                            ? `${nutrient.difference_per_100g_product_2_minus_product_1 > 0 ? '+' : ''}${formatCatalogValue(nutrient.difference_per_100g_product_2_minus_product_1, unit)}`
                            : 'Not available'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="catalog-comparison-ingredients">
              <article>
                <h2>{data.product_1.name} ingredients</h2>
                <p>{data.product_1.ingredients || 'Not available'}</p>
              </article>
              <article>
                <h2>{data.product_2.name} ingredients</h2>
                <p>{data.product_2.ingredients || 'Not available'}</p>
              </article>
            </div>
            <p className="catalog-disclaimer">
              Per-serving values are shown as stored and are not directly comparable when the
              serving sizes or measurement bases differ. Per-100 g values are shown only when
              the backend can normalize them from a supported basis. This is informational,
              not medical advice.
            </p>
          </>
        )}
      </section>
    </main>
  );
}
