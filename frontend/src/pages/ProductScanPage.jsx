import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  importBarcodeProduct,
  importOcrProduct,
  lookupBarcode,
} from '../api/products.js';
import ProductReviewForm from '../components/ProductReviewForm.jsx';
import { cameraErrorMessage, isSupportedBarcode } from '../utils/barcodeScanner.js';
import { parseNutritionLabel } from '../utils/labelParser.js';

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

export default function ProductScanPage() {
  const navigate = useNavigate();
  const videoRef = useRef(null);
  const [mode, setMode] = useState('barcode');
  const [barcode, setBarcode] = useState('');
  const [existingBarcodeProduct, setExistingBarcodeProduct] = useState(null);
  const [ocrForm, setOcrForm] = useState(EMPTY_OCR);
  const [reviewSource, setReviewSource] = useState(null);
  const [reviewMetadata, setReviewMetadata] = useState({});
  const [recognizedText, setRecognizedText] = useState('');
  const [ocrWarnings, setOcrWarnings] = useState([]);
  const [uncertainFields, setUncertainFields] = useState([]);
  const [reviewConfirmed, setReviewConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const findBarcode = useCallback(async (value) => {
    const code = value.trim();
    if (!isSupportedBarcode(code)) {
      setError('Enter an EAN-13, EAN-8, or UPC-A barcode (13, 8, or 12 digits).');
      return;
    }
    setLoading(true);
    setError('');
    setStatus('');
    setReviewSource(null);
    setExistingBarcodeProduct(null);
    try {
      const { data } = await lookupBarcode(code);
      if (data.existing_product) {
        setExistingBarcodeProduct(data.existing_product);
        setBarcode(code);
        setStatus('This barcode is already saved in your product library.');
        return;
      }
      const product = data.product;
      const formValues = {
        ...EMPTY_OCR,
        ...product,
        serving_size_g: product.serving_size_g == null ? '' : String(product.serving_size_g),
        basis: '100g',
        ...Object.fromEntries(
          NUTRIENTS.map(([field]) => [
            field,
            product[field] == null ? '' : String(product[field]),
          ]),
        ),
      };
      const missing = [];
      const uncertain = [];
      for (const [field, label] of [
        ['name', 'Product name'],
        ['brand', 'Brand'],
        ['category', 'Category'],
        ['ingredients', 'Ingredients'],
        ['serving_size_g', 'Serving size'],
        ...NUTRIENTS.map(([field, label]) => [field, label]),
      ]) {
        if (formValues[field] === '' || formValues[field] == null) {
          missing.push(`${label} is not available in Open Food Facts.`);
          uncertain.push(field);
        }
      }
      if (formValues.category === 'other') {
        missing.push('Category could not be matched confidently; choose the closest category.');
        uncertain.push('category');
      }
      const servingSize = Number(formValues.serving_size_g);
      if (formValues.serving_size_g !== '' && (servingSize < 1 || servingSize > 1000)) {
        missing.push('Serving size looks unusual; verify it against the package.');
        uncertain.push('serving_size_g');
      }
      setOcrForm(formValues);
      setReviewSource('open_food_facts');
      setReviewMetadata({
        sourceLabel: product.source_label,
        imageUrl: product.image_url,
      });
      setOcrWarnings(missing);
      setUncertainFields(uncertain);
      setReviewConfirmed(missing.length === 0);
      setBarcode(code);
      setStatus('Product details were found. Review and edit the imported information before saving.');
    } catch (requestError) {
      setError(requestError.response?.data?.message
        || 'Could not reach the product database. Check your connection and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!cameraActive) return undefined;
    let active = true;
    let controls;
    async function startCameraReader() {
      if (!window.isSecureContext) {
        setCameraActive(false);
        setError(cameraErrorMessage('SecurityError'));
        return;
      }
      const { BarcodeFormat, BrowserMultiFormatReader } = await import('@zxing/browser');
      if (!active) return;
      const reader = new BrowserMultiFormatReader();
      reader.possibleFormats = [
        BarcodeFormat.EAN_13,
        BarcodeFormat.EAN_8,
        BarcodeFormat.UPC_A,
      ];
      controls = await reader.decodeFromVideoDevice(undefined, videoRef.current, (result) => {
        if (!result || !active) return;
        const code = result.getText();
        const format = BarcodeFormat[result.getBarcodeFormat()];
        if (!isSupportedBarcode(code, format)) {
          setError('This barcode format is not supported. Use EAN-13, EAN-8, or UPC-A.');
          return;
        }
        active = false;
        controls?.stop();
        setCameraActive(false);
        setBarcode(code);
        findBarcode(code);
      });
      if (!active) controls.stop();
    }

    startCameraReader().catch((cameraError) => {
      if (active) {
        setCameraActive(false);
        setError(cameraErrorMessage(cameraError.name));
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
        const extracted = parseNutritionLabel(data.text, { confidence: data.confidence });
        const {
          warnings,
          uncertainFields: uncertain,
          ...formValues
        } = extracted;
        setRecognizedText(data.text);
        setOcrForm({
          ...EMPTY_OCR,
          ...formValues,
        });
        setReviewSource('label_ocr');
        setReviewMetadata({
          sourceLabel: 'OCR-extracted from package; user-reviewed, not independently verified',
          imageUrl: null,
        });
        setOcrWarnings(warnings);
        setUncertainFields(uncertain);
        setReviewConfirmed(false);
        setStatus('Extracted fields have been populated. Review highlighted items and confirm before saving.');
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

  function updateOcr(event) {
    const { name, value } = event.target;
    setOcrForm((current) => ({ ...current, [name]: value }));
    setReviewConfirmed(false);
    setError('');
  }

  async function saveProduct(event) {
    event.preventDefault();
    if (!ocrForm.name.trim()) {
      setError('Enter the product name so you can find it in your library.');
      return;
    }
    if (!ocrForm.category) {
      setError('Choose a food category before saving.');
      return;
    }
    if (ocrForm.brand.length > 120) {
      setError('Brand must be at most 120 characters.');
      return;
    }
    if (reviewSource === 'label_ocr' && !NUTRIENTS.some(([field]) => ocrForm[field] !== '')) {
      setError('No nutrition facts were detected. Try a clearer label photo.');
      return;
    }
    const servingSize = ocrForm.serving_size_g === ''
      ? null
      : Number(ocrForm.serving_size_g);
    if (servingSize !== null && (
      !Number.isFinite(servingSize)
      || servingSize <= 0
      || servingSize > 5000
    )) {
      setError('Serving size must be greater than 0 and no more than 5000 g.');
      return;
    }
    if (
      ocrForm.basis === 'serving' &&
      (servingSize === null || servingSize <= 0)
    ) {
      setError('Enter the serving size in grams to convert per-serving facts to per 100 g.');
      return;
    }
    if (servingSize !== null && (servingSize < 1 || servingSize > 1000)
      && !uncertainFields.includes('serving_size_g')) {
      setUncertainFields((current) => [...current, 'serving_size_g']);
      setOcrWarnings((current) => [
        ...current,
        'Serving size looks unusual; verify it against the package.',
      ]);
      setReviewConfirmed(false);
      setError('Serving size looks unusual. Verify the amount, then confirm the review checkbox.');
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
    if (ocrWarnings.length > 0 && !reviewConfirmed) {
      setError('Review the highlighted scan results and confirm the review checkbox before saving.');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const payload = {
        name: ocrForm.name.trim(),
        brand: ocrForm.brand.trim() || null,
        barcode: reviewSource === 'open_food_facts'
          ? barcode
          : ocrForm.barcode.trim() || null,
        ingredients: ocrForm.ingredients.trim() || null,
        packaging_text: reviewSource === 'label_ocr'
          ? recognizedText.slice(0, 20000)
          : null,
        image_url: reviewSource === 'open_food_facts' ? reviewMetadata.imageUrl : null,
        category: ocrForm.category,
        dietary_tags: [],
        serving_size_g: servingSize,
        review_confirmed: reviewConfirmed,
        ...facts,
      };
      const { data } = reviewSource === 'open_food_facts'
        ? await importBarcodeProduct({
          barcode,
          category: ocrForm.category,
          reviewed_product: payload,
        })
        : await importOcrProduct(payload);
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
            onClick={() => { setMode('barcode'); setReviewSource(null); setError(''); }}
            role="tab"
            type="button"
          >
            Scan barcode
          </button>
          <button
            aria-selected={mode === 'label'}
            className={mode === 'label' ? 'is-selected' : ''}
            onClick={() => { setMode('label'); setReviewSource(null); setError(''); setCameraActive(false); }}
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
                onChange={(event) => {
                  setBarcode(event.target.value.replace(/\D/g, ''));
                  setExistingBarcodeProduct(null);
                  setReviewSource(null);
                  setStatus('');
                }}
                placeholder="Scan or enter EAN-13, EAN-8, or UPC-A"
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

            {existingBarcodeProduct && (
              <div className="product-state product-state--empty">
                <h2>Already in your library</h2>
                <p>{existingBarcodeProduct.name}{existingBarcodeProduct.brand ? ` · ${existingBarcodeProduct.brand}` : ''}</p>
                <button
                  className="button button--primary"
                  onClick={() => navigate(`/products/${existingBarcodeProduct.id}`)}
                  type="button"
                >
                  Open saved product
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

          </section>
        )}

        {reviewSource && (
          <>
            {reviewSource === 'open_food_facts' && (
              <p className="scan-panel__hint">
                Source: <a href={`https://world.openfoodfacts.org/product/${encodeURIComponent(barcode)}`} rel="noreferrer" target="_blank">Open Food Facts (ODbL)</a>
              </p>
            )}
            <ProductReviewForm
              error={error}
              form={ocrForm}
              imageUrl={reviewMetadata.imageUrl}
              loading={loading}
              onChange={updateOcr}
              onReviewConfirmed={setReviewConfirmed}
              onSubmit={saveProduct}
              reviewConfirmed={reviewConfirmed}
              sourceLabel={reviewMetadata.sourceLabel}
              sourceType={reviewSource}
              uncertainFields={uncertainFields}
              warnings={ocrWarnings}
            />
          </>
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
