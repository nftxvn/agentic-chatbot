import { useSearchParams } from "react-router-dom";
import { useState, useEffect, useRef, useLayoutEffect } from "react";
import { useIntegrationApiKeys } from "./useIntegrationApiKeys";
import { useIntegrationWhatsApp } from "./useIntegrationWhatsApp";
import { useIntegrationTelegram } from "./useIntegrationTelegram";
import gsap from "gsap";
import { apiKeysApi } from "../../api/apiKeys";
import { getWhatsappSettings, getTelegramSettings } from "../../api/settings";

/** Tab integrasi, pemuatan awal, status, clipboard, snippet API, dan komposisi workflow kanal. */
export function useIntegrations() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')
  const validTabs = ['apikeys', 'whatsapp', 'telegram', 'docs']
  const activeTab = validTabs.includes(tabParam) ? tabParam : 'apikeys'

  const setActiveTab = (newTab) => {
    setSearchParams({ tab: newTab }, { replace: true })
  }

  const [loading, setLoading] = useState(true)
  const [statusMsg, setStatusMsg] = useState(null)

  const {
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
  } = useIntegrationApiKeys({ setStatusMsg });

  const {
    setInitialWaForm,
    waForm,
    setWaForm,
    isWaDirty,
    savingWa,
    showWaToken,
    setShowWaToken,
    testPhone,
    setTestPhone,
    testMsgText,
    setTestMsgText,
    testingSend,
    testResult,
    copiedWebhook,
    setCopiedWebhook,
    copiedVerifyToken,
    setCopiedVerifyToken,
    handleWaChange,
    handleDiscardWa,
    handleWaSubmit,
    handleTestSendWa,
  } = useIntegrationWhatsApp({ setStatusMsg });

  const {
    setInitialTgForm,
    tgForm,
    setTgForm,
    isTgDirty,
    savingTg,
    showTgToken,
    setShowTgToken,
    tgTestChatId,
    setTgTestChatId,
    tgTestMsg,
    setTgTestMsg,
    testingTgSend,
    tgTestResult,
    setCopiedTgWebhook,
    registeringWebhook,
    webhookResult,
    handleTgChange,
    handleDiscardTg,
    handleTgSubmit,
    handleTestSendTg,
    handleAutoRegisterWebhook,
  } = useIntegrationTelegram({ setStatusMsg });

  // ── STATE: CODE SNIPPET DOCS ─────────────────────────────────
  const [docLang, setDocLang] = useState('curl')
  const [copiedCode, setCopiedCode] = useState(false)
  const headerRef = useRef(null)

  useEffect(() => {
    fetchAllData()
  }, [])

  useLayoutEffect(() => {
    if (headerRef.current?.children?.length) {
      gsap.fromTo(
        headerRef.current.children,
        { opacity: 0, x: -16 },
        { opacity: 1, x: 0, duration: 0.5, stagger: 0.08, ease: 'power2.out', clearProps: 'all' }
      )
    }
  }, [loading])

  async function fetchAllData() {
    const startTime = Date.now()
    try {
      setLoading(true)
      const [keysRes, waRes, tgRes] = await Promise.all([
        apiKeysApi.list().catch(() => ({ data: [] })),
        getWhatsappSettings().catch(() => ({})),
        getTelegramSettings().catch(() => ({})),
      ])
      const keysList = Array.isArray(keysRes?.data) ? keysRes.data : Array.isArray(keysRes) ? keysRes : []
      setKeys(keysList)
      const loadedWa = {
        wa_status: waRes?.wa_status || false,
        wa_api_url: waRes?.wa_api_url || '',
        wa_token: waRes?.wa_token || '',
        wa_phone_number: waRes?.wa_phone_number || '',
        wa_webhook_verify_token: waRes?.wa_webhook_verify_token || 'diskominfo_wa_rag_token',
        webhook_url: waRes?.webhook_url || `${window.location.origin}/api/v1/webhook/whatsapp`,
      }
      setWaForm(loadedWa)
      setInitialWaForm(loadedWa)

      const loadedTg = {
        telegram_status: tgRes?.telegram_status || false,
        telegram_bot_token: tgRes?.telegram_bot_token || '',
        telegram_bot_username: tgRes?.telegram_bot_username || '',
        webhook_url: tgRes?.webhook_url || `${window.location.origin}/api/v1/webhook/telegram`,
      }
      setTgForm(loadedTg)
      setInitialTgForm(loadedTg)
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal memuat data integrasi dari server.' })
    } finally {
      const elapsed = Date.now() - startTime
      setTimeout(() => setLoading(false), Math.max(0, 200 - elapsed))
    }
  }

  const handleCopy = (text, type) => {
    navigator.clipboard.writeText(text)
    if (type === 'webhook') {
      setCopiedWebhook(true)
      setTimeout(() => setCopiedWebhook(false), 2000)
    } else if (type === 'tg_webhook') {
      setCopiedTgWebhook(true)
      setTimeout(() => setCopiedTgWebhook(false), 2000)
    } else if (type === 'verify') {
      setCopiedVerifyToken(true)
      setTimeout(() => setCopiedVerifyToken(false), 2000)
    } else if (type === 'secret') {
      setCopiedKey(true)
      setTimeout(() => setCopiedKey(false), 2000)
    } else if (type === 'code') {
      setCopiedCode(true)
      setTimeout(() => setCopiedCode(false), 2000)
    }
  }

  const generateSnippet = () => {
    if (docLang === 'curl') {
      return `curl -X POST "${window.location.origin}/api/v1/chat" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer sk_live_YOUR_API_KEY" \\
  -d '{
    "session_id": "client-session-123",
    "query": "Bagaimana prosedur permohonan subdomain acehkota.go.id?"
  }'`
    }
    if (docLang === 'python') {
      return `import requests

url = "${window.location.origin}/api/v1/chat"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer sk_live_YOUR_API_KEY"
}
payload = {
    "session_id": "client-session-123",
    "query": "Bagaimana prosedur permohonan subdomain acehkota.go.id?"
}

response = requests.post(url, headers=headers, json=payload, timeout=30)
data = response.json()

print("Jawaban AI:", data.get("answer"))
print("Rujukan SOP:", data.get("sources"))`
    }
    return `// JavaScript (Fetch API)
const response = await fetch("${window.location.origin}/api/v1/chat", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer sk_live_YOUR_API_KEY",
  },
  body: JSON.stringify({
    session_id: "client-session-123",
    query: "Bagaimana prosedur permohonan subdomain acehkota.go.id?",
  }),
});

const data = await response.json();
console.log("Jawaban:", data.answer);
console.log("Rujukan:", data.sources);`
  }

  return {
    activeTab,
    setActiveTab,
    loading,
    statusMsg,
    setStatusMsg,
    keys,
    showCreateKeyModal,
    setShowCreateKeyModal,
    keyName,
    setKeyName,
    creatingKey,
    newlyCreatedKey,
    setNewlyCreatedKey,
    copiedKey,
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
    waForm,
    isWaDirty,
    savingWa,
    showWaToken,
    setShowWaToken,
    testPhone,
    setTestPhone,
    testMsgText,
    setTestMsgText,
    testingSend,
    testResult,
    copiedWebhook,
    copiedVerifyToken,
    handleWaChange,
    handleDiscardWa,
    handleWaSubmit,
    handleTestSendWa,
    tgForm,
    isTgDirty,
    savingTg,
    showTgToken,
    setShowTgToken,
    tgTestChatId,
    setTgTestChatId,
    tgTestMsg,
    setTgTestMsg,
    testingTgSend,
    tgTestResult,
    registeringWebhook,
    webhookResult,
    handleTgChange,
    handleDiscardTg,
    handleTgSubmit,
    handleTestSendTg,
    handleAutoRegisterWebhook,
    docLang,
    setDocLang,
    copiedCode,
    headerRef,
    handleCopy,
    generateSnippet,
  };
}
