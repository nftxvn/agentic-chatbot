import { useState, useCallback, useRef } from 'react'

/**
 * Custom React hook for SSE streaming chat.
 *
 * Connects to POST /api/chat/stream and accumulates
 * streamed chunks into a single bot message in real-time.
 *
 * @returns {{ messages, sendMessage, isLoading }}
 */
export function useStreamChat() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const sessionIdRef = useRef(generateSessionId())
  const abortControllerRef = useRef(null)

  const sendMessage = useCallback(async (query) => {
    if (!query.trim() || isLoading) return

    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: query.trim(),
      timestamp: new Date(),
    }

    const botMessageId = (Date.now() + 1).toString()
    const botMessage = {
      id: botMessageId,
      role: 'assistant',
      content: '',
      sources: [],
      timestamp: new Date(),
      isStreaming: true,
    }

    setMessages((prev) => [...prev, userMessage, botMessage])
    setIsLoading(true)

    // Abort any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    const controller = new AbortController()
    abortControllerRef.current = controller

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          query: query.trim(),
        }),
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Process SSE lines
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // keep incomplete line in buffer

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || trimmed.startsWith(':')) continue // skip empty / comments

          if (trimmed.startsWith('event:')) {
            // Parse event type — handled in data parsing below
            continue
          }

          if (trimmed.startsWith('data:')) {
            const dataStr = trimmed.slice(5).trim()
            if (!dataStr || dataStr === '[DONE]') continue

            try {
              const parsed = JSON.parse(dataStr)

              if (parsed.type === 'chunk' || parsed.chunk) {
                // Accumulate text chunk
                const chunk = parsed.chunk || parsed.content || parsed.text || ''
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === botMessageId
                      ? { ...msg, content: msg.content + chunk }
                      : msg
                  )
                )
              } else if (parsed.type === 'sources' || parsed.sources) {
                // Attach source references
                const sources = parsed.sources || []
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === botMessageId
                      ? { ...msg, sources }
                      : msg
                  )
                )
              } else if (parsed.type === 'error') {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === botMessageId
                      ? { ...msg, content: `❌ ${parsed.message || 'Terjadi kesalahan'}`, isStreaming: false }
                      : msg
                  )
                )
              }
            } catch {
              // If data is plain text (not JSON), treat as chunk
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === botMessageId
                    ? { ...msg, content: msg.content + dataStr }
                    : msg
                )
              )
            }
          }
        }
      }

      // Mark streaming complete
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === botMessageId
            ? { ...msg, isStreaming: false }
            : msg
        )
      )
    } catch (err) {
      if (err.name === 'AbortError') return

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === botMessageId
            ? {
                ...msg,
                content: '❌ Gagal menghubungi server. Pastikan backend sedang berjalan.',
                isStreaming: false,
              }
            : msg
        )
      )
    } finally {
      setIsLoading(false)
      abortControllerRef.current = null
    }
  }, [isLoading])

  return { messages, sendMessage, isLoading }
}

/** Generate a random session ID */
function generateSessionId() {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  const segments = [8, 4, 4, 4, 12]
  return segments
    .map((len) =>
      Array.from({ length: len }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
    )
    .join('-')
}
