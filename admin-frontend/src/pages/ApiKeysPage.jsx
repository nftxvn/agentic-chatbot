import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import ReactDOM from 'react-dom'
import gsap from 'gsap'
import { apiKeysApi } from '../api/apiKeys'
import ConfirmModal from '../components/ConfirmModal'
import { addAppNotification } from '../utils/notifications'

export default function ApiKeysPage() {
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusMsg, setStatusMsg] = useState(null)

  // Modal Create
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [keyName, setKeyName] = useState('')
  const [creating, setCreating] = useState(false)

  // Modal Created Secret View (Show once)
  const [newlyCreatedKey, setNewlyCreatedKey] = useState(null)
  const [copiedKey, setCopiedKey] = useState(false)

  // Modal Delete / Revoke
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const headerRef = useRef(null)
  const tableCardRef = useRef(null)

  useEffect(() => {
    fetchKeys()
  }, [])

  useLayoutEffect(() => {
    if (headerRef.current) {
      gsap.fromTo(
        headerRef.current.children,
        { opacity: 0, x: -16 },
        { opacity: 1, x: 0, duration: 0.5, stagger: 0.08, ease: 'power2.out', clearProps: 'all' }
      )
    }
  }, [loading])

  async function fetchKeys() {
    const startTime = Date.now()
    try {
      setLoading(true)
      const res = await apiKeysApi.list()
      setKeys(res.data || [])
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal memuat daftar API Key dari server.' })
    } finally {
      const elapsed = Date.now() - startTime
      setTimeout(() => setLoading(false), Math.max(0, 200 - elapsed))
    }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!keyName || !keyName.trim()) {
      setStatusMsg({ type: 'error', text: 'Nama aplikasi / klien pemanggil wajib diisi.' })
      return
    }

    setCreating(true)
    setStatusMsg(null)
    try {
      const res = await apiKeysApi.create(keyName.trim())
      setShowCreateModal(false)
      setKeyName('')
      setNewlyCreatedKey(res.data)
      await fetchKeys()
      addAppNotification({
        title: 'Manajemen Kunci API',
        message: `Kunci API "${res.data.name}" berhasil dibuat.`,
        type: 'system',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({
        type: 'error',
        text: err.response?.data?.message || 'Gagal membuat API Key baru.',
      })
    } finally {
      setCreating(false)
    }
  }

  const handleToggle = async (key) => {
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

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await apiKeysApi.delete(deleteTarget.id)
      setKeys((prev) => prev.filter((k) => k.id !== deleteTarget.id))
      setDeleteTarget(null)
      addAppNotification({
        title: 'Kunci API Dicabut',
        message: `Kunci API "${deleteTarget.name}" telah dihapus permanen.`,
        type: 'system',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal menghapus API Key.' })
    } finally {
      setDeleting(false)
    }
  }

  const handleCopySecret = (secret) => {
    navigator.clipboard.writeText(secret)
    setCopiedKey(true)
    setTimeout(() => setCopiedKey(false), 2000)
  }

  if (loading) {
    return (
      <div className="p-4 sm:p-5 max-w-7xl mx-auto space-y-4">
        <div className="p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs space-y-2">
          <div className="skeleton h-6 w-64 rounded-md" />
          <div className="skeleton h-4 w-96 rounded-md" />
        </div>
        <div className="p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs space-y-3">
          <div className="skeleton h-10 w-full rounded-lg" />
          <div className="skeleton h-64 w-full rounded-lg" />
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-5 max-w-7xl mx-auto space-y-4 pb-20 relative">
      {/* ── TOP HEADER BANNER ───────────────────────────────────── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs">
        <div ref={headerRef} className="space-y-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl sm:text-2xl font-bold text-[var(--text-primary)] tracking-tight">
              Manajemen Kunci API
            </h1>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-[var(--bg-input)] text-sky-600 dark:text-sky-400 border border-[var(--border-color)]">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-500" />
              Public API Gateway
            </div>
          </div>
          <p className="text-xs sm:text-sm text-[var(--text-secondary)]">
            Buat dan kelola token autentikasi (Bearer Token) untuk menghubungkan WhatsApp Bot, Portal Web, dan sistem eksternal ke mesin RAG.
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0 self-start lg:self-auto">
          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 rounded-lg text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white transition-colors cursor-pointer flex items-center gap-2 shadow-xs"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            <span>Buat Kunci API Baru</span>
          </button>
        </div>
      </div>

      {/* ── NOTIFICATION TOAST ─────────────────────────────────── */}
      {statusMsg && (
        <div
          className={`px-4 py-3 rounded-lg text-xs font-medium flex items-center justify-between transition-all border ${
            statusMsg.type === 'success'
              ? 'bg-[var(--bg-input)] text-emerald-600 dark:text-emerald-400 border-[var(--border-color)]'
              : 'bg-[var(--bg-input)] text-rose-600 dark:text-rose-400 border-[var(--border-color)]'
          }`}
        >
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {statusMsg.type === 'success' ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              )}
            </svg>
            <span>{statusMsg.text}</span>
          </div>
          <button
            type="button"
            onClick={() => setStatusMsg(null)}
            className="text-inherit opacity-60 hover:opacity-100 p-1 cursor-pointer"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* ── TABLE CARD ─────────────────────────────────────────── */}
      <div
        ref={tableCardRef}
        className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs overflow-hidden"
      >
        <div className="p-4 sm:p-5 border-b border-[var(--border-color)] flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-[var(--text-primary)]">
              Daftar Kunci Akses Aktif
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Setiap request dari sistem luar wajib menyertakan token ini pada header <code>Authorization: Bearer &lt;API_KEY&gt;</code>.
            </p>
          </div>
          <span className="text-xs font-mono font-semibold px-2.5 py-1 rounded-md bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)]">
            Total: {keys.length} Token
          </span>
        </div>

        {keys.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <div className="w-12 h-12 mx-auto rounded-full bg-[var(--bg-input)] border border-[var(--border-color)] flex items-center justify-center text-[var(--text-muted)]">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" />
              </svg>
            </div>
            <p className="text-xs font-semibold text-[var(--text-primary)]">Belum ada Kunci API yang dibuat</p>
            <p className="text-xs text-[var(--text-muted)] max-w-sm mx-auto">
              Klik tombol "Buat Kunci API Baru" untuk mengizinkan aplikasi eksternal (seperti WhatsApp Gateway atau Portal Web) mengakses data RAG.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[var(--border-color)] bg-[var(--bg-input)] text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  <th className="py-3 px-4">Nama Kunci / Aplikasi</th>
                  <th className="py-3 px-4">Token Akses</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Terakhir Digunakan</th>
                  <th className="py-3 px-4">Dibuat Pada</th>
                  <th className="py-3 px-4 text-right">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)] text-xs text-[var(--text-primary)]">
                {keys.map((key) => (
                  <tr key={key.id} className="hover:bg-[var(--bg-input)] transition-colors">
                    <td className="py-3.5 px-4 font-semibold">
                      {key.name}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs text-[var(--text-secondary)]">
                      {key.masked_key}
                    </td>
                    <td className="py-3.5 px-4">
                      <button
                        type="button"
                        onClick={() => handleToggle(key)}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border transition-colors cursor-pointer ${
                          key.is_active
                            ? 'bg-[var(--bg-card)] text-emerald-600 dark:text-emerald-400 border-[var(--border-color)] hover:bg-[var(--bg-input)]'
                            : 'bg-[var(--bg-input)] text-[var(--text-muted)] border-[var(--border-color)] hover:bg-[var(--border-color)]'
                        }`}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full ${key.is_active ? 'bg-emerald-500' : 'bg-zinc-400'}`} />
                        <span>{key.is_active ? 'Aktif' : 'Nonaktif'}</span>
                      </button>
                    </td>
                    <td className="py-3.5 px-4 text-xs text-[var(--text-muted)]">
                      {key.last_used_at ? new Date(key.last_used_at).toLocaleString('id-ID') : 'Belum pernah'}
                    </td>
                    <td className="py-3.5 px-4 text-xs text-[var(--text-muted)]">
                      {new Date(key.created_at).toLocaleDateString('id-ID')}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => setDeleteTarget(key)}
                        className="p-1.5 text-zinc-400 hover:text-rose-500 hover:bg-[var(--bg-input)] rounded-lg transition-colors cursor-pointer"
                        title="Cabut & Hapus Kunci API"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── MODAL: BUAT KUNCI API (PORTAL KE DOCUMENT.BODY) ────── */}
      {showCreateModal &&
        ReactDOM.createPortal(
          <div className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in">
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl max-w-md w-full p-5 shadow-xl space-y-4">
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Buat Kunci API Baru
                </h3>
                <p className="text-xs text-[var(--text-muted)]">
                  Beri nama identifikasi untuk aplikasi atau layanan yang akan menggunakan kunci ini.
                </p>
              </div>

              <form noValidate onSubmit={handleCreate} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[var(--text-primary)] block">
                    Nama Aplikasi / Klien Pemanggil
                  </label>
                  <input
                    type="text"
                    value={keyName}
                    onChange={(e) => setKeyName(e.target.value)}
                    placeholder="Contoh: Portal Web Resmi Dinas, WhatsApp Bot Gateway, CRM Helpdesk"
                    autoFocus
                    className="w-full px-3.5 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors"
                  />
                </div>

                <div className="flex justify-end gap-2.5 pt-2 border-t border-[var(--border-color)]">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    disabled={creating}
                    className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-input)] transition-colors cursor-pointer"
                  >
                    Batal
                  </button>
                  <button
                    type="submit"
                    disabled={creating || !keyName.trim()}
                    className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white transition-colors cursor-pointer shadow-xs flex items-center gap-1.5"
                  >
                    {creating ? (
                      <>
                        <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        <span>Membuat...</span>
                      </>
                    ) : (
                      <span>Buat Token</span>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>,
          document.body
        )}

      {/* ── MODAL: KUNCI RAHASIA DITAMPILKAN SEKALI (PORTAL KE DOCUMENT.BODY) ── */}
      {newlyCreatedKey &&
        ReactDOM.createPortal(
          <div className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in">
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl max-w-lg w-full p-5 shadow-2xl space-y-4">
              <div className="space-y-1">
                <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-[var(--bg-input)] text-emerald-600 dark:text-emerald-400 border border-[var(--border-color)] mb-1">
                  Kunci API Berhasil Dibuat
                </div>
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Simpan Kunci API "{newlyCreatedKey.name}"
                </h3>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  Harap salin dan simpan kunci rahasia ini sekarang. Demi alasan keamanan, token lengkap <strong>hanya ditampilkan satu kali</strong> dan tidak dapat dilihat kembali setelah jendela ini ditutup.
                </p>
              </div>

              <div className="relative p-3.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] font-mono text-xs text-[var(--text-primary)] break-all select-all flex items-center justify-between gap-3">
                <span>{newlyCreatedKey.plain_key}</span>
                <button
                  type="button"
                  onClick={() => handleCopySecret(newlyCreatedKey.plain_key)}
                  className="shrink-0 px-3 py-1.5 rounded-md text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white transition-colors cursor-pointer flex items-center gap-1.5 shadow-xs"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    {copiedKey ? (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                    ) : (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                    )}
                  </svg>
                  <span>{copiedKey ? 'Tersalin' : 'Salin Token'}</span>
                </button>
              </div>

              <div className="p-3 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-amber-700 dark:text-amber-400 space-y-1">
                <span className="font-bold">Perhatian:</span>
                <p className="leading-relaxed">
                  Jangan bagikan token ini di repositori kode publik. Sertakan token pada header HTTP <code>Authorization: Bearer &lt;API_KEY&gt;</code> saat memanggil endpoint <code>POST /api/v1/chat</code>.
                </p>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={() => setNewlyCreatedKey(null)}
                  className="px-4 py-2 rounded-lg text-xs font-semibold bg-[var(--bg-input)] hover:bg-[var(--border-color)] text-[var(--text-primary)] border border-[var(--border-color)] transition-colors cursor-pointer"
                >
                  Saya Sudah Menyimpan Token Ini
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}

      {/* ── MODAL: KONFIRMASI HAPUS / CABUT ─────────────────────── */}
      <ConfirmModal
        isOpen={Boolean(deleteTarget)}
        title="Cabut Kunci API?"
        message={`Apakah Anda yakin ingin mencabut dan menghapus Kunci API "${deleteTarget?.name}"? Aplikasi atau layanan yang menggunakan kunci ini akan langsung ditolak aksesnya.`}
        confirmText="Ya, Cabut Kunci"
        cancelText="Batal"
        danger={true}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
