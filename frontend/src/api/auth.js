import api from './client.js';

export const register = (details) => api.post('/auth/register', details);
export const login = (credentials) => api.post('/auth/login', credentials);
export const getCurrentUser = () => api.get('/auth/me');
export const getHealthProfile = () => api.get('/profile');
export const saveHealthProfile = (profile) => api.put('/profile', profile);
