import { useState, useRef, useEffect } from 'react'

/** Menjaga ambang scroll 100px, badge unread, dan jeda auto-scroll halaman chat. */
export function useConversationScroll(messages) {
  const [showScrollBottomBtn, setShowScrollBottomBtn] = useState(false)
  const [unreadWhileScrolled, setUnreadWhileScrolled] = useState(0)

  const messagesContainerRef = useRef(null)
  const messagesEndRef = useRef(null)
  const isNearBottomRef = useRef(true)
  const prevMessagesLengthRef = useRef(0)

  const handleScroll = () => {
    if (!messagesContainerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight
    const isNear = distanceFromBottom < 100

    isNearBottomRef.current = isNear

    if (isNear) {
      setShowScrollBottomBtn(false)
      setUnreadWhileScrolled(0)
    } else {
      setShowScrollBottomBtn(true)
    }
  }

  const scrollToBottom = (behavior = 'smooth') => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior,
      })
    } else if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior })
    }
    isNearBottomRef.current = true
    setShowScrollBottomBtn(false)
    setUnreadWhileScrolled(0)
  }

  // Pesan baru tidak memindahkan viewport ketika petugas membaca riwayat.
  useEffect(() => {
    if (messages.length === 0) return

    const diff = messages.length - prevMessagesLengthRef.current
    prevMessagesLengthRef.current = messages.length

    if (diff > 0) {
      if (isNearBottomRef.current) {
        const timer = setTimeout(() => {
          scrollToBottom('smooth')
        }, 50)
        return () => clearTimeout(timer)
      } else {
        // User is scrolled up reading previous history -> don't yank view, show unread badge!
        setUnreadWhileScrolled((prev) => prev + diff)
        setShowScrollBottomBtn(true)
      }
    }
  }, [messages])

  return {
    showScrollBottomBtn,
    unreadWhileScrolled,
    messagesContainerRef,
    messagesEndRef,
    isNearBottomRef,
    prevMessagesLengthRef,
    setShowScrollBottomBtn,
    setUnreadWhileScrolled,
    handleScroll,
    scrollToBottom,
  }
}
