import { useState, useRef, useEffect } from 'react'
import { useStreamChat } from '../hooks/useStreamChat.js'
import MessageBubble from './MessageBubble.jsx'
import './ChatWidget.css'

function ChatWidget() {
  const { messages, sendMessage, isLoading, clearChat } = useStreamChat()
  const [input, setInput] = useState('')
  const [showClearConfirm, setShowClearConfirm] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    sendMessage(input)
    setInput('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="chat-widget">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </div>
        <div className="chat-header-text">
          <h1>IT Support Copilot</h1>
          <span className="chat-header-status">
            <span className="status-dot" />
            Online — Siap membantu
          </span>
        </div>
        
        {messages.length > 0 && (
          <button 
            className="chat-clear-btn" 
            onClick={() => setShowClearConfirm(true)} 
            title="Bersihkan chat"
            type="button"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        )}
      </div>

      {/* Messages Area */}
      <div className="chat-messages">
        {/* Clear Confirmation Overlay */}
        {showClearConfirm && (
          <div className="clear-confirm-overlay">
            <div className="clear-confirm-box">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="clear-confirm-icon">
                <path d="M3 6h18"></path>
                <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
              </svg>
              <h3>Hapus Percakapan?</h3>
              <p>Semua riwayat pesan ini akan dihapus secara permanen.</p>
              <div className="clear-confirm-actions">
                <button type="button" className="btn-cancel" onClick={() => setShowClearConfirm(false)}>Batal</button>
                <button type="button" className="btn-delete" onClick={() => { clearChat(); setShowClearConfirm(false); }}>Ya, Hapus</button>
              </div>
            </div>
          </div>
        )}

        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                <line x1="9" y1="9" x2="15" y2="9" />
                <line x1="9" y1="13" x2="13" y2="13" />
              </svg>
            </div>
            <h2>Halo! 👋</h2>
            <p>Saya IT Support Copilot Anda.</p>
            <p className="chat-empty-sub">Tanyakan apa saja seputar IT — troubleshooting, panduan, atau pertanyaan teknis lainnya.</p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg.content}
            isUser={msg.role === 'user'}
            sources={msg.sources}
            isTyping={msg.isStreaming && msg.content === ''}
          />
        ))}

        {/* Typing indicator when loading but no streaming content yet */}
        {isLoading && messages.length > 0 && messages[messages.length - 1]?.role === 'user' && (
          <MessageBubble message="" isUser={false} isTyping={true} />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <form className="chat-input-area" onSubmit={handleSubmit}>
        <div className="chat-input-container">
          <input
            ref={inputRef}
            type="text"
            className="chat-input"
            placeholder="Ketik pertanyaan Anda..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            autoComplete="off"
          />
          <button
            type="submit"
            className={`chat-send-btn ${input.trim() && !isLoading ? 'active' : ''}`}
            disabled={!input.trim() || isLoading}
            title="Kirim pesan"
          >
            {isLoading ? (
              <svg className="send-spinner" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </div>
        <span className="chat-input-hint">Enter untuk mengirim</span>
      </form>
    </div>
  )
}

export default ChatWidget
