import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getRecommendations } from '../api/products.js';

const NUTRIENTS = [
  ['calories_kcal', 'Calories', 'kcal'],
  ['energy_kj', 'Energy', 'kJ'],
  ['carbohydrates_g', 'Carbohydrates', 'g'],
  ['sugars_g', 'Total sugar', 'g'],
  ['protein_g', 'Protein', 'g'],
  ['total_fat_g', 'Total fat', 'g'],
  ['saturated_fat_g', 'Saturated fat', 'g'],
  ['fibre_g', 'Fibre', 'g'],
  ['sodium_mg', 'Sodium', 'mg'],
];

const GOAL_LABELS = {
  lose_weight: 'weight-loss goal',
  maintain_weight: 'weight-maintenance goal',
  gain_weight: 'weight-gain goal',
  build_muscle: 'muscle-building goal',
  general_wellness: 'general-wellness goal',
  manage_condition: 'health goal',
};

function display(value, unit) {
  return value == null
    ? 'Unavailable'
    : `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit}`;
}

function reasonTitle(reason) {
  if (!reason) return 'This alternative aligns with your selected goal.';
  return reason;
}

export default function ProductRecommendationsPage() {
  const { productId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    getRecommendations(productId)
      .then(({ data: response }) => {
        if (active) setData(response);
      })
      .catch((requestError) => {
        if (!active) return;
        const status = requestError.response?.status;
        setError(
          status === 404
            ? 'This product is not available in your saved products.'
            : requestError.response?.data?.message
              || 'Could not load recommendations. Please try again.',
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [productId]);

  if (loading) {
    return <main className="app-loading">Finding comparable products...</main>;
  }

  return (
    <main className="product-page">
      <header className="dashboard__header">
        <Link className="brand" to="/products" aria-label="Product nutrition search">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <Link className="button button--quiet" to={data ? `/products/${data.target.id}` : '/products'}>
          Back to product
        </Link>
      </header>

      <section className="product-content product-content--detail">
        {error && (
          <div className="product-state product-state--empty">
            <h1>Recommendations unavailable</h1>
            <p role="alert">{error}</p>
            <Link className="text-link" to="/products">Return to product search</Link>
          </div>
        )}
        {data && (
          <>
            <div className="product-page__intro">
              <p className="eyebrow">Based on your health profile</p>
              <h1>Similar product alternatives</h1>
              <p>
                Comparing <strong>{data.target.name}</strong> with your saved
                {' '}{data.target.category_label.toLowerCase()} products for your
                {' '}{GOAL_LABELS[data.health_goal] || 'health goal'}.
              </p>
            </div>
            <div className="data-warning data-warning--compact">
              All product values and dietary tags are user-entered and not independently verified.
              Check packaging and suitability with the product manufacturer.
            </div>

            {data.recommendations.length === 0 && (
              <div className="product-state product-state--empty">
                <span className="empty-mark" aria-hidden="true">⌕</span>
                <h2>No suitable alternative found</h2>
                <p>{data.message}</p>
                <p className="recommendation-rules">{data.rules}</p>
                <Link className="text-link" to="/products/new">Add another similar product</Link>
              </div>
            )}

            {data.recommendations.length > 0 && (
              <div className="recommendation-list">
                <p className="recommendation-rules">{data.rules}</p>
                {data.recommendations.map((recommendation) => {
                  const alternative = recommendation.product;
                  return (
                    <article className="recommendation-card" key={alternative.id}>
                      <div className="recommendation-card__heading">
                        <div>
                          <span className="recommendation-kicker">Potentially better fit</span>
                          <h2>{alternative.name}</h2>
                          <p>{alternative.brand || 'Brand not specified'} · {alternative.category_label}</p>
                        </div>
                        <span className="source-badge">{alternative.source_label}</span>
                      </div>
                      <ul className="recommendation-reasons">
                        {recommendation.reasons.map((reason) => (
                          <li key={reason}><span aria-hidden="true">✓</span>{reasonTitle(reason)}</li>
                        ))}
                      </ul>

                      <div className="recommendation-table-wrap">
                        <table className="recommendation-table">
                          <caption>Nutrition comparison per 100 g</caption>
                          <thead>
                            <tr>
                              <th scope="col">Nutrient</th>
                              <th scope="col">{data.target.name}</th>
                              <th scope="col">{alternative.name}</th>
                              <th scope="col">Difference</th>
                            </tr>
                          </thead>
                          <tbody>
                            {recommendation.comparisons.map((item) => {
                              const nutrient = NUTRIENTS.find(([field]) => field === item.field);
                              const unit = nutrient?.[2] || '';
                              return (
                                <tr key={item.field}>
                                  <th scope="row">{item.label}</th>
                                  <td>{display(item.target_value, unit)}</td>
                                  <td>{display(item.alternative_value, unit)}</td>
                                  <td className={item.goal_improvement ? 'difference difference--better' : ''}>
                                    {item.difference == null
                                      ? 'Unavailable'
                                      : `${item.difference > 0 ? '+' : ''}${display(item.difference, unit)}`}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>

                      <div className="recommendation-card__footer">
                        <p>
                          This is a relative comparison, not a medical assessment or guarantee
                          that the alternative is healthier for everyone.
                        </p>
                        <Link className="button button--primary" to={`/products/${alternative.id}`}>
                          View product details
                        </Link>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </>
        )}
      </section>
    </main>
  );
}
