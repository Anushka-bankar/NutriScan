import api from './client.js';

export const getCatalogProducts = (params = {}) =>
  api.get('/catalog/products', { params });
export const filterCatalogProducts = (params = {}) =>
  api.get('/catalog/products/filter', { params });
export const getCatalogProduct = (productId) =>
  api.get(`/catalog/products/${productId}`);
export const getCatalogCategories = () => api.get('/catalog/categories');
export const compareCatalogProducts = (productId1, productId2) =>
  api.get('/catalog/products/compare', {
    params: {
      product_id_1: productId1,
      product_id_2: productId2,
    },
  });
export const getCatalogAlternatives = (productId, limit = 5) =>
  api.get(`/catalog/products/${productId}/alternatives`, {
    params: { limit },
  });
