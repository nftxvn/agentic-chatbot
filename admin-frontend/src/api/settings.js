import client from './client'

export async function getWhatsappSettings() {
  const { data } = await client.get('/api/settings/whatsapp')
  return data
}

export async function updateWhatsappSettings(payload) {
  const { data } = await client.post('/api/settings/whatsapp', payload)
  return data
}

export async function testWhatsappConnection(payload) {
  const { data } = await client.post('/api/settings/whatsapp/test', payload)
  return data
}

export async function getTelegramSettings() {
  const { data } = await client.get('/api/settings/telegram')
  return data
}

export async function updateTelegramSettings(payload) {
  const { data } = await client.post('/api/settings/telegram', payload)
  return data
}

export async function testTelegramConnection(payload) {
  const { data } = await client.post('/api/settings/telegram/test', payload)
  return data
}

export async function setTelegramWebhook(payload) {
  const { data } = await client.post('/api/settings/telegram/webhook', payload)
  return data
}

export async function getChatbotSettings() {
  const { data } = await client.get('/api/settings/chatbot')
  return data
}

export async function updateChatbotSettings(payload) {
  const { data } = await client.post('/api/settings/chatbot', payload)
  return data
}

export async function resetChatbotSettings() {
  const { data } = await client.post('/api/settings/chatbot/reset')
  return data
}

export async function getAvailableModels() {
  const { data } = await client.get('/api/settings/models')
  return data
}

export async function getHardwareStatus(model) {
  const { data } = await client.get('/api/settings/hardware', { params: { model } })
  return data
}

export async function benchmarkModel(model) {
  const { data } = await client.post('/api/settings/models/benchmark', { model })
  return data
}



