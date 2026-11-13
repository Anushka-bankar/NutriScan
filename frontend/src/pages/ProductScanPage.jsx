import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  importBarcodeProduct,
  importOcrProduct,
  lookupBarcode,
} from '../api/products.js';
import { parseNutritionLabel } from '../utils/labelParser.js';

const CATEGORIES = [
  ['grains_cereals', 'Grains & cereals'],
  ['snacks', 'Snacks'],
  ['beverages', 'Beverages'],
  ['dairy', 'Dairy'],
  ['dairy_alternatives', 'Dairy alternatives'],
  ['meat_poultry', 'Meat & poultry'],
  ['seafood', 'Seafood'],
  ['plant_protein', 'Plant proteins'],
  ['fruits_vegetables', 'Fruits & vegetables'],
  ['condiments_sauces', 'Condiments & sauces'],
  ['prepared_meals', 'Prepared meals'],
  ['bakery', 'Bakery'],
  ['other', 'Other'],
];

const NUTRIENTS = [
  ['energy_kj', 'Energy', 'kJ', 3766, 1],
  ['calories_kcal', 'Calories', 'kcal', 900, 1],
  ['carbohydrates_g', 'Carbohydrates', 'g', 100, 2],
  ['sugars_g', 'Total sugar', 'g', 100, 2],
  ['protein_g', 'Protein', 'g', 100, 2],
  ['total_fat_g', 'Total fat', 'g', 100, 2],
  ['saturated_fat_g', 'Saturated fat', 'g', 100, 2],
  ['fibre_g', 'Fibre', 'g', 100, 2],
  ['sodium_mg', 'Sodium', 'mg', 100000, 2],
];

const EMPTY_OCR = {
  name: '',
  brand: '',
  barcode: '',
  ingredients: '',
  serving_size_g: '',
  basis: '100g',
  category: '',
  energy_kj: '',
  calories_kcal: '',
  carbohydrates_g: '',
  sugars_g: '',
  protein_g: '',
  total_fat_g: '',
  saturated_fat_g: '',
  fibre_g: '',
  sodium_mg: '',
};

function messageFrom(error, fallback) {
  return error.response?.data?.message || fallback;
}

function displayNumber(value, unit) {
  return value == null ? 'Unavailable' : `${value} ${unit}`;
}

export default function ProductScanPage() {
  const navigate = useNavigate();
  const videoRef = useRef(null);
  const [mode, setMode] = useState('barcode');
  const [barcode, setBarcode] = useState('');
  const [barcodeProduct, setBarcodeProduct] = useState(null);
  const [category, setCategory] = useState('');
  const [ocrForm, setOcrForm] = useState(EMPTY_OCR);
  const [recognizedText, setRecognizedText] = useState('');
  const [loading, setLoading] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const findBarcode = useCallback(async (value) => {
    const code = value.trim();
    if (!/^(?:\d{8}|\d{12,14})$/.test(code)) {
      setError('Barcode should contain 8, 12, 13, or 14 digits.');
      return;
    }
    setLoading(true);
    setError('');
    setStatus('');
    setBarcodeProduct(null);
    try {
      const { data } = await lookupBarcode(code);
      setBarcodeProduct(data.product);
      setCategory(data.product.category || 'other');
      setBarcode(code);
      setStatus('Review the product details and package values before saving.');
    } catch (requestError) {
      setError(messageFrom(requestError, 'Barcode lookup failed. Try the label scan instead.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!cameraActive) return undefined;
    let active = true;
    let controls;
    async function startCameraReader() {
      const { BrowserMultiFormatReader } = await import('@zxing/browser');
      if (!active) return;
      const reader = new BrowserMultiFormatReader();
      controls = await reader.decodeFromVideoDevice(undefined, videoRef.current, (result) => {
        if (!result || !active) return;
        active = false;
        controls?.stop();
        setCameraActive(false);
        const scanned = result.getText();
        setBarcode(scanned);
        findBarcode(scanned);
      });
      if (!active) controls.stop();
    }

    startCameraReader().catch(() => {
      if (active) {
        setCameraActive(false);
        setError('Could not access the camera. Allow camera permission or enter the barcode below.');
      }
    });

    return () => {
      active = false;
      controls?.stop();
    };
  }, [cameraActive, findBarcode]);

  async function scanLabel(event) {
    const image = event.target.files?.[0];
    event.target.value = '';
    if (!image) return;
    if (!image.type.startsWith('image/')) {
      setError('Choose an image of the package label.');
      return;
    }
    if (image.size > 12 * 1024 * 1024) {
      setError('Image must be 12 MB or smaller.');
      return;
    }

    setLoading(true);
    setError('');
    setStatus('Reading the label on this device...');
    setProgress(0);
    try {
      const { createWorker } = await import('tesseract.js');
      const worker = await createWorker('eng', 1, {
        logger: (eventData) => {
          if (eventData.status === 'recognizing text') {
            setProgress(Math.round((eventData.progress || 0) * 100));
          }
        },
      });
      try {
        const { data } = await worker.recognize(image);
        if (!data.text.trim()) {
          setError('No label text was recognized. Try a sharper, well-lit photo.');
          setStatus('');
          return;
        }
        const extracted = parseNutritionLabel(data.text);
        setRecognizedText(data.text);
        setOcrForm((current) => ({
          ...EMPTY_OCR,
          name: current.name,
          brand: current.brand,
          barcode: current.barcode,
          category: current.category,
          ...extracted,
        }));
        setStatus('Review the extracted details. Values may need correction if the photo is unclear.');
      } finally {
        await worker.terminate();
      }
    } catch {
      setError('Could not read this image. Try a sharper, well-lit photo of the nutrition panel.');
      setStatus('');
    } finally {
      setLoading(false);
    }
  }

  async function saveBarcodeProduct() {
    if (!category) {
      setError('Choose the matching food category before saving.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const { data } = await importBarcodeProduct({ barcode, category });
      navigate(`/products/${data.product.id}`, { replace: true });
    } catch (requestError) {
      setError(messageFrom(requestError, 'Could not save product. Please try again.'));
    } finally {
      setLoading(false);
    }
  }

  function updateOcr(event) {
    const { name, value } = event.target;
    setOcrForm((current) => ({ ...current, [name]: value }));
    setError('');
  }

  async function saveOcrProduct(event) {
    event.preventDefault();
    if (!ocrForm.name.trim()) {
      setError('Enter the product name so you can find it in your library.');
      return;
    }
    if (!ocrForm.category) {
      setError('Choose a food category before saving.');
      return;
    }
    if (!NUTRIENTS.some(([field]) => ocrForm[field] !== '')) {
      setError('No nutrition facts were detected. Try a clearer label photo.');
      return;
    }
    const servingSize = Number(ocrForm.serving_size_g);
    if (
      ocrForm.basis === 'serving' &&
      (!Number.isFinite(servingSize) || servingSize <= 0)
    ) {
      setError('Enter the serving size in grams to convert per-serving facts to per 100 g.');
      return;
    }

    const facts = Object.fromEntries(
      NUTRIENTS.map(([field, , , maximum]) => {
        if (ocrForm[field] === '') return [field, null];
        const amount = Number(ocrForm[field]);
        const per100 = ocrForm.basis === 'serving'
          ? (amount * 100) / servingSize
          : amount;
        if (!Number.isFinite(per100) || per100 < 0 || per100 > maximum) {
          return [field, NaN];
        }
        return [field, Number(per100.toFixed(2))];
      }),
    );
    if (Object.values(facts).some((value) => Number.isNaN(value))) {
      setError('One or more nutrition values are outside the supported range. Check the scan and serving size.');
      return;
    }
    if (facts.sugars_g != null && facts.carbohydrates_g != null && facts.sugars_g > facts.carbohydrates_g) {
      setError('Extracted sugar is greater than carbohydrates. Check the recognized label values.');
      return;
    }
    if (facts.saturated_fat_g != null && facts.total_fat_g != null && facts.saturated_fat_g > facts.total_fat_g) {
      setError('Extracted saturated fat is greater than total fat. Check the recognized label values.');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const payload = {
        name: ocrForm.name.trim(),
        brand: ocrForm.brand.trim() || null,
        barcode: ocrForm.barcode.trim() || null,
        ingredients: ocrForm.ingredients.trim() || null,
        category: ocrForm.category,
        dietary_tags: [],
        serving_size_g: ocrForm.serving_size_g ? servingSize : null,
        ...facts,
      };
      const { data } = await importOcrProduct(payload);
      navigate(`/products/${data.product.id}`, { replace: true });
    } catch (requestError) {
      setError(messageFrom(requestError, 'Could not save product. Please try again.'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="product-page">
      <header className="dashboard__header">
        <Link className="brand" to="/products" aria-label="Product nutrition search">
          <span className="brand__icon" aria-hidden="true">N</span>
          <span>NutriScan</span>
        </Link>
        <Link className="button button--quiet" to="/products">Cancel</Link>
      </header>

      <section className="product-content product-content--form">
        <div className="product-page__intro">
          <p className="eyebrow">Scan, review, understand</p>
          <h1>Scan a food product</h1>
          <p>Look up a barcode or photograph the package label. NutriScan extracts the information so you do not have to type nutrition facts.</p>
        </div>

        <div className="scan-tabs" role="tablist" aria-label="Choose scan method">
          <button
            aria-selected={mode === 'barcode'}
            className={mode === 'barcode' ? 'is-selected' : ''}
            onClick={() => { setMode('barcode'); setError(''); }}
            role="tab"
            type="button"
          >
            Scan barcode
          </button>
          <button
            aria-selected={mode === 'label'}
            className={mode === 'label' ? 'is-selected' : ''}
            onClick={() => { setMode('label'); setError(''); setCameraActive(false); }}
            role="tab"
            type="button"
          >
            Scan package label
          </button>
        </div>

        {mode === 'barcode' ? (
          <section className="scan-panel" aria-label="Barcode lookup">
            <p className="scan-panel__hint">
              Barcode lookup uses Open Food Facts, a community-maintained product database.
              If your product is missing or incomplete, scan its label instead.
            </p>
            <form
              className="product-search scan-barcode-form"
              onSubmit={(event) => {
                event.preventDefault();
                findBarcode(barcode);
              }}
            >
              <label className="sr-only" htmlFor="barcode-input">Product barcode</label>
              <input
                autoComplete="off"
                id="barcode-input"
                inputMode="numeric"
                maxLength="14"
                onChange={(event) => setBarcode(event.target.value.replace(/\D/g, ''))}
                placeholder="Scan or enter 8–14 barcode digits"
                value={barcode}
              />
              <button className="button button--primary" disabled={loading} type="submit">
                {loading ? 'Looking up...' : 'Look up'}
              </button>
            </form>
            <div className="scan-camera-actions">
              <button
                className="button button--outline"
                disabled={loading || cameraActive}
                onClick={() => { setError(''); setCameraActive(true); }}
                type="button"
              >
                {cameraActive ? 'Camera scanning...' : 'Use camera to scan barcode'}
              </button>
              {cameraActive && (
                <button className="text-link" onClick={() => setCameraActive(false)} type="button">
                  Stop camera
                </button>
              )}
            </div>
            {cameraActive && <video className="barcode-video" muted playsInline ref={videoRef} />}

            {barcodeProduct && (
              <div className="scan-review">
                <div className="scan-review__heading">
                  <div>
                    <p className="eyebrow">Review before saving</p>
                    <h2>{barcodeProduct.name}</h2>
                    <p>{barcodeProduct.brand || 'Brand not listed'} · Barcode {barcodeProduct.barcode}</p>
                  </div>
                  <span className="source-badge">{barcodeProduct.source_label}</span>
                </div>
                <p className="scan-panel__hint">
                  Source: <a href={`https://world.openfoodfacts.org/product/${encodeURIComponent(barcodeProduct.barcode)}`} rel="noreferrer" target="_blank">Open Food Facts (ODbL)</a>
                </p>
                <label className="field scan-category">
                  <span>Food category</span>
                  <select onChange={(event) => setCategory(event.target.value)} value={category}>
                    {CATEGORIES.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </label>
                <h3>Nutrition per 100 g</h3>
                <div className="scan-nutrient-grid">
                  {NUTRIENTS.map(([field, label, unit]) => (
                    <div className="scan-nutrient" key={field}>
                      <span>{label}</span>
                      <strong>{displayNumber(barcodeProduct[field], unit)}</strong>
                    </div>
                  ))}
                </div>
                {barcodeProduct.serving_size_g && (
                  <p className="scan-panel__hint">
                    Database serving: {barcodeProduct.serving_size_g} g. Per-serving amounts will be calculated from the per-100 g values.
                  </p>
                )}
                {barcodeProduct.ingredients && (
                  <div className="scan-ingredients">
                    <h3>Ingredients</h3>
                    <p>{barcodeProduct.ingredients}</p>
                  </div>
                )}
                <p className="result-note">
                  Values and ingredients are community-contributed; some may be incomplete or inaccurate.
                  NutriScan will fetch these barcode details again when you confirm.
                </p>
                <button className="button button--primary entry-submit" disabled={loading} onClick={saveBarcodeProduct} type="button">
                  {loading ? 'Saving product...' : 'Confirm and save product'}
                </button>
              </div>
            )}
          </section>
        ) : (
          <section className="scan-panel" aria-label="Package label OCR">
            <p className="scan-panel__hint">
              Take a close, well-lit photo of the ingredients and nutrition panels. Text recognition
              runs in your browser; the image itself is not uploaded. English text is currently
              recognized best.
            </p>
            <label className="button button--primary scan-upload">
              {loading ? `Reading label... ${progress}%` : 'Take photo or choose label image'}
              <input
                accept="image/*"
                capture="environment"
                disabled={loading}
                onChange={scanLabel}
                type="file"
              />
            </label>
            {loading && <p className="product-state" role="status">Reading text on this device... {progress}%</p>}
            {recognizedText && (
              <details className="recognized-text">
                <summary>Show recognized label text</summary>
                <pre>{recognizedText}</pre>
              </details>
            )}

            {recognizedText && (
              <form className="product-entry-form scan-review" onSubmit={saveOcrProduct} noValidate>
                <div className="scan-review__heading">
                  <div>
                    <p className="eyebrow">Review extracted information</p>
                    <h2>Confirm the package details</h2>
                    <p>OCR can misread small text. Check the values against the photo; you can correct any extraction before saving.</p>
                  </div>
                </div>
                <div className="data-warning" role="note">
                  <strong>Image stays on this device</strong>
                  <span>Only the product details you confirm are sent to NutriScan. OCR data is not independently verified.</span>
                </div>
                <div className="entry-fields entry-fields--identity scan-identity">
                  <label className="field">
                    <span>Product name</span>
                    <input maxLength="160" name="name" onChange={updateOcr} required value={ocrForm.name} />
                  </label>
                  <label className="field">
                    <span>Brand <em>Optional</em></span>
                    <input maxLength="120" name="brand" onChange={updateOcr} value={ocrForm.brand} />
                  </label>
                  <label className="field">
                    <span>Food category</span>
                    <select name="category" onChange={updateOcr} value={ocrForm.category}>
                      <option value="">Select a category</option>
                      {CATEGORIES.map(([value, label]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>Serving size <em>Optional</em></span>
                    <div className="input-with-unit">
                      <input max="5000" min="0.01" name="serving_size_g" onChange={updateOcr} step="0.01" type="number" value={ocrForm.serving_size_g} />
                      <span>g</span>
                    </div>
                  </label>
                  <label className="field">
                    <span>Barcode <em>Optional</em></span>
                    <input inputMode="numeric" maxLength="14" name="barcode" onChange={(event) => setOcrForm((current) => ({ ...current, barcode: event.target.value.replace(/\D/g, '') }))} value={ocrForm.barcode} />
                  </label>
                  <label className="field scan-basis">
                    <span>Nutrition values shown</span>
                    <select name="basis" onChange={updateOcr} value={ocrForm.basis}>
                      <option value="100g">Per 100 g</option>
                      <option value="serving">Per serving</option>
                    </select>
                  </label>
                </div>

                <label className="field scan-ingredients-field">
                  <span>Ingredients <em>Optional</em></span>
                  <textarea maxLength="10000" name="ingredients" onChange={updateOcr} rows="4" value={ocrForm.ingredients} />
                </label>

                <h3 className="entry-section-title">Recognized nutrition values</h3>
                <p className="entry-help">
                  {ocrForm.basis === 'serving'
                    ? 'Confirm the serving size above. Values will be converted to per 100 g before saving.'
                    : 'Values are saved per 100 g. Missing values remain unavailable, not zero.'}
                </p>
                <div className="entry-fields entry-fields--nutrients">
                  {NUTRIENTS.map(([name, label, unit, max, step]) => (
                    <label className="field" key={name}>
                      <span>{label} <small>({unit})</small></span>
                      <input max={max} min="0" name={name} onChange={updateOcr} step={step} type="number" value={ocrForm[name]} />
                    </label>
                  ))}
                </div>
                {error && <p className="form-message form-message--error" role="alert">{error}</p>}
                <button className="button button--primary entry-submit" disabled={loading} type="submit">
                  {loading ? 'Saving product...' : 'Confirm and save nutrition'}
                </button>
              </form>
            )}
          </section>
        )}

        {error && <p className="form-message form-message--error" role="alert">{error}</p>}
        {status && <p className="form-message form-message--success" role="status">{status}</p>}
        <p className="scan-manual-link">
          Scanner not available? <Link className="text-link" to="/products/manual">Enter product details manually</Link>
        </p>
      </section>
    </main>
  );
}
