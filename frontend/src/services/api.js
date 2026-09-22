const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export async function api(path) {
  const response = await fetch(`${API_URL}${path}`)
  if (!response.ok) throw new Error(`API request failed (${response.status})`)
  return response.json()
}

export async function post(path, body) {
  const response = await fetch(`${API_URL}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!response.ok) throw new Error(`API request failed (${response.status})`)
  return response.json()
}
