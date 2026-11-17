import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getHealthProfile } from '../api/auth.js';
import { useAuth } from '../auth/AuthContext.jsx';
import { getBmiCategoryLabel } from '../utils/bmi.js';

export default function Dashboard() {
  const { user, signOut } = useAuth();
  const [profile, setProfile] = useState(undefined);
  const [profileError, setProfileError] = useState('');

  useEffect(() => {
    let active = true;
    getHealthProfile()
      .then(({ data }) => {
        if (active) setProfile(data.profile);
      })
      .catch(() => {
        if (active) setProfileError('Your health profile could not be loaded.');
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="dashboard">
      <header className="dashboard__header">
        <Link className="brand" to="/" aria-label="NutriScan">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <button className="button button--quiet" onClick={signOut} type="button">Sign out</button>
      </header>
      <section className="dashboard__welcome">
        <p className="eyebrow">Your personal nutrition space</p>
        <h1>Welcome, {user?.full_name}.</h1>
        <p>You’re signed in. Your NutriScan journey starts here.</p>
        {profileError && <p className="form-message form-message--error" role="alert">{profileError}</p>}
        {profile === undefined && !profileError && (
          <p className="dashboard-loading">Loading your health profile...</p>
        )}
        {profile === null && (
          <div className="dashboard-card">
            <span className="dashboard-card__icon" aria-hidden="true">+</span>
            <div className="dashboard-card__content">
              <h2>Set up your health profile</h2>
              <p>Add a few details to get personalized nutrition insights and estimates.</p>
              <Link className="text-link" to="/profile/setup">Set up profile</Link>
            </div>
          </div>
        )}
        {profile && (
          <div className="dashboard-card">
            <span className="dashboard-card__icon" aria-hidden="true">✓</span>
            <div className="dashboard-card__content">
              <h2>Your profile is ready</h2>
              <p>
                BMI {profile.bmi.value} · {getBmiCategoryLabel(profile.bmi.category) || profile.bmi.label}
                {profile.daily_calories
                  ? ` · ${profile.daily_calories.minimum.toLocaleString()}–${profile.daily_calories.maximum.toLocaleString()} kcal/day estimated`
                  : ''}
              </p>
              <Link className="text-link" to="/profile/setup">View or update profile</Link>
            </div>
          </div>
        )}
        <div className="dashboard-card">
          <span className="dashboard-card__icon" aria-hidden="true">⌕</span>
          <div className="dashboard-card__content">
            <h2>Explore product nutrition</h2>
            <p>Search your product analyses or add nutrition values from a product label.</p>
            <Link className="text-link" to="/products">Search products</Link>
          </div>
        </div>
        <div className="dashboard-card dashboard-card--links">
          <div className="dashboard-card__content">
            <h2>Your product activity</h2>
            <p>Revisit analyzed products or return to products saved for later.</p>
            <div className="dashboard-shortcuts">
              <Link className="text-link" to="/history">View history</Link>
              <Link className="text-link" to="/watchlist">Open watchlist</Link>
              <Link className="text-link" to="/products/compare">Compare products</Link>
            </div>
          </div>
        </div>
        <div className="dashboard-card">
          <span className="dashboard-card__icon" aria-hidden="true">✓</span>
          <div>
            <h2>Your account is ready</h2>
            <p>We’ll help you make informed food choices, one step at a time.</p>
          </div>
        </div>
      </section>
    </main>
  );
}
