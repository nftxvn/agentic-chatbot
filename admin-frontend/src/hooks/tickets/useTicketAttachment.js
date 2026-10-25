import { useState, useRef } from 'react'
import { addAppNotification } from '../../utils/notifications'

/** Pilihan lampiran lokal, batas 10 MB, dan object URL pratinjau gambar. */
export function useTicketAttachment() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [filePreviewUrl, setFilePreviewUrl] = useState(null)

  const fileInputRef = useRef(null)

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 10 * 1024 * 1024) {
      addAppNotification({
        title: 'Ukuran File Terlalu Besar',
        message: 'Maksimal ukuran file lampiran adalah 10 MB.',
        type: 'warning',
      })
      return
    }
    setSelectedFile(file)
    if (file.type.startsWith('image/')) {
      setFilePreviewUrl(URL.createObjectURL(file))
    } else {
      setFilePreviewUrl(null)
    }
  }

  const handleClearFile = () => {
    setSelectedFile(null)
    if (filePreviewUrl) {
      URL.revokeObjectURL(filePreviewUrl)
      setFilePreviewUrl(null)
    }
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return {
    selectedFile,
    filePreviewUrl,
    fileInputRef,
    handleFileChange,
    handleClearFile,
  }
}
