import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import * as authApi from '../api/auth.js';

const INITIAL_FORM = {
  age: '',
  gender: '',
  height_cm: '',
  weight_kg: '',
  activity_level: '',
  dietary_preferences: [],
  health_goal: '',
};

const DIETARY_OPTIONS = [
  ['vegetarian', 'Vegetarian'],
  ['vegan', 'Vegan'],
  ['pescatarian', 'Pescatarian'],
  ['gluten_free', 'Gluten-free'],
  ['dairy_free', 'Dairy-free'],
  ['halal', 'Halal'],
  ['kosher', 'Kosher'],
  ['none', 'No specific preference'],
];

const ACTIVITY_OPTIONS = [
  ['sedentary', 'Mostly sitting'],
  ['light', 'Light activity 1–3 days/week'],
  ['moderate', 'Moderate activity 3–5 days/week'],
  ['active', 'Active 6–7 days/week'],
  ['very_active', 'Very active or physical job'],
];

const GOAL_OPTIONS = [
  ['general_wellness', 'Improve general wellness'],
  ['maintain_weight', 'Maintain my weight'],
  ['lose_weight', 'Lose weight'],
  ['gain_weight', 'Gain weight'],
  ['build_muscle', 'Build muscle'],
  ['manage_condition', 'Support a health condition'],
];

function messageFrom(error) {
  return error.response?.data?.message || 'We could not load your profile. Please try again.';
}

function updateFormFromProfile(profile) {
  if (!profile) return INITIAL_FORM;
  return {
    age: profile.age == null ? '' : String(profile.age),
    gender: profile.gender || '',
    height_cm: profile.height_cm == null ? '' : String(profile.height_cm),
    weight_kg: profile.weight_kg == null ? '' : String(profile.weight_kg),
    activity_level: profile.activity_level || '',
    dietary_preferences: profile.dietary_preferences || [],
    health_goal: profile.health_goal,
  };
}

function BmiIndicator({ bmi }) {
  const position = Math.max(0, Math.min(100, ((bmi.value - 12) / 28) * 100));
  const adultCategories = bmi.category !== 'not_classified';

  return (
    <section className="result-card" aria-label="BMI result">
      <div className="result-card__heading">
        <div>
          <p className="eyebrow">Body mass index</p>
          <div className="bmi-value">{bmi.value}</div>
        </div>
        <span className={`bmi-tag${adultCategories ? '' : ' bmi-tag--neutral'}`}>
          {bmi.label}
        </span>
      </div>
      <div
        className={`bmi-scale${adultCategories ? '' : ' bmi-scale--neutral'}`}
        role="img"
        aria-label={
          adultCategories
            ? `BMI ${bmi.value}: ${bmi.label}`
            : `BMI ${bmi.value}; adult categories do not apply`
        }
      >
        <div className="bmi-scale__bar">
          <span className="bmi-scale__segment bmi-scale__segment--low" />
          <span className="bmi-scale__segment bmi-scale__segment--healthy" />
          <span className="bmi-scale__segment bmi-scale__segment--high" />
          <span className="bmi-scale__segment bmi-scale__segment--very-high" />
          {adultCategories && (
            <span className="bmi-scale__marker" style={{ left: `${position}%` }} />
          )}
        </div>
        {adultCategories ? (
          <div className="bmi-scale__labels">
            <span>Below 18.5</span><span>18.5–24.9</span><span>25–29.9</span><span>30+</span>
          </div>
        ) : (
          <p className="bmi-scale__minor-note">Adult BMI cutoffs are not shown</p>
        )}
      </div>
      {!adultCategories && (
        <p className="result-note">
          BMI is shown for reference only. Adult BMI categories are not used for people under 18.
          A healthcare professional can interpret BMI using age- and growth-specific measures.
        </p>
      )}
      {adultCategories && (
        <p className="result-note">
          BMI is a screening measure, not a diagnosis. Individual health factors matter.
        </p>
      )}
    </section>
  );
}

export default function HealthProfilePage() {
  const navigate = useNavigate();
  const [form, setForm] = useState(INITIAL_FORM);
  const [profile, setProfile] = useState(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    let active = true;
    authApi.getHealthProfile()
      .then(({ data }) => {
        if (!active) return;
        setProfile(data.profile);
        setForm(updateFormFromProfile(data.profile));
      })
      .catch((requestError) => {
        if (active) setError(messageFrom(requestError));
      })
      .finally(() => {
        if (active) setInitialLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function update(event) {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
    setError('');
    setSuccess('');
  }

  function togglePreference(preference) {
    setForm((current) => ({
      ...current,
      dietary_preferences: current.dietary_preferences.includes(preference)
        ? current.dietary_preferences.filter((item) => item !== preference)
        : [...current.dietary_preferences, preference],
    }));
    setSuccess('');
  }

  function validate() {
    const age = Number(form.age);
    const height = Number(form.height_cm);
    const weight = Number(form.weight_kg);
    if (!Number.isInteger(age) || age < 1 || age > 120) {
      return 'Enter an age between 1 and 120.';
    }
    if (!Number.isFinite(height) || height < 80 || height > 250) {
      return 'Height must be between 80 and 250 cm.';
    }
    if (!Number.isFinite(weight) || weight < 20 || weight > 400) {
      return 'Weight must be between 20 and 400 kg.';
    }
    if (!form.activity_level || !form.health_goal) {
      return 'Choose an activity level and a health goal.';
    }
    return '';
  }

  async function submit(event) {
    event.preventDefault();
    setSuccess('');
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);
    setError('');
    try {
      const { data } = await authApi.saveHealthProfile({
        ...form,
        age: Number(form.age),
        height_cm: Number(form.height_cm),
        weight_kg: Number(form.weight_kg),
      });
      setProfile(data.profile);
      setForm(updateFormFromProfile(data.profile));
      setSuccess('Your health profile has been saved.');
    } catch (requestError) {
      setError(messageFrom(requestError));
    } finally {
      setSaving(false);
    }
  }

  if (initialLoading) {
    return <main className="app-loading">Loading your health profile...</main>;
  }

  return (
    <main className="profile-page">
      <header className="dashboard__header">
        <Link className="brand" to="/" aria-label="NutriScan dashboard">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <button className="button button--quiet" onClick={() => navigate('/')} type="button">
          Back to dashboard
        </button>
      </header>

      <div className="profile-layout">
        <section className="profile-intro">
          <p className="eyebrow">{profile ? 'Your wellbeing, your way' : 'A thoughtful first step'}</p>
          <h1>{profile ? 'Your health profile' : 'Let’s get to know you.'}</h1>
          <p>
            A few details help NutriScan tailor nutrition insights to your needs.
            You can update these details any time.
          </p>
          <div className="profile-privacy">
            <span aria-hidden="true">✓</span>
            Your health information is private to your account.
          </div>
        </section>

        <div className="profile-content">
          <form className="profile-form" onSubmit={submit} noValidate>
            <section className="form-section">
              <div className="form-section__heading">
                <span className="section-number">01</span>
                <div>
                  <h2>About you</h2>
                  <p>Used to make estimates more relevant.</p>
                </div>
              </div>
              <div className="profile-fields profile-fields--two">
                <label className="field">
                  <span>Age</span>
                  <div className="input-with-unit">
                    <input
                      max="120"
                      min="1"
                      name="age"
                      onChange={update}
                      placeholder="e.g. 28"
                      required
                      type="number"
                      value={form.age}
                    />
                    <span>years</span>
                  </div>
                </label>
                <label className="field">
                  <span>Gender <em>Optional</em></span>
                  <select name="gender" onChange={update} value={form.gender}>
                    <option value="">Prefer not to specify</option>
                    <option value="woman">Woman</option>
                    <option value="man">Man</option>
                    <option value="non_binary">Non-binary</option>
                    <option value="prefer_not_to_say">Prefer not to say</option>
                  </select>
                </label>
                <label className="field">
                  <span>Height</span>
                  <div className="input-with-unit">
                    <input
                      max="250"
                      min="80"
                      name="height_cm"
                      onChange={update}
                      placeholder="e.g. 168"
                      required
                      step="0.1"
                      type="number"
                      value={form.height_cm}
                    />
                    <span>cm</span>
                  </div>
                </label>
                <label className="field">
                  <span>Weight</span>
                  <div className="input-with-unit">
                    <input
                      max="400"
                      min="20"
                      name="weight_kg"
                      onChange={update}
                      placeholder="e.g. 65"
                      required
                      step="0.1"
                      type="number"
                      value={form.weight_kg}
                    />
                    <span>kg</span>
                  </div>
                </label>
              </div>
            </section>

            <section className="form-section">
              <div className="form-section__heading">
                <span className="section-number">02</span>
                <div>
                  <h2>Your lifestyle</h2>
                  <p>Choose the closest fit for a typical week.</p>
                </div>
              </div>
              <label className="field">
                <span>Activity level</span>
                <select
                  name="activity_level"
                  onChange={update}
                  required
                  value={form.activity_level}
                >
                  <option value="">Select your typical activity</option>
                  {ACTIVITY_OPTIONS.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
              <fieldset className="preference-field">
                <legend>Dietary preferences <em>Optional</em></legend>
                <div className="preference-grid">
                  {DIETARY_OPTIONS.map(([value, label]) => (
                    <label className="check-option" key={value}>
                      <input
                        checked={form.dietary_preferences.includes(value)}
                        onChange={() => togglePreference(value)}
                        type="checkbox"
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
              </fieldset>
            </section>

            <section className="form-section">
              <div className="form-section__heading">
                <span className="section-number">03</span>
                <div>
                  <h2>Your health goal</h2>
                  <p>There’s no wrong answer; you can change this later.</p>
                </div>
              </div>
              <label className="field">
                <span>What would you like to focus on?</span>
                <select name="health_goal" onChange={update} required value={form.health_goal}>
                  <option value="">Select a goal</option>
                  {GOAL_OPTIONS.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
            </section>

            {error && <p className="form-message form-message--error" role="alert">{error}</p>}
            {success && <p className="form-message form-message--success" role="status">{success}</p>}
            <button className="button button--primary profile-submit" disabled={saving} type="submit">
              {saving ? 'Saving your profile...' : profile ? 'Save changes' : 'Save my profile'}
            </button>
          </form>

          {profile?.bmi && (
            <aside className="profile-results" aria-live="polite">
              <BmiIndicator bmi={profile.bmi} />
              <section className="result-card calorie-card">
                <p className="eyebrow">Daily energy estimate</p>
                {profile.daily_calories ? (
                  <>
                    <div className="calorie-value">
                      {profile.daily_calories.minimum.toLocaleString()}
                      <span>–</span>
                      {profile.daily_calories.maximum.toLocaleString()}
                      <small>kcal / day</small>
                    </div>
                    <p className="result-note">
                      {profile.daily_calories.method}. This is a general estimate, not a
                      prescribed intake.
                    </p>
                  </>
                ) : (
                  <p className="result-note">
                    Adult calorie equations are not provided for people under 18. A pediatric
                    healthcare professional can advise on age-appropriate needs.
                  </p>
                )}
              </section>
            </aside>
          )}
        </div>
      </div>
    </main>
  );
}
