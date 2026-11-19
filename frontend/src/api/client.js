import axios from 'axios';

let inMemoryToken = null;
export const setAuthToken = (token) => {
  inMemoryToken = token;
};

const client = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

// Attach in-memory token if present (supplementing HttpOnly cookie)
client.interceptors.request.use((config) => {
  if (inMemoryToken) {
    config.headers.Authorization = `Bearer ${inMemoryToken}`;
  }
  return config;
});

// Redirect to login on 401 using location.replace() and notify tabs
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      inMemoryToken = null;
      try {
        const channel = new BroadcastChannel('pharmatrack_auth');
        channel.postMessage({ type: 'LOGOUT' });
        channel.close();
      } catch (e) {}
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.history.replaceState(null, '', '/login?reason=session_expired');
        window.location.replace('/login?reason=session_expired');
      }
    }
    return Promise.reject(err);
  }
);

export default client;

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (username, password) =>
    client.post('/auth/login', { username, password }),
  logout: () => client.post('/auth/logout'),
  me: () => client.get('/auth/me'),
  changePassword: (data) => client.post('/auth/change-password', data),
  reportUnauthorized: (path, details) =>
    client.post('/auth/report-unauthorized', { path, details }),
};

// ── Users ─────────────────────────────────────────────────────────────────────
export const usersApi = {
  list: () => client.get('/users'),
  create: (data) => client.post('/users', data),
  update: (id, data) => client.put(`/users/${id}`, data),
  toggleStatus: (id) => client.patch(`/users/${id}/toggle-status`),
};

// ── Medicines ─────────────────────────────────────────────────────────────────
export const medicinesApi = {
  list: (params) => client.get('/medicines', { params }),
  get: (id) => client.get(`/medicines/${id}`),
  create: (data) => client.post('/medicines', data),
  update: (id, data) => client.put(`/medicines/${id}`, data),
  deactivate: (id) => client.delete(`/medicines/${id}`),
  createBatch: (data) => client.post('/medicines/batches', data),
  getBatches: (medicineId) => client.get(`/medicines/${medicineId}/batches`),
};

// ── Suppliers ─────────────────────────────────────────────────────────────────
export const suppliersApi = {
  list: () => client.get('/suppliers'),
  create: (data) => client.post('/suppliers', data),
  update: (id, data) => client.put(`/suppliers/${id}`, data),
};

// ── Purchases ─────────────────────────────────────────────────────────────────
export const purchasesApi = {
  list: (params) => client.get('/purchases', { params }),
  get: (id) => client.get(`/purchases/${id}`),
  create: (data) => client.post('/purchases', data),
  receive: (id, data) => client.post(`/purchases/${id}/receive`, data),
  cancel: (id, data) => client.post(`/purchases/${id}/cancel`, data),
  pdf: (id) => client.get(`/purchases/${id}/pdf`, { responseType: 'blob' }),
};

// ── Sales ─────────────────────────────────────────────────────────────────────
export const salesApi = {
  list: (params) => client.get('/sales', { params }),
  get: (id) => client.get(`/sales/${id}`),
  create: (data) => client.post('/sales', data),
  void: (id, data) => client.post(`/sales/${id}/void`, data),
  pdf: (id) => client.get(`/sales/${id}/pdf`, { responseType: 'blob' }),
};

// ── Customers ─────────────────────────────────────────────────────────────────
export const customersApi = {
  list: (params) => client.get('/customers', { params }),
  create: (data) => client.post('/customers', data),
  update: (id, data) => client.put(`/customers/${id}`, data),
};

// ── Stock ─────────────────────────────────────────────────────────────────────
export const stockApi = {
  overview: (params) => client.get('/stock/overview', { params }),
  dashboard: () => client.get('/stock/dashboard'),
  writeOff: (data) => client.post('/stock/write-off', data),
  adjust: (data) => client.post('/stock/adjust', data),
  adjustments: (params) => client.get('/stock/adjustments', { params }),
};

// ── Recommendations ───────────────────────────────────────────────────────────
export const recommendationsApi = {
  list: (params) => client.get('/recommendations', { params }),
  get: (id) => client.get(`/recommendations/${id}`),
  decide: (id, data) => client.post(`/recommendations/${id}/decide`, data),
  runForMedicine: (medicineId) =>
    client.post(`/recommendations/on-demand/${medicineId}`),
  runAll: () => client.post('/recommendations/run-all'),
  history: (params) => client.get('/recommendations/decision-history', { params }),
};

// ── Reports ───────────────────────────────────────────────────────────────────
export const reportsApi = {
  sales: (params) => client.get('/reports/sales', { params }),
  stockExpiry: (params) => client.get('/reports/stock-expiry', { params }),
  purchases: (params) => client.get('/reports/purchases', { params }),
  wastage: (params) => client.get('/reports/wastage', { params }),
  recommendations: (params) => client.get('/reports/recommendations', { params }),
  export: (type, params) =>
    client.get(`/reports/${type}`, { params: { ...params, format: 'pdf' }, responseType: 'blob' }),
  exportCsv: (type, params) =>
    client.get(`/reports/${type}`, { params: { ...params, format: 'csv' }, responseType: 'blob' }),
};

// ── Settings ──────────────────────────────────────────────────────────────────
export const settingsApi = {
  list: () => client.get('/settings'),
  update: (key, data) => client.put(`/settings/${key}`, data),
  auditLogs: (params) => client.get('/settings/audit-logs', { params }),
};
