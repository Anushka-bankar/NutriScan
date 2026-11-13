import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { compareProducts } from '../api/products.js';

export default function ProductComparisonPage() {
  const [params] = useSearchParams();
  const ids = params.get('ids') || '';
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const productIds = ids.split(',').filter(Boolean);
    if (productIds.length < 2) {
      setError('Choose at least two products from your watchlist to compare.');
      setLoading(false);
      setComparison(null);
      return () => {
        active = false;
      };
    }
    setLoading(true);
    setError('');
    compareProducts(productIds)
      .then(({ data }) => {
        if (active) setComparison(data);
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.response?.data?.message || 'Could not compare these products.');
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [ids]);

  if (loading) return <main className="app-loading">Preparing product comparison...</main>;

  return (
    <main className="product-page">
      <header className="dashboard__header">
        <Link className="brand" to="/watchlist" aria-label="Your watchlist">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <Link className="button button--quiet" to="/watchlist">Back to watchlist</Link>
      </header>
      <section className="product-content product-content--detail">
        <div className="product-page__intro">
          <p className="eyebrow">Per 100 g</p>
          <h1>Compare products</h1>
          <p>Review saved nutrition facts side by side. Missing values are shown as unavailable.</p>
        </div>
        <div className="data-warning">
          <strong>User-entered data · not independently verified</strong>
          <span>Comparisons reflect entered nutrition values and are not a medical assessment.</span>
        </div>
        {error && (
          <div className="product-state product-state--empty">
            <h2>Comparison unavailable</h2>
            <p role="alert">{error}</p>
            <Link className="text-link" to="/watchlist">Return to your watchlist</Link>
          </div>
        )}
        {comparison && (
          <div className="comparison-table-wrap">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th scope="col">Nutrition</th>
                  {comparison.products.map((product) => (
                    <th scope="col" key={product.id}>
                      <Link to={`/products/${product.id}`}>{product.name}</Link>
                      <small>{product.brand || 'Brand not specified'}</small>
                      <span className="source-badge">{product.source_label}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparison.nutrients.map((nutrient) => (
                  <tr key={nutrient.field}>
                    <th scope="row">{nutrient.label}</th>
                    {nutrient.values.map((value, index) => (
                      <td key={comparison.products[index].id}>
                        {value == null
                          ? 'Unavailable'
                          : `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${nutrient.unit}`}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
