# NutriScan Project Status

## Project phases

| Phase | Scope | Status |
|---|---|---|
| 1. Project foundation | Frontend/backend structure, runnable app shells, health endpoint, project conventions | Complete |
| 2. Database foundation | MySQL configuration/schema and SQLAlchemy models | Complete and verified against local MySQL |
| 3. Registration and authentication | Signup/login, bcrypt, JWT and protected routes | Complete and tested against local MySQL |
| 4. Health profile and BMI | Profile setup/editing, BMI, calorie estimates, dietary preferences and goals | Complete and tested against local MySQL |
| 5. Product nutrition analysis | Product search, nutrition entry/retrieval, per-100 g and serving analysis | Complete and tested against local MySQL |
| 6. Healthier product recommendations | Goal-aware alternatives, category matching, dietary suitability and comparisons | Complete and tested against local MySQL |
| 7. Product history and watchlist | Analysis history, favourites, watchlists, comparison | Complete and tested against local MySQL |
| Final integration and quality assurance | MySQL integration journey, frontend build, security review, setup documentation | Complete; visual browser checks were not run |
| Scan-first product capture | Barcode lookup, on-device label OCR, reviewed imports, per-gram calculations | Implemented; automated checks run, live camera/photo device verification remains |

## Current foundation

- React + Vite frontend is under `frontend/`.
- Flask backend is under `backend/`.
- `GET /api/health` is the initial backend smoke-test endpoint.
- MySQL configuration, SQLAlchemy models, and database initialization scripts are under `backend/`.
- `GET /api/health/database` and `backend/scripts/init_db.py --check-only` check database connectivity.
- Local credentials are configured in the ignored `backend/.env`; never commit this file.
- MySQL initialization created `users`, `health_profiles`, and `products`; their foreign keys were verified.
- Verified against the actual MySQL server: `GET /api/health/database` returned HTTP 200 on 2026-11-12.
- Registration and login APIs are under `backend/app/auth.py`; authenticated account lookup is `GET /api/auth/me`.
- React signup/login pages use the shared Axios client and authentication context; JWTs are kept in session storage.
- MySQL-backed auth integration test: registration, bcrypt password storage, duplicate email rejection, login, invalid credentials, and protected route checks passed.
- Profile API is available at `GET/PUT /api/profile` and derives ownership from the authenticated JWT.
- `backend/scripts/migrate_health_profile.py` safely adds age, gender, and dietary-preference columns to the existing MySQL table.
- Health profile integration tests against MySQL passed for profile creation/update/persistence, per-user isolation, validation, BMI adult/minor handling, and calorie estimates.
- Adult calorie estimates use the Mifflin-St Jeor formula as a range; calorie estimates are withheld for users under 18. Adult BMI classifications and cutoffs are also withheld for users under 18.
- Products are stored in the `products` MySQL table, linked to their owner. `backend/scripts/init_products.py` initializes and verifies this table without duplicating existing tables.
- Authenticated product APIs support name search, nutrition entry, and detail retrieval at `/api/products`; users can access only their own entries.
- Product facts are stored per 100 g; per-serving values are derived from the entered serving size. Manual entry is labeled user-entered, barcode data is labeled community-sourced, and OCR imports are labeled user-reviewed but unverified. No sample values are presented as verified.
- Product analysis shows nutrition indicators and an explanatory macro-energy chart; it does not assign an opaque nutrition score.
- Product MySQL integration tests passed for persistence, search, serving calculations, validation, and owner isolation. Existing authentication and health-profile integration tests also passed.
- Product recommendations use the authenticated user's own products and health profile. Exact, explicitly selected categories are required; selected dietary preferences must all match product suitability tags.
- Explainable goal rules require a measured primary improvement (lower calories for weight loss, higher protein for muscle building, higher calories for weight gain, and lower sugar/saturated fat/sodium for maintenance or general wellness). Results are ordered by primary improvements and then measured trade-offs; the API explains this ordering.
- The product table migration adds category and dietary tags and allows unavailable nutrition facts to remain `NULL`. Comparison results preserve unavailable values instead of treating them as zero.
- Recommendation pages show goal-specific reasons and per-100 g side-by-side nutrient differences. Products remain explicitly labeled as user-entered and not independently verified; no recommendations are invented when none qualify.
- Recommendation MySQL tests passed for category matching, goal changes, dietary filtering, missing nutrient handling, no-result cases, and owner isolation. Product, authentication, and health-profile MySQL tests also passed.
- Frontend production build passed with recommendation and product-detail routes code-split.
- Product analysis history and watchlist are stored in `product_analysis_history` and `product_watchlist`, linked to users and products with product-deletion snapshots and `ON DELETE SET NULL`.
- Opening a product detail records a timestamped per-user analysis snapshot. History supports search, category filtering, and newest/oldest ordering.
- The watchlist supports add/remove, unique user/product entries, search and category sorting. Saved products can be compared side-by-side; users can only access their own history, watchlist entries, and products.
- Product edits do not mutate saved snapshots. Deleting a product retains the history/watchlist snapshot and removes the live product reference; deleted watchlist records remain removable.
- Activity tables are initialized idempotently by `backend/scripts/init_products.py`, reusing the existing product schema.
- MySQL integration tests passed for history timestamps, watchlist operations and duplicate prevention, search/filter/order, comparison, user isolation, edits, and product deletion snapshot preservation. Existing product, recommendation, auth, and profile tests passed.
- Frontend production build passed with activity and comparison pages.
- Fixed the missing `BrowserRouter` provider that prevented routed React screens from rendering.
- Added global handling for expired-session 401 responses; public login and registration failures no longer trigger the expired-session sign-out behavior.
- `README.md` documents teammate setup with a local MySQL database, private environment configuration, initialization scripts, startup, and verification commands.
- Product capture now starts with barcode lookup against Open Food Facts and offers on-device OCR for package labels as a fallback. Barcode responses include available nutrients per 100 g, product name/brand, serving size, and ingredient text; missing data remains unavailable.
- Barcode lookup/import is authenticated, uses server-side requests with validation and timeouts, and saves records under the current user only after review. Imported source metadata identifies community data that may be incomplete or unverified.
- Label OCR uses Tesseract.js in the browser; package images are not sent to Flask or Open Food Facts. Recognized facts and ingredient text are reviewed/corrected before import, with OCR provenance recorded. OCR values can be converted from a confirmed per-serving basis to per 100 g.
- Product records preserve barcode and ingredient text. The product detail page displays ingredients and calculates nutrition for the declared serving or another user-selected gram amount.
- `backend/scripts/init_products.py` adds nullable barcode and ingredient columns to existing MySQL product tables without recreating the table.
- Added mocked MySQL integration coverage for barcode data normalization/import, source labels, sodium conversion, OCR import, and invalid barcode handling; added Node tests for OCR extraction and unavailable values.

## Final integration and quality assurance

- Re-ran the three MySQL initialization/migration scripts successfully; they connected to the configured MySQL server and reported the schema ready.
- `GET /api/health/database` returned HTTP 200 from the Flask test client against the configured MySQL connection.
- Ran `python -m unittest discover -s tests -v` in `backend/`: all 10 MySQL integration tests passed, including registration through product comparison, authentication and ownership isolation, profile calculations/persistence, product validation, barcode/OCR import, recommendation rules, history, watchlist, and deletion snapshots.
- Ran `npm test` in `frontend/`: both OCR parser tests passed. `npm run build` passed with the scan and OCR dependencies code-split.
- Security review reported no vulnerabilities in the reviewed code. The implemented API uses JWT-protected routes and owner-scoped data access; SQLAlchemy expression queries and configured CORS restrictions were also reviewed.
- `npm audit` and `npm ci --dry-run --ignore-scripts` passed with 0 dependency vulnerabilities and a valid clean-install lockfile. Updated React Router to its patched 7.18.5 release after npm reported two moderate advisories in the existing v6 dependency.
- Verified `.gitignore` rules cover `.env`, `.env.*` (while retaining `.env.example`), virtual environments, and `node_modules`.
- Browser-based end-to-end and desktop/tablet/mobile visual checks were not run because browser automation was declined. CSS includes responsive breakpoints, but visual responsiveness is not confirmed.
- Git tracking/staging status could not be inspected: Git is unavailable in this environment and the workspace is not a Git repository. The ignore rules were verified from `.gitignore`; a repository-level secret scan was therefore not performed.
- Ran a live authenticated lookup for a public barcode against Open Food Facts: lookup returned HTTP 200; confirmed import persisted to MySQL and product retrieval returned HTTP 200. The temporary test account and product were removed afterward.
- The running Vite scan route and Flask MySQL health endpoint both returned HTTP 200 after restarting the application.
- Camera scanning and image OCR were not exercised with a physical device or browser because browser automation was previously declined; parser logic, build output, routes, and backend imports were tested.

## Known limitations and remaining work

- The separate profile-aware nutrition-insights feature is not implemented. Existing recommendations use transparent, goal-specific comparisons; this final QA did not add feature scope.
- Product reformulation tracking and update notifications are not implemented.
- Product facts come from user entry, a community database, or OCR and are not independently verified; recommendations are informational and not medical advice.
- Open Food Facts is community-maintained and may lack or contain incorrect product facts. OCR is English-focused, imperfect, and requires package review. Camera access requires browser permission and a secure context (localhost or HTTPS); OCR downloads its browser engine and language assets on first use.
