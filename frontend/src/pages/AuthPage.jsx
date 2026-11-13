import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';

function errorMessage(error) {
  return error.response?.data?.message || 'We could not complete your request. Please try again.';
}

export default function AuthPage({ mode }) {
  const isSignup = mode === 'signup';
  const { isAuthenticated, loading, signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: '', email: '', password: '', confirmPassword: '' });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!loading && isAuthenticated && !submitting) return <Navigate to="/" replace />;

  function update(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  async function submit(event) {
    event.preventDefault();
    setError('');

    const email = form.email.trim();
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Enter a valid email address.');
      return;
    }
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (isSignup && !form.full_name.trim()) {
      setError('Enter your name.');
      return;
    }
    if (isSignup && form.password !== form.confirmPassword) {
      setError('Your passwords do not match.');
      return;
    }

    setSubmitting(true);
    try {
      if (isSignup) {
        await signUp({ full_name: form.full_name.trim(), email, password: form.password });
      } else {
        await signIn({ email, password: form.password });
      }
      navigate(isSignup ? '/profile/setup' : '/', { replace: true });
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-layout">
      <aside className="auth-aside">
        <Link className="brand" to="/login" aria-label="NutriScan home">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <div className="auth-aside__copy">
          <p className="eyebrow">Food choices, made clearer</p>
          <h1>A more mindful way to nourish yourself.</h1>
          <p>Personalized nutrition starts with understanding what matters to you.</p>
        </div>
        <div className="aside-note">
          <span className="aside-note__dot" />
          Built around your wellbeing
        </div>
      </aside>

      <section className="auth-main" aria-labelledby="auth-title">
        <div className="auth-card">
          <div className="auth-card__mobile-brand">
            <span className="brand__icon" aria-hidden="true">N</span>
            <span>NutriScan</span>
          </div>
          <p className="eyebrow">{isSignup ? 'Your nutrition journey' : 'Welcome back'}</p>
          <h2 id="auth-title">{isSignup ? 'Create your account' : 'Sign in to NutriScan'}</h2>
          <p className="auth-subtitle">
            {isSignup
              ? 'A few details to make your experience personal.'
              : 'Your personal nutrition space is ready when you are.'}
          </p>

          <form className="auth-form" onSubmit={submit} noValidate>
            {isSignup && (
              <label className="field">
                <span>Full name</span>
                <input
                  autoComplete="name"
                  name="full_name"
                  onChange={update}
                  placeholder="Your name"
                  required
                  value={form.full_name}
                />
              </label>
            )}
            <label className="field">
              <span>Email address</span>
              <input
                autoComplete="email"
                name="email"
                onChange={update}
                placeholder="you@example.com"
                required
                type="email"
                value={form.email}
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                autoComplete={isSignup ? 'new-password' : 'current-password'}
                name="password"
                onChange={update}
                placeholder={isSignup ? 'At least 8 characters' : 'Enter your password'}
                required
                type="password"
                value={form.password}
              />
            </label>
            {isSignup && (
              <label className="field">
                <span>Confirm password</span>
                <input
                  autoComplete="new-password"
                  name="confirmPassword"
                  onChange={update}
                  placeholder="Re-enter your password"
                  required
                  type="password"
                  value={form.confirmPassword}
                />
              </label>
            )}

            {error && <p className="form-message form-message--error" role="alert">{error}</p>}
            <button className="button button--primary" disabled={submitting} type="submit">
              {submitting ? 'Please wait...' : isSignup ? 'Create account' : 'Sign in'}
            </button>
          </form>

          <p className="auth-switch">
            {isSignup ? 'Already have an account?' : 'New to NutriScan?'}
            {' '}
            <Link to={isSignup ? '/login' : '/signup'}>
              {isSignup ? 'Sign in' : 'Create an account'}
            </Link>
          </p>
          <p className="privacy-note">Your health journey is personal. Your account is yours.</p>
        </div>
      </section>
    </main>
  );
}
