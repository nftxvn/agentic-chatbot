import client from './client'

// ── Fast-Path & FAQ API ─────────────────────────────────────────────

export async function getFastPaths(params = {}) {
  const { data } = await client.get('/api/fast-paths', { params })
  return data
}

export async function createFastPath(payload) {
  const { data } = await client.post('/api/fast-paths', payload)
  return data
}

export async function updateFastPath(id, payload) {
  const { data } = await client.put(`/api/fast-paths/${id}`, payload)
  return data
}

export async function toggleFastPath(id) {
  const { data } = await client.patch(`/api/fast-paths/${id}/toggle`)
  return data
}

export async function deleteFastPath(id) {
  const { data } = await client.delete(`/api/fast-paths/${id}`)
  return data
}

// ── Direktori Unit Kerja & Bidang API ────────────────────────────────

export async function getDirectories(params = {}) {
  const { data } = await client.get('/api/directories', { params })
  return data
}

export async function createDirectory(payload) {
  const { data } = await client.post('/api/directories', payload)
  return data
}

export async function updateDirectory(id, payload) {
  const { data } = await client.put(`/api/directories/${id}`, payload)
  return data
}

export async function toggleDirectory(id) {
  const { data } = await client.patch(`/api/directories/${id}/toggle`)
  return data
}

export async function deleteDirectory(id) {
  const { data } = await client.delete(`/api/directories/${id}`)
  return data
}
