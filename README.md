# NutriScan

NutriScan is a React/Vite frontend with a Flask API and a MySQL database. Product nutrition and dietary classifications entered by users are labelled as unverified; the app does not fetch or certify manufacturer data.

## Requirements

- Node.js 20+ and npm
- Python 3.10+
- MySQL Server 8.x and MySQL Workbench

## 1. Create your local database

Start MySQL Server, connect to your local instance in Workbench, open a SQL tab, and execute:

```sql
CREATE DATABASE IF NOT EXISTS nutriscan
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

Use your own MySQL account. Avoid using an administrator account for a shared deployment; create a dedicated local application user and grant it access to the `nutriscan` database if appropriate for your setup.

## 2. Configure the Flask backend

From the project root, copy the example environment file:

```powershell
Copy-Item backend\.env.example backend\.env
```

Edit `backend\.env` locally. Set `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, and `MYSQL_PASSWORD` for your MySQL instance. Replace `JWT_SECRET_KEY` with a unique, random secret for this machine. For example, generate one into the clipboard without displaying it in the terminal:

```powershell
Set-Clipboard -Value (python -c "import secrets; print(secrets.token_urlsafe(48))")
```

Paste the generated value into your local `backend\.env`, then clear the clipboard. Never commit or share this file. The repository ignores `.env` and `.env.*` files while keeping `.env.example` tracked.

Create and install the backend virtual environment:

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Initialize the existing tables and add any schema columns needed by the current application. These scripts are idempotent and do not create duplicate tables:

```powershell
.\.venv\Scripts\python.exe scripts\init_db.py
.\.venv\Scripts\python.exe scripts\migrate_health_profile.py
.\.venv\Scripts\python.exe scripts\init_products.py
```

The scripts connect using the credentials in `backend\.env`. In Workbench, refresh the `nutriscan` schema and inspect the `users`, `health_profiles`, `products`, `product_analysis_history`, `product_watchlist`, `product_ingredient_analyses`, and `product_food_claim_analyses` tables.

## 3. Start the application

Open two terminals from the project root.

Terminal 1 — backend:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe run.py
```

The Flask API listens at `http://localhost:5000`. Check database connectivity at `http://localhost:5000/api/health/database`.

Terminal 2 — frontend:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open the Vite URL printed in the terminal (normally `http://localhost:5173`). Vite proxies `/api` requests to the Flask API.

## 4. Run verification

With your MySQL server running and `backend\.env` configured, run the integration tests. They use the configured MySQL database and create temporary records that are removed after the tests:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Build the frontend:

```powershell
Set-Location frontend
npm ci
npm run build
```

## Product data and recommendations

Product capture is scan-first:

- Barcode scanning supports EAN-13, EAN-8, and UPC-A using the browser camera or manual barcode entry. Camera access requires permission and a secure context (localhost or HTTPS). The Flask server looks up the scanned barcode at Open Food Facts; only the barcode is sent to that service. Available name, brand, image, category, ingredients, serving size, and per-100 g nutrients populate the editable confirmation form. Missing facts stay unavailable, and incomplete product records can be saved with a package-confirmed name and no nutrition values. Product records are community-contributed and should be checked against the package. Data is provided by [Open Food Facts](https://world.openfoodfacts.org/) under the Open Database License (ODbL); NutriScan labels the source and does not claim independent verification.
- The barcode review step allows corrections before saving, preserves the original scanned barcode and source attribution, and opens an existing product when the same user scans a barcode already in their library. The database enforces a per-user barcode uniqueness constraint where existing data permits it; the idempotent products initialization script reports pre-existing duplicates rather than deleting records.
- Package-label photos are processed with Tesseract.js in the browser (English OCR). The image is not uploaded; OCR engine and English language assets are downloaded by the browser on first use. Review and correct extracted values before saving.
- The package OCR text is saved with the product (up to 20,000 characters) for the claim-review workflow. The package image remains in the browser and is not uploaded.
- Ingredient analysis is available from each saved product and reuses the saved OCR, Open Food Facts, or user-entered ingredient list. Users can edit the text and save a timestamped analysis. A local NLP matcher recognizes a limited, reviewed set of ingredient names and additive codes, links relevant FDA references, and checks known matches against the profile's dietary preferences. Unsupported names remain explicitly unclassified; unmatched health effects are not generated.
- The ingredient analyzer intentionally does not call a generative AI service: the current backend has no configured, evidence-grounded model provider, and free-form health claims could be unreliable. It highlights U.S. FDA major-allergen references and the FDA's aspartame/PKU guidance where matched, but is not a medical or allergy-safety assessment. Health goals are shown only as context and are not inferred from ingredient names.
- Ingredient history comparison reuses the timestamped analysis snapshots. From a product or ingredient-analysis page, compare two saved analyses of that same product to see added, removed, unchanged, reordered, and differently classified/explained ingredients. Matching normalizes case, whitespace, Unicode accents, punctuation, and common additive-code formatting while retaining both original label text and saved analysis results; previous records are never recalculated or overwritten. A non-foreign-key product identity snapshot preserves grouping after product deletion. Existing analyses whose products were already deleted before this migration have no recoverable identity and are deliberately not grouped by name alone.
- If an OCR scan finds salt but no sodium value, it estimates sodium as 40% of the salt amount; verify this estimate against the package or manufacturer information.
- Nutrition is stored per 100 g, with values calculated for the recorded serving size or another gram amount. Missing values remain unavailable rather than being treated as zero.
- Manual product entry remains available as a fallback and is labelled user-entered and not independently verified.

Recommendations only compare products saved by the signed-in user, require a matching category, and use the user's recorded health goal and dietary preferences. Product information may be inaccurate and is not medical advice.

Product reformulation tracking and update notifications are not implemented. Ingredient reference coverage is limited and may not recognize regional names, complex formulations, or all sub-ingredients. Physical camera permission/device behavior has not been validated on actual desktop or mobile hardware.

## Historical ingredient comparison

The `product_ingredient_analyses` table remains the source of historical records; no duplicate history table is created. `backend/scripts/init_products.py` adds the nullable `product_identity_snapshot` column and its index, backfills it for analyses still linked to a product, and is safe to rerun. Newly saved analyses include this identity so their snapshots can still be compared after the live product is deleted. Analyses for products deleted before the migration retain their text and results, but cannot be safely associated with other records and are not comparable.

The authenticated endpoints are `GET /api/products/ingredients/history` and `POST /api/products/ingredients/compare`. The comparison endpoint requires two distinct, chronologically ordered analysis IDs belonging to the authenticated user and the same product identity. Comparison reads only the stored JSON snapshots and does not modify them.

Phase 10 verification: MySQL schema initialization passed; the backend suite passed all 23 tests (including MySQL history, deletion preservation, ownership, validation, normalization, ordering, and saved classification/explanation comparisons); `npm test` passed all 10 frontend tests; `npm run build` passed; and `git diff --check` passed.

## Phase 11 food packaging claims

The product detail page links to a packaging-claims review. It can start with the saved raw OCR text or accept claim text entered or edited by the user. The analyzer recognizes selected nutrition, dietary, certification, marketing, and health-related phrases; unknown manually supplied phrases are reported as unclassified and unable to verify. It does not treat every marketing phrase as a regulated nutrition claim.

Claims are compared with the saved product's nutrition values and ingredients. For sugar-free, low-sugar, low-fat, and fat-free claims, the preliminary numeric comparison uses the referenced FSSAI 2018 Advertising and Claims Regulations compendium (14 Dec 2022), and only when a per-100 g value and a solid-food category are available. Beverage claims remain unverifiable because NutriScan stores nutrients per 100 g and does not infer a 100 ml conversion. Other claim types are shown as unverifiable unless the current product data and a reliable applicable criterion support a limited consistency check. An ingredient match can indicate a potential inconsistency, never a legal finding. No nutrition values are filled in when missing.

The saved product OCR text is optional and limited to 20,000 characters. `backend/scripts/init_products.py` adds the nullable `products.packaging_text` column and creates `product_food_claim_analyses`. Claim snapshots store the input text, product evidence, source label, analysis result, user/product identifiers, and timestamp. The product reference uses `ON DELETE SET NULL`; a non-foreign-key product identity and name snapshot preserve access to records after product deletion. Authenticated endpoints are `POST /api/products/<product_id>/claims/analyze` and `GET /api/products/claims/history` (optionally filtered by `product_id`); both scope all records to the current user.

Each result is labelled “Appears supported,” “Potentially inconsistent,” or “Unable to verify,” with evidence and explanation. The UI clearly identifies saved product facts as user-entered, OCR-extracted, or community-sourced and not independently verified. Claim checks are preliminary product-data comparisons, not official FSSAI verification, legal compliance findings, or medical advice.

Known limitations: product records do not include cholesterol, so cholesterol claims cannot be checked; the analyzer does not currently apply thresholds for high/source-of-protein, high-fibre, low-sodium, low-carbohydrate, reduced-sugar, or most certification/marketing claims. It also cannot confirm ingredient-list completeness, organic certification, gluten cross-contact, product category correctness, or package authenticity. OCR claim text should be reviewed before analysis. The recognized phrase set is intentionally limited, and no AI service or external claim-verification API is used.

Phase 11 verification against the configured MySQL database: `scripts/init_products.py` passed and all 31 backend tests passed, including claim detection, supported/inconsistent/unverifiable results, missing values, nutrition units, ingredient evidence, personalization, persistence, owner isolation, validation, and product deletion preservation. `npm test` passed all 10 frontend tests, `npm run build` passed, and `git diff --check` passed.
