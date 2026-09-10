import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export function getApiBase() {
  return API_BASE
}

const client = axios.create({
  baseURL: API_BASE,
  timeout: 120000,
})

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function detailFromError(error) {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join('; ')
  }
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return error?.message || 'Request failed'
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

async function request(promise) {
  try {
    const res = await promise
    return res.data
  } catch (error) {
    throw new ApiError(error?.response?.status || 0, detailFromError(error))
  }
}

export const api = {
  login(email, password) {
    const body = new URLSearchParams()
    body.set('username', email)
    body.set('password', password)
    return request(
      client.post('/api/v1/auth/login', body, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      }),
    )
  },

  me(token) {
    return request(client.get('/api/v1/auth/me', { headers: authHeaders(token) }))
  },

  listCases(token) {
    return request(client.get('/api/v1/cases', { headers: authHeaders(token) }))
  },

  getCase(token, caseId) {
    return request(client.get(`/api/v1/cases/${caseId}`, { headers: authHeaders(token) }))
  },

  getEvidence(token, caseId) {
    return request(
      client.get(`/api/v1/cases/${caseId}/evidence`, { headers: authHeaders(token) }),
    )
  },

  listDrafts(token, caseId) {
    return request(
      client.get(`/api/v1/cases/${caseId}/drafts`, { headers: authHeaders(token) }),
    )
  },

  generateDraft(token, caseId) {
    return request(
      client.post(`/api/v1/cases/${caseId}/generate-draft`, null, {
        headers: authHeaders(token),
      }),
    )
  },

  updateDraft(token, caseId, payload) {
    return request(
      client.patch(`/api/v1/cases/${caseId}/draft`, payload, {
        headers: authHeaders(token),
      }),
    )
  },

  submitCase(token, caseId) {
    return request(
      client.post(`/api/v1/cases/${caseId}/submit`, null, {
        headers: authHeaders(token),
      }),
    )
  },

  approveCase(token, caseId, comment) {
    return request(
      client.post(
        `/api/v1/cases/${caseId}/approve`,
        { comment },
        { headers: authHeaders(token) },
      ),
    )
  },

  rejectCase(token, caseId, comment) {
    return request(
      client.post(
        `/api/v1/cases/${caseId}/reject`,
        { comment },
        { headers: authHeaders(token) },
      ),
    )
  },

  caseAudit(token, caseId) {
    return request(
      client.get(`/api/v1/cases/${caseId}/audit`, { headers: authHeaders(token) }),
    )
  },
}
