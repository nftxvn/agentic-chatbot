/**
 * Utility untuk mencatat event notifikasi tindakan pengguna (Tambah, Edit, Hapus)
 * secara real-time ke localStorage dan memicu update di header.
 */
export function addAppNotification({ title, message, type = 'info', documentId = null }) {
  try {
    const existing = JSON.parse(localStorage.getItem('action_notifications') || '[]')
    const newNotification = {
      id: `action-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`,
      title,
      message,
      time: 'Baru saja',
      timestamp: Date.now(),
      type,
      unread: true,
      documentId: documentId ? Number(documentId) : null,
    }
    // Simpan maksimal 30 histori tindakan terakhir
    const updated = [newNotification, ...existing].slice(0, 30)
    localStorage.setItem('action_notifications', JSON.stringify(updated))
    window.dispatchEvent(new Event('app-notification-update'))
    window.dispatchEvent(new CustomEvent('app-global-toast', { detail: newNotification }))
  } catch (err) {
    console.error('Failed to log app notification:', err)
  }
}
