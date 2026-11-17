import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildCatalogFilterParams,
  catalogErrorMessage,
  CATALOG_PAGE_SIZE,
  filterCatalogItems,
  formatCatalogValue,
  hasCatalogFilterCriteria,
  paginateCatalogItems,
} from '../src/utils/catalog.js';

test('unavailable catalog nutrition stays distinct from a measured zero', () => {
  assert.equal(formatCatalogValue(null, 'g'), 'Not available');
  assert.equal(formatCatalogValue('', 'mg'), 'Not available');
  assert.equal(formatCatalogValue('not numeric', 'kcal'), 'Not available');
  assert.equal(formatCatalogValue(0, 'g'), '0 g');
});

test('catalog filter parameters omit blank bounds and preserve selected values', () => {
  const params = buildCatalogFilterParams({
    category: ' SNACKS ',
    calories_min: '100',
    calories_max: '',
    sugar_min: '',
    sugar_max: '12',
    fat_min: '',
    fat_max: '',
    protein_min: '5',
    protein_max: '',
    sodium_min: '',
    sodium_max: '',
  });
  assert.deepEqual(params, {
    category: 'SNACKS',
    calories_min: '100',
    sugar_max: '12',
    protein_min: '5',
  });
  assert.equal(hasCatalogFilterCriteria(params), true);
  assert.equal(hasCatalogFilterCriteria({}), false);
});

test('combined catalog name and brand search filters the loaded catalog', () => {
  const products = [
    { id: 1, name: 'Oats Bar', brand: 'Nature Mill' },
    { id: 2, name: 'Oats Cereal', brand: 'Example Foods' },
    { id: 3, name: 'Rice Crackers', brand: 'Nature Mill' },
  ];
  assert.deepEqual(
    filterCatalogItems(products, { q: 'OATS', brand: 'nature' }).map(({ id }) => id),
    [1],
  );
  assert.deepEqual(
    filterCatalogItems(products, { brand: 'mill' }).map(({ id }) => id),
    [1, 3],
  );
});

test('catalog pagination clamps page bounds and handles empty results', () => {
  const products = Array.from({ length: 45 }, (_, index) => ({ id: index + 1 }));
  const secondPage = paginateCatalogItems(products, 2);
  assert.equal(secondPage.pagination.per_page, CATALOG_PAGE_SIZE);
  assert.equal(secondPage.pagination.pages, 3);
  assert.equal(secondPage.products[0].id, 21);
  assert.equal(paginateCatalogItems(products, 99).pagination.page, 3);
  assert.deepEqual(paginateCatalogItems([], 1), {
    products: [],
    pagination: { page: 1, per_page: CATALOG_PAGE_SIZE, total: 0, pages: 0 },
  });
});

test('catalog API errors use server messages and a fallback', () => {
  assert.equal(
    catalogErrorMessage({ response: { data: { message: 'Not found.' } } }, 'Failed.'),
    'Not found.',
  );
  assert.equal(catalogErrorMessage(new Error('offline'), 'Failed.'), 'Failed.');
});
