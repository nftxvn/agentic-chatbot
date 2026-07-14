import SourceReference from './SourceReference.jsx'
import './MessageBubble.css'

function MessageBubble({ message, isUser, sources, isTyping }) {
  return (
    <div className={`message-row ${isUser ? 'message-row--user' : 'message-row--bot'}`}>
      {/* Bot avatar */}
      {!isUser && (
        <div className="message-avatar">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="10" rx="2" />
            <circle cx="12" cy="5" r="3" />
            <line x1="8" y1="16" x2="8" y2="16.01" />
            <line x1="16" y1="16" x2="16" y2="16.01" />
          </svg>
        </div>
      )}

      <div className="message-content-wrapper">
        <div className={`message-bubble ${isUser ? 'message-bubble--user' : 'message-bubble--bot'}`}>
          {isTyping ? (
            <div className="typing-indicator">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          ) : (
            <div className="message-text">{message}</div>
          )}
        </div>

        {/* Source references (bot only) */}
        {!isUser && sources && sources.length > 0 && (
          <SourceReference sources={sources} />
        )}
      </div>
    </div>
  )
}

export default MessageBubble
