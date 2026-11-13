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

The scripts connect using the credentials in `backend\.env`. In Workbench, refresh the `nutriscan` schema and inspect the `users`, `health_profiles`, `products`, `product_analysis_history`, and `product_watchlist` tables.

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

- Barcode scanning looks up public product records using the barcode at Open Food Facts. Only the barcode is sent to that service; product records are community-contributed, may be incomplete, and should be checked against the package. Product data is provided by [Open Food Facts](https://world.openfoodfacts.org/) under the Open Database License (ODbL). NutriScan attributes this source in the product details and does not claim independent verification.
- Package-label photos are processed with Tesseract.js in the browser (English OCR). The image is not uploaded; OCR engine and English language assets are downloaded by the browser on first use. Review and correct extracted values before saving.
- If an OCR scan finds salt but no sodium value, it estimates sodium as 40% of the salt amount; verify this estimate against the package or manufacturer information.
- Nutrition is stored per 100 g, with values calculated for the recorded serving size or another gram amount. Missing values remain unavailable rather than being treated as zero.
- Manual product entry remains available as a fallback and is labelled user-entered and not independently verified.

Recommendations only compare products saved by the signed-in user, require a matching category, and use the user's recorded health goal and dietary preferences. Product information may be inaccurate and is not medical advice.

Product reformulation tracking and update notifications are not implemented.
