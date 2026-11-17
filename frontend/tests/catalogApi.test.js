import test from 'node:test';
import assert from 'node:assert/strict';
import api from '../src/api/client.js';
import {
  compareCatalogProducts,
  filterCatalogProducts,
  getCatalogAlternatives,
  getCatalogCategories,
  getCatalogProduct,
  getCatalogProducts,
} from '../src/api/catalog.js';

test('catalog API helpers use the shared Axios client and Flask routes', async () => {
  const previousAdapter = api.defaults.adapter;
  const previousWindow = globalThis.window;
  const requests = [];
  globalThis.window = {
    sessionStorage: { getItem: () => 'test-jwt-token' },
  };
  api.defaults.adapter = async (config) => {
    requests.push(config);
    return {
      data: { ok: true },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    };
  };

  try {
    await getCatalogProducts({ page: 2, q: 'oats', brand: 'mill' });
    await filterCatalogProducts({ category: 'SNACKS', sugar_max: '10' });
    await getCatalogProduct(14);
    await getCatalogCategories();
    await compareCatalogProducts(14, 22);
    await getCatalogAlternatives(14, 3);

    assert.deepEqual(
      requests.map(({ method, url }) => [method, url]),
      [
        ['get', '/catalog/products'],
        ['get', '/catalog/products/filter'],
        ['get', '/catalog/products/14'],
        ['get', '/catalog/categories'],
        ['get', '/catalog/products/compare'],
        ['get', '/catalog/products/14/alternatives'],
      ],
    );
    assert.deepEqual(requests[0].params, {
      page: 2,
      q: 'oats',
      brand: 'mill',
    });
    assert.deepEqual(requests[4].params, {
      product_id_1: 14,
      product_id_2: 22,
    });
    assert.deepEqual(requests[5].params, { limit: 3 });
    assert.equal(requests[0].headers.Authorization, 'Bearer test-jwt-token');
  } finally {
    api.defaults.adapter = previousAdapter;
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
  }
});
