/**
 * aiChatService.js - Persistent Singleton AI Chat Simulator Service
 *
 * Keeps chat streaming, history, and retrieval state active in the background
 * even when the admin navigates to other pages (Dashboard, Documents, etc.).
 */

const STORAGE_KEYS = {
  MESSAGES: 'rag_playground_chat_messages',
  CHUNKS: 'rag_playground_retrieved_chunks',
  SESSION_ID: 'rag_playground_session_id',
}

class AiChatService {
  constructor() {
    this.listeners = new Set()
    this.abortController = null
    this.isStreaming = false

    // Load initial session ID
    this.sessionId = this._loadSessionId()

    // Load initial messages
    this.chatMessages = this._loadMessages()

    // Load initial retrieved chunks
    this.retrievedChunks = this._loadChunks()
  }

  _loadSessionId() {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEYS.SESSION_ID)
      if (saved) return saved
      const newId = `sandbox-${Math.random().toString(36).substring(2, 10)}`
      sessionStorage.setItem(STORAGE_KEYS.SESSION_ID, newId)
      return newId
    } catch {
      return `sandbox-${Math.random().toString(36).substring(2, 10)}`
    }
  }

  _loadMessages() {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEYS.MESSAGES)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed.map((m) => ({
            ...m,
            isStreaming: false, // reset any dangling stream flag on reload
            timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
          }))
        }
      }
    } catch (e) {
      console.error('Failed to load cached chat messages:', e)
    }
    return []
  }

  _loadChunks() {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEYS.CHUNKS)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed)) return parsed
      }
    } catch (e) {
      console.error('Failed to load cached chunks:', e)
    }
    return []
  }

  _saveMessages() {
    try {
      if (this.chatMessages.length > 0) {
        sessionStorage.setItem(
          STORAGE_KEYS.MESSAGES,
          JSON.stringify(this.chatMessages)
        )
      }
    } catch (e) {
      console.error('Failed to save chat messages:', e)
    }
  }

  _saveChunks() {
    try {
      sessionStorage.setItem(
        STORAGE_KEYS.CHUNKS,
        JSON.stringify(this.retrievedChunks)
      )
    } catch (e) {
      console.error('Failed to save chunks:', e)
    }
  }

  subscribe(listener) {
    this.listeners.add(listener)
    // Immediately emit current state
    listener(this.getState())
    return () => {
      this.listeners.delete(listener)
    }
  }

  notify() {
    const state = this.getState()
    this.listeners.forEach((listener) => {
      try {
        listener(state)
      } catch (e) {
        console.error('Listener error in aiChatService:', e)
      }
    })
  }

  getState() {
    return {
      chatMessages: [...this.chatMessages],
      retrievedChunks: [...this.retrievedChunks],
      isStreaming: this.isStreaming,
      sessionId: this.sessionId,
    }
  }

  setInitialGreeting(greeting) {
    if (this.chatMessages.length === 0 && greeting) {
      this.chatMessages = [
        {
          id: 'init-greeting',
          role: 'assistant',
          content: greeting,
          timestamp: new Date(),
          sources: [],
        },
      ]
      this._saveMessages()
      this.notify()
    }
  }

  stopStream() {
    if (this.abortController) {
      this.abortController.abort()
      this.abortController = null
    }
    if (this.isStreaming) {
      this.isStreaming = false
      this.chatMessages = this.chatMessages.map((msg) =>
        msg.isStreaming ? { ...msg, isStreaming: false } : msg
      )
      this._saveMessages()
      this.notify()
    }
  }

  clearChat(greeting = 'Sesi pengujian baru telah dimulai.') {
    this.stopStream()
    this.sessionId = `sandbox-${Math.random().toString(36).substring(2, 10)}`
    try {
      sessionStorage.setItem(STORAGE_KEYS.SESSION_ID, this.sessionId)
      sessionStorage.removeItem(STORAGE_KEYS.CHUNKS)
    } catch {}

    this.retrievedChunks = []
    this.chatMessages = [
      {
        id: 'new-session',
        role: 'assistant',
        content: greeting,
        timestamp: new Date(),
        sources: [],
      },
    ]
    this._saveMessages()
    this._saveChunks()
    this.notify()
  }

  async sendMessage({
    query,
    systemPrompt,
    temperature = 0.2,
    topK = 8,
    selectedDocIds = [],
  }) {
    const q = (query || '').trim()
    if (!q || this.isStreaming) return

    this.stopStream()

    const userMsgId = `user-${Date.now()}`
    const botMsgId = `bot-${Date.now() + 1}`

    const userMsg = {
      id: userMsgId,
      role: 'user',
      content: q,
      timestamp: new Date(),
    }

    const botMsg = {
      id: botMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      sources: [],
      isStreaming: true,
      trace: {
        stage: 'retrieval',
        step: 1,
        totalSteps: 3,
        label: 'Pencarian Vektor & BM25',
        detail: 'Menghubungkan ke basis data vektor dan indeks leksikal...',
      },
    }

    this.chatMessages = [...this.chatMessages, userMsg, botMsg]
    this.isStreaming = true
    this._saveMessages()
    this.notify()

    const controller = new AbortController()
    this.abortController = controller
    const startTime = Date.now()

    try {
      const response = await fetch('/api/ai/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.sessionId,
          query: q,
          system_prompt: systemPrompt || undefined,
          temperature,
          top_k: topK,
          document_ids:
            selectedDocIds && selectedDocIds.length > 0
              ? selectedDocIds
              : undefined,
          include_debug: true,
        }),
        signal: controller.signal,
      })

      if (!response.ok) {
        let errorMsg = `Gagal terhubung ke layanan AI (Status ${response.status})`
        try {
          const errData = await response.json()
          if (errData?.detail) {
            errorMsg =
              typeof errData.detail === 'string'
                ? errData.detail
                : JSON.stringify(errData.detail)
          } else if (errData?.message) {
            errorMsg = errData.message
          }
        } catch {}
        throw new Error(errorMsg)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || trimmed.startsWith(':')) continue

          if (trimmed.startsWith('data:')) {
            const dataStr = trimmed.slice(5).trim()
            if (!dataStr || dataStr === '[DONE]') continue

            try {
              const parsed = JSON.parse(dataStr)

              if (parsed.type === 'trace') {
                this.chatMessages = this.chatMessages.map((msg) =>
                  msg.id === botMsgId
                    ? {
                        ...msg,
                        trace: {
                          stage: parsed.stage,
                          step: parsed.step,
                          totalSteps: parsed.total_steps,
                          label: parsed.label,
                          detail: parsed.detail,
                        },
                      }
                    : msg
                )
                this.notify()
              } else if (parsed.type === 'telemetry') {
                this.chatMessages = this.chatMessages.map((msg) =>
                  msg.id === botMsgId
                    ? {
                        ...msg,
                        telemetry: {
                          modelName: parsed.model_name,
                          contextTokens: parsed.context_tokens,
                          chunksCount: parsed.chunks_count,
                          isFallback: parsed.is_fallback,
                        },
                      }
                    : msg
                )
                this.notify()
              } else if (
                parsed.type === 'debug' &&
                Array.isArray(parsed.chunks)
              ) {
                this.retrievedChunks = parsed.chunks
                this._saveChunks()
                this.notify()
              } else if (parsed.type === 'chunk' || parsed.chunk) {
                const chunkText = parsed.chunk || parsed.content || ''
                this.chatMessages = this.chatMessages.map((msg) =>
                  msg.id === botMsgId
                    ? { ...msg, content: msg.content + chunkText }
                    : msg
                )
                this.notify()
              } else if (parsed.type === 'error') {
                this.chatMessages = this.chatMessages.map((msg) =>
                  msg.id === botMsgId
                    ? {
                        ...msg,
                        content:
                          parsed.content ||
                          parsed.message ||
                          'Terjadi kesalahan pada pemrosesan AI.',
                        isStreaming: false,
                        isError: true,
                      }
                    : msg
                )
                this.notify()
              }
            } catch {
              this.chatMessages = this.chatMessages.map((msg) =>
                msg.id === botMsgId
                  ? { ...msg, content: msg.content + dataStr }
                  : msg
              )
              this.notify()
            }
          }
        }
      }

      const elapsedMs = Date.now() - startTime
      this.chatMessages = this.chatMessages.map((msg) =>
        msg.id === botMsgId
          ? {
              ...msg,
              isStreaming: false,
              elapsedMs,
              telemetry: {
                ...(msg.telemetry || {}),
                elapsedMs,
                chunksCount: msg.telemetry?.chunksCount ?? this.retrievedChunks.length,
              },
              // Fallback if empty
              content:
                msg.content ||
                'Tidak ada respons yang dihasilkan oleh model AI.',
            }
          : msg
      )
      this._saveMessages()
      this.notify()
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('SSE Error in aiChatService:', err)
        const errorContent =
          err.message ||
          'Gagal terhubung ke layanan AI (Port 8080). Pastikan backend mikroservis sedang berjalan.'
        this.chatMessages = this.chatMessages.map((msg) =>
          msg.id === botMsgId
            ? {
                ...msg,
                content: errorContent,
                isStreaming: false,
                isError: true,
              }
            : msg
        )
        this._saveMessages()
        this.notify()
      }
    } finally {
      this.isStreaming = false
      this.abortController = null
      this._saveMessages()
      this.notify()
    }
  }
}

export const aiChatService = new AiChatService()
export default aiChatService
