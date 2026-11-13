import api from './client.js';

export const searchProducts = (query) =>
  api.get('/products', { params: { q: query } });
export const getProduct = (productId) => api.get(`/products/${productId}`);
export const createProduct = (product) => api.post('/products', product);
export const lookupBarcode = (barcode) =>
  api.get(`/products/lookup/barcode/${encodeURIComponent(barcode)}`);
export const importBarcodeProduct = (details) =>
  api.post('/products/import/barcode', details);
export const importOcrProduct = (details) =>
  api.post('/products/import/ocr', details);
export const classifyProduct = (productId, classification) =>
  api.patch(`/products/${productId}/classification`, classification);
export const getRecommendations = (productId) =>
  api.get(`/products/${productId}/recommendations`);
export const recordProductAnalysis = (productId) =>
  api.post(`/products/${productId}/history`);
export const getProductHistory = (params = {}) => api.get('/history', { params });
export const getWatchlist = (params = {}) => api.get('/watchlist', { params });
export const getWatchlistStatus = (productId) =>
  api.get(`/watchlist/status/${productId}`);
export const addToWatchlist = (productId) => api.post(`/watchlist/${productId}`);
export const removeWatchlistEntry = (entryId) =>
  api.delete(`/watchlist/entries/${entryId}`);
export const compareProducts = (productIds) =>
  api.get('/products/compare', { params: { ids: productIds.join(',') } });
