import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 10000,
});

const isPublicAuthRequest = (url = '') =>
  url.endsWith('/auth/login') || url.endsWith('/auth/register');

api.interceptors.request.use((config) => {
  const token = window.sessionStorage.getItem('nutriscan_token');
  if (token && !isPublicAuthRequest(config.url)) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      !isPublicAuthRequest(error.config?.url)
    ) {
      window.dispatchEvent(new Event('nutriscan:unauthorized'));
    }
    return Promise.reject(error);
  },
);

export default api;
