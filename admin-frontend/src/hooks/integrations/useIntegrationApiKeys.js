import { useState } from "react";
import { apiKeysApi } from "../../api/apiKeys";
import { addAppNotification } from "../../utils/notifications";

/** State dan operasi API key, webhook keluar, secret sekali tampil, dan riwayat pengiriman. */
export function useIntegrationApiKeys({ setStatusMsg }) {
  // ── STATE: API KEYS ──────────────────────────────────────────
  const [keys, setKeys] = useState([])
  const [showCreateKeyModal, setShowCreateKeyModal] = useState(false)
  const [keyName, setKeyName] = useState('')
  const [creatingKey, setCreatingKey] = useState(false)
  const [newlyCreatedKey, setNewlyCreatedKey] = useState(null)
  const [copiedKey, setCopiedKey] = useState(false)
  const [deleteKeyTarget, setDeleteKeyTarget] = useState(null)
  const [deletingKey, setDeletingKey] = useState(false)
  const [webhookTarget, setWebhookTarget] = useState(null)
  const [webhookForm, setWebhookForm] = useState({ webhook_url: '', webhook_enabled: false })
  const [savingWebhook, setSavingWebhook] = useState(false)
  const [rotatingWebhookSecret, setRotatingWebhookSecret] = useState(false)
  const [webhookSecretOnce, setWebhookSecretOnce] = useState('')
  const [webhookDeliveries, setWebhookDeliveries] = useState([])

  // ── API KEY HANDLERS ─────────────────────────────────────────
  const handleCreateKey = async (e) => {
    e.preventDefault()
    if (!keyName || !keyName.trim()) {
      setStatusMsg({ type: 'error', text: 'Nama aplikasi / klien pemanggil wajib diisi.' })
      return
    }
    setCreatingKey(true)
    setStatusMsg(null)
    try {
      const res = await apiKeysApi.create(keyName.trim())
      setShowCreateKeyModal(false)
      setKeyName('')
      setNewlyCreatedKey(res.data)
      const listRes = await apiKeysApi.list()
      const listData = Array.isArray(listRes?.data) ? listRes.data : Array.isArray(listRes) ? listRes : []
      setKeys(listData)
      addAppNotification({
        title: 'Manajemen Kunci API',
        message: `Kunci API "${res.data.name}" berhasil dibuat.`,
        type: 'system',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: err.response?.data?.message || 'Gagal membuat API Key baru.' })
    } finally {
      setCreatingKey(false)
    }
  }

  const handleToggleKey = async (key) => {
    try {
      await apiKeysApi.toggle(key.id)
      setKeys((prev) =>
        prev.map((k) => (k.id === key.id ? { ...k, is_active: !k.is_active } : k))
      )
      addAppNotification({
        title: 'Status Kunci API',
        message: `Kunci API "${key.name}" telah ${!key.is_active ? 'diaktifkan' : 'dinonaktifkan'}.`,
        type: 'info',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal mengubah status API Key.' })
    }
  }

  const handleDeleteKey = async () => {
    if (!deleteKeyTarget) return
    setDeletingKey(true)
    try {
      await apiKeysApi.delete(deleteKeyTarget.id)
      setKeys((prev) => prev.filter((k) => k.id !== deleteKeyTarget.id))
      setDeleteKeyTarget(null)
      addAppNotification({
        title: 'Kunci API Dicabut',
        message: `Kunci API "${deleteKeyTarget.name}" telah dihapus permanen.`,
        type: 'system',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal menghapus API Key.' })
    } finally {
      setDeletingKey(false)
    }
  }

  const openWebhookSettings = async (key) => {
    setWebhookTarget(key)
    setWebhookForm({
      webhook_url: key.webhook_url || '',
      webhook_enabled: Boolean(key.webhook_enabled),
    })
    setWebhookSecretOnce('')
    setWebhookDeliveries([])
    try {
      const result = await apiKeysApi.webhookDeliveries(key.id)
      setWebhookDeliveries(Array.isArray(result?.data) ? result.data : [])
    } catch (err) {
      console.error(err)
    }
  }

  const handleSaveWebhook = async (e) => {
    e.preventDefault()
    if (!webhookTarget) return
    setSavingWebhook(true)
    try {
      const result = await apiKeysApi.updateWebhook(webhookTarget.id, webhookForm)
      setKeys((prev) => prev.map((key) => key.id === webhookTarget.id ? { ...key, ...result.data } : key))
      setWebhookTarget((prev) => prev ? { ...prev, ...result.data } : prev)
      setStatusMsg({ type: 'success', text: result.message || 'Konfigurasi webhook tersimpan.' })
      setWebhookTarget(null)
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.response?.data?.message || 'Gagal menyimpan webhook.' })
    } finally {
      setSavingWebhook(false)
    }
  }

  const handleRotateWebhookSecret = async () => {
    if (!webhookTarget) return
    setRotatingWebhookSecret(true)
    try {
      const result = await apiKeysApi.rotateWebhookSecret(webhookTarget.id)
      setWebhookSecretOnce(result.data.plain_secret)
      setKeys((prev) => prev.map((key) => key.id === webhookTarget.id ? { ...key, webhook_secret_configured: true } : key))
      setWebhookTarget((prev) => prev ? { ...prev, webhook_secret_configured: true } : prev)
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.response?.data?.message || 'Gagal membuat secret webhook.' })
    } finally {
      setRotatingWebhookSecret(false)
    }
  }

  return {
    keys,
    setKeys,
    showCreateKeyModal,
    setShowCreateKeyModal,
    keyName,
    setKeyName,
    creatingKey,
    newlyCreatedKey,
    setNewlyCreatedKey,
    copiedKey,
    setCopiedKey,
    deleteKeyTarget,
    setDeleteKeyTarget,
    webhookTarget,
    setWebhookTarget,
    webhookForm,
    setWebhookForm,
    savingWebhook,
    rotatingWebhookSecret,
    webhookSecretOnce,
    webhookDeliveries,
    handleCreateKey,
    handleToggleKey,
    handleDeleteKey,
    openWebhookSettings,
    handleSaveWebhook,
    handleRotateWebhookSecret,
  };
}
