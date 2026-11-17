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
| 8. Barcode scanning and product identification | ZXing camera/manual scan, Open Food Facts lookup, editable import confirmation | Implemented and tested; physical camera operation remains unverified |
| 9. Ingredient analysis | Ingredient parsing, reference-matched explanations, dietary insights, persisted results | Complete and tested against local MySQL |
| 10. Historical ingredient comparison | Compare saved ingredient-analysis snapshots with user/product isolation | Complete and tested against local MySQL |
| 11. Misleading food claims detection | Preliminary, evidence-based packaging claim checks and saved analysis history | Complete; verified against local MySQL |
| Final integration and quality assurance | MySQL integration journey, frontend build, security review, setup documentation | Complete; visual browser checks were not run |
| Scan-first product capture | Barcode lookup, on-device label OCR, reviewed imports, per-gram calculations | Implemented; automated checks run, live camera/photo device verification remains |
| Indian catalog extension 1. Dataset contract and audit | CSV mapping, data-quality rules, duplicate strategy, and separate catalog design | Complete; read-only audit |
| Indian catalog extension 2. Safe catalog and importer | Dedicated MySQL table and idempotent, transactional dataset import | Complete; verified against local MySQL |
| Indian catalog extension 3. Flask catalog API | Authenticated catalog listing, detail, category, and nutrition-filter endpoints | Implemented; MySQL smoke-tested |
| Indian catalog extension 4. Comparison and alternatives | Serving-aware comparison and transparent rules-based alternatives | Complete; verified against local MySQL |
| Indian catalog extension 5. React catalog integration | Protected catalog browsing, search, filters, details, comparisons, and alternatives | Complete; frontend tests and production build passed |

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
- Product records preserve barcode, ingredients, and optional Open Food Facts package image URLs. Product details display ingredients and calculate nutrition for the declared serving or another user-selected gram amount.
- Package OCR text is optionally preserved on its owner-scoped product record, capped at 20,000 characters, for manual review and claim analysis; package images remain local to the browser.
- `product_ingredient_analyses` stores user-owned ingredient text, reference-matched results, a product-name snapshot, and analysis timestamps; `backend/scripts/init_products.py` creates and verifies the table and its user/product foreign keys.
- `backend/scripts/init_products.py` adds nullable barcode, ingredient, and image columns and a per-user unique barcode index to existing MySQL product tables without recreating the table; it warns and leaves existing duplicate rows untouched if they prevent index creation.
- Added mocked MySQL integration coverage for barcode data normalization/import, source labels, sodium conversion, OCR import, and invalid barcode handling; added Node tests for OCR extraction and unavailable values.
- Improved package OCR extraction to auto-fill explicit or clearly positioned product names, explicitly labelled brands, serving sizes, ingredient text, category suggestions, and readable nutrition values. Ambiguous identity/category guesses remain visibly uncertain rather than being presented as verified.
- OCR now surfaces missing and low-confidence fields, suspicious nutrition values, mixed per-serving/per-100 g bases, implausible serving weights, and inconsistent nutrition facts. Per-serving amounts are normalized only when a valid serving weight is present; missing values remain blank.
- OCR confirmation requires explicit review when uncertain fields are present. Users can edit any detected value; suspicious serving sizes also require a review confirmation at the authenticated API.
- Fixed OCR product creation with an empty optional brand: `null` is accepted and saved as no brand rather than triggering the length validation error.
- Confirmed OCR behavior is extraction-only: values absent from the printed package are not predicted. For labels with one `Per 100 g` heading and a row value without a repeated unit (for example sugar `0`), the parser extracts the printed value and flags the implied unit for review. It does not derive category from unrelated ingredient/use text.
- Added a parser regression case modeled on the provided cocoa powder package: extracts “COCO POWDER”, the marketed-by company as a low-confidence brand candidate, ingredient section only, a low-confidence “other” category suggestion, calories, fats, sugar, carbohydrate, salt-derived sodium, and protein; missing fibre and kJ remain unavailable.

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
- Follow-up OCR tests cover automatic identity/category extraction, the provided label layout, missing fields, low OCR confidence, mixed bases, suspicious nutrient/serving values, editable review confirmation, empty optional brand persistence, and invalid serving-size rejection (8 frontend parser tests and 10 backend MySQL tests passed).

## Phase 8 barcode scanning and product identification

- Added a separate camera/manual barcode option alongside the existing on-device OCR flow. ZXing is restricted to EAN-13, EAN-8, and UPC-A; decoded formats and digit lengths are validated before lookup.
- Camera startup now identifies permission denial, missing devices, busy/unreadable cameras, and insecure contexts with actionable messages. Barcode lookups distinguish not-found, incomplete response, and network errors.
- Barcode lookup returns Open Food Facts name, brand, safe HTTPS product image, category suggestion, ingredients, serving size, and available nutrition normalized per 100 g. Missing values remain blank; incomplete records may be saved after the user supplies a name, even if nutrition is unavailable.
- Barcode results and OCR extraction use the shared editable product review form. Imported values retain source provenance, and barcode imports preserve the scanned code. Scanning a saved barcode opens the user's existing product; the MySQL schema enforces per-user barcode uniqueness when existing data permits.
- `backend/scripts/init_products.py` adds `image_url` and creates the composite unique barcode index idempotently; if legacy duplicate barcode rows exist, it logs a warning rather than removing data.
- Validation run for this phase: `npm test` passed (10 tests), `npm run build` passed, the product MySQL initialization script passed, and `python -m unittest discover -s tests -v` passed all 10 MySQL integration tests. Added coverage for supported/invalid formats, camera error mapping, successful/not-found/incomplete/network-failed provider responses, reviewed field overrides, image mapping, duplicate imports, and per-user barcode isolation.
- Open Food Facts requests were mocked in the integration tests; no live provider lookup was performed in this phase. Camera permissions, actual camera hardware, and desktop/mobile visual behavior were not physically exercised.

## Phase 9 ingredient analysis

- Added ingredient analysis from the product details page. Saved OCR, Open Food Facts, or user-entered ingredient text is prefilled; users can edit the list and save each analysis without changing the source product record.
- Implemented local NLP-style parsing and normalization for comma/semicolon-separated lists and parenthetical sub-ingredients. A curated reference matcher classifies supported ingredients and additives, links relevant FDA pages for additive functions, U.S. major food allergens, color additives, and aspartame/PKU guidance, and reports unmatched terms as insufficient information.
- Personalized notes use only the authenticated user's saved dietary preferences and health goal. Known matches can flag explicit preference conflicts or request certification/source verification; health goals provide context only and are not inferred from ingredients. No disease diagnosis, product safety certification, or unsupported health-effect claims are produced.
- No external generative AI service or API key was added: the existing backend had no configured evidence-grounded model provider, and free-form generated health claims would be difficult to verify. Model/provider failure handling is therefore not applicable; unknown or unsupported ingredients use an explicit unavailable-information result.
- Analysis records use the existing user and product relationships. Product deletion preserves the analysis text and product-name snapshot while setting the product reference to null; users cannot read or create analyses for another user's products.
- `backend/scripts/init_products.py` initializes and verifies the new `product_ingredient_analyses` table without duplicating existing product/history tables.
- Verification: MySQL initialization succeeded; `python -m unittest discover -s tests -v` passed all 17 backend tests, including ingredient parsing, classifications, invalid input, personalization, persistence, no-profile behavior, product deletion, and owner isolation. `npm test` passed all 10 frontend tests and `npm run build` completed successfully. `git diff --check` passed.
- Source URLs were checked for the FDA allergen, additive, sweetener, and color-additive references. The ingredient catalogue is intentionally limited; label coverage and physical/browser visual behavior were not exhaustively tested.

## Phase 10 historical ingredient comparison

- Added authenticated APIs to retrieve the current user's timestamped ingredient-analysis history and compare two saved analysis IDs. Comparisons require distinct, chronologically ordered records owned by the caller and associated with the same product identity.
- Comparison uses the immutable Phase 9 `analysis_result` snapshots. It reports added, removed, unchanged, reordered, classification-changed, and explanation/evidence-changed entries; it does not rerun analysis or modify the stored records.
- Ingredient matching normalizes Unicode presentation, case, accents, punctuation, whitespace, and common E-number formatting. Original ingredient text and original names remain available in the comparison. Repeated ingredients are matched by occurrence, not collapsed to a set.
- Added nullable, indexed `product_identity_snapshot` to `product_ingredient_analyses`. The idempotent `backend/scripts/init_products.py` backfills currently linked rows and stores product identity on new analyses, so future product deletions can preserve same-product grouping while `product_id` remains `NULL` under the existing `ON DELETE SET NULL` relationship. No new history table or foreign key was added.
- Analyses tied to products deleted before this migration retain their ingredient and analysis snapshots, but their former product identity cannot be recovered; they remain visible in history and are not guessed/grouped by product name.
- Added a responsive comparison page reachable from product details, ingredient analysis, and product history. It provides same-product selectors, dates, changes by category, saved ingredient text, and loading/error/insufficient-history states.
- Verification against the configured MySQL server: `scripts/init_products.py` completed successfully; all 23 backend tests passed, including MySQL persistence, user isolation, invalid IDs, same-product validation, product edit/deletion preservation, ingredient normalization, duplicates, ordering, and saved classification/explanation changes.
- Frontend verification: `npm test` passed all 10 tests; `npm run build` passed. `git diff --check` passed. Physical device/browser visual checks were not run.

## Phase 11 misleading food claims detection

- Added a product-detail entry point for reviewing OCR-extracted package text or manually entered/edited claims. Existing OCR was reused; recognized OCR text is stored only when saving an OCR-scanned product and is capped at 20,000 characters.
- Added deterministic claim phrase recognition for common nutrition claims, dietary/certification claims, and selected marketing/health-related statements. Unknown manual phrases are retained as unclassified and marked unable to verify; marketing text is not automatically treated as a regulated nutrition claim.
- Claim analysis compares saved product evidence and ingredients. A limited FSSAI 2018 Advertising and Claims Regulations reference check is applied to sugar-free, low-sugar, low-fat, and fat-free claims only where saved per-100 g data and an allowed solid-food category are available. Beverage claims require per-100 ml facts; no density conversion or missing-value default is used. Other criteria remain unavailable unless reliably implemented.
- Results show original claim text, category, applicable criterion, evidence, status, explanation, regulatory reference where used, and a per-analysis disclaimer. Potentially conflicting ingredient terms produce only a potential inconsistency, not a declaration of falsity or non-compliance. User dietary preferences appear only when relevant.
- Added authenticated `POST /api/products/<product_id>/claims/analyze` and `GET /api/products/claims/history` endpoints. Queries are scoped to the current user. Persisted records snapshot the claim text, product facts, source label, results, date, and product identity; product deletion sets the live reference to null while preserving the snapshot.
- Added nullable `products.packaging_text` and the `product_food_claim_analyses` MySQL table. `backend/scripts/init_products.py` migrates and verifies both idempotently; no existing tables or snapshots are overwritten.
- Limitations: no cholesterol field is stored; high/source-of-protein, high-fibre, low-sodium, low-carbohydrate, reduced-sugar, organic, natural, and most other claim types remain unable to verify. Category, ingredient completeness, certification, cross-contact, data accuracy, and package authenticity cannot be independently confirmed. OCR and manual text must be reviewed. No external AI or claim API is used.
- Verification against configured MySQL: schema initialization passed; the full backend suite passed all 31 tests, including the new claim unit and MySQL integration tests for detection, supported/inconsistent/unverifiable cases, missing data, nutrition units, ingredient evidence, personalization, invalid input, ownership, persistence, and product deletion preservation.
- Frontend verification: `npm test` passed all 10 tests, `npm run build` passed, and `git diff --check` passed. Physical device/browser visual checks were not run.

## Known limitations and remaining work

- The separate profile-aware nutrition-insights feature is not implemented. Existing recommendations use transparent, goal-specific comparisons; this final QA did not add feature scope.
- Product reformulation tracking and update notifications are not implemented.
- Product facts come from user entry, a community database, or OCR and are not independently verified; recommendations are informational and not medical advice.
- Open Food Facts is community-maintained and may lack or contain incorrect product facts. OCR is English-focused, imperfect, and requires package review. Camera access requires browser permission and a secure context (localhost or HTTPS); OCR downloads its browser engine and language assets on first use.
- Ingredient matching uses a limited static alias/reference set and may miss regional names, formulation-specific sub-ingredients, allergens, or cross-contact statements. Its ingredient-specific health notes are limited to cited reference material; it is not medical advice or an allergy-safety assessment. No generative AI provider is configured.
- Product identity cannot be reconstructed for legacy ingredient-analysis rows whose products were already deleted before the Phase 10 identity-snapshot migration; those rows remain preserved but cannot be compared safely.

## Indian packaged-food catalog — Phase 2

- Added a standalone `packaged_food_catalog` table; the existing user-owned `products` table and its relationships were not changed. The new table has a unique `(source_name, source_row_id)` key, row/file SHA-256 values, per-serving-inferred nutrition columns, complete raw CSV row JSON, and quality flags. Search-oriented indexes cover product name, brand, category, and subcategory.
- Added `backend/app/catalog_import.py` and `backend/scripts/import_packaged_foods.py`. The importer accepts the audited CSV or a ZIP containing exactly one `packaged_foods_india.csv`, verifies the SHA-256 (`f64832743d4918c428aab31fb8a3681cd2dee89f3c5f305185ec0edfabe8f303`), all 25 headers, 852 rows, and serials 1–852 before database writes. It batches inserts in one transaction, skips matching source keys and row hashes, reports changed-row conflicts without overwriting, and refuses to alter an existing catalog table with a mismatched schema.
- Missing, ambiguous comma-formatted, nonnumeric, and `<N` nutrition values are not silently converted to zero. Original cells remain in `source_row_raw`; parsed values remain nullable and their parse status is recorded in `quality_flags`. Nutrition basis is marked `per_serving_inferred`, not per 100 g.
- MySQL import result: 852 records validated and inserted; 0 identical skips, conflicts, invalid records, or failed records; catalog count 852. A second run inserted 0 and skipped all 852 identical source rows.
- Database changes: only the new `packaged_food_catalog` table and its indexes were created. Post-import verification found source row IDs 1–852, a single source/file hash, and the expected source unique constraint. The existing `products` table remained at 1 row and its pre-import content fingerprint was unchanged.
- Dataset quality flags retain suspicious source facts rather than dropping records. Among the 852 rows, warnings include nutrition values larger than serving mass, nutrients that do not reconcile with other source values, upper-bound (`<N`) entries, ambiguous comma values, malformed numeric text, and implausible energy density. These flags are prompts for review, not corrections.
- The seven isolated importer tests cover exact CSV preflight checks, parsing and raw-value retention, first/repeated import, changed-row conflicts, invalid records, transaction rollback, and unchanged `products` data. The full backend suite passed all 38 tests, including integration tests against the configured MySQL database; the frontend suite passed all 11 tests; the production Vite build and `git diff --check` passed.
- This phase imports a static source snapshot only. It does not update catalog records when a source row later changes, normalize duplicate-name products into one record, or claim that the source nutrition data is independently verified.

## Indian packaged-food catalog — Phase 3

- Added the authenticated `/api/catalog` Flask blueprint. It queries only `packaged_food_catalog`; existing `/api/products` routes and authentication were left unchanged.
- `GET /api/catalog/products` supports case-insensitive substring search with `q` (name) and `brand`, plus bounded `page`/`per_page` pagination. `GET /api/catalog/products/<id>` returns ingredients, per-serving-inferred nutrition, provenance, source raw cells, and quality flags. `GET /api/catalog/categories` returns categories with subcategories.
- `GET /api/catalog/products/filter` supports exact category matching and inclusive `*_min`/`*_max` ranges for calories, sugar, fat, protein, and sodium. SQL comparisons explicitly exclude `NULL` nutrient values; other missing nutrition values remain `null` in API responses. No per-100 g conversion or zero substitution is performed.
- Added isolated backend tests for JWT access, name/brand search, detail data and provenance, category retrieval, pagination, nutrition filters with missing values, invalid parameters, not-found products, database errors, and the unchanged existing product endpoint.
- MySQL smoke checks against the imported 852-row catalog passed for list/search/detail/categories/filter, invalid parameters, missing IDs, and the existing product API. All 47 backend tests passed, including MySQL integration tests; Python compilation and `git diff --check` passed. No frontend files or behavior were changed in this phase.

## Indian packaged-food catalog — Phase 4

- Added authenticated `GET /api/catalog/products/compare?product_id_1=<id>&product_id_2=<id>` and `GET /api/catalog/products/<id>/alternatives?limit=5`. Both query only `packaged_food_catalog`; neither changes the user-owned `products` table.
- Comparison returns both catalog snapshots, all available nutrition, ingredients, serving sizes, raw values, and provenance. Per-serving differences are marked comparable only when both records use the inferred per-serving basis and have equal serving sizes. Supported per-100 g values are normalized only when the stored basis and serving size permit it; different serving sizes/bases are explicitly reported. Missing values remain `null`.
- Alternatives prioritize the same category and subcategory, then same category, then a matching subcategory across categories. They compare calories, sugar, saturated fat, sodium, protein, and dietary fiber on a supported common per-100 g basis. A candidate needs at least two comparable values and one measured favorable difference; explanations also disclose measurable trade-offs and unavailable nutrients. Results are ranked transparently by category match and observed changes, not by an aggregate score.
- Reviewed `NutriScan1-main/main.py` in the supplied archive. Its score uses a 0–100 threshold-based penalty/bonus heuristic, requires calories/sugar/saturated fat/sodium, optionally awards protein/fiber bonuses, and normalizes using serving size. It was not ported: these cutoffs are not validated, category/context-specific, or suitable as an official health rating. No score endpoint or field was added.
- Added isolated backend tests for comparisons, ID validation, missing values, serving-size and measurement-basis handling, category matching, recommendation explanations and trade-offs, missing-data exclusions, uniqueness, and existing API regression. All 54 backend tests passed, including MySQL integration tests; the seven focused Phase 4 tests passed.
- Read-only smoke checks against the imported MySQL catalog passed for both endpoints. Different serving sizes were flagged, per-serving comparison was disabled, supported per-100 g normalization was returned, recommendations contained unique IDs and excluded the selected product, and no score was returned. Existing catalog/product APIs returned successfully; the catalog remained at 852 rows.
- Python compilation and `git diff --check` passed. No frontend files, database schema, existing `products` records, or imported dataset rows were changed in this phase.

## Indian packaged-food catalog — Phase 5

- Added protected React routes for `/catalog`, `/catalog/:productId`, and `/catalog/compare`, plus a minimal dashboard entry card. Existing product, authentication, and profile pages were not redesigned.
- Added catalog Axios wrappers that reuse the existing API client and JWT request interceptor. The UI supports product-name and brand search, category and per-serving nutrient ranges, pagination, product details, ingredients, source provenance, and original CSV values.
- Combined text search with category/nutrition filters by fetching the filtered catalog pages (up to the API's 100-record page limit) and applying name/brand search in the browser; this preserves the existing Flask API without changing it.
- Added two-product comparison with explicit serving-size and measurement-basis warnings, per-serving and supported per-100 g values, ingredients, and unavailable values shown as “Not available.” Added alternatives with backend explanations, nutrient differences, and trade-offs; no score or universal health claim is shown.
- Added responsive, catalog-scoped styles using the existing Sage/Off-White design tokens. Added focused Node tests for catalog filtering, local pagination, unavailable-value formatting, API routes, and shared Axios JWT handling.
- Frontend verification: `npm test` passed all 17 tests and `npm run build` passed. Browser-interaction checks were attempted but the integrated browser navigation timed out before the catalog rendered; no backend, database schema, or catalog records were changed.
