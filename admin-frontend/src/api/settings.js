import client from './client'

export async function getWhatsappSettings() {
  const { data } = await client.get('/settings/whatsapp')
  return data
}

export async function updateWhatsappSettings(payload) {
  const { data } = await client.post('/settings/whatsapp', payload)
  return data
}
