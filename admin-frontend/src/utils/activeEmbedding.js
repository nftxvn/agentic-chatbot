const STORAGE_KEY = 'active_embeddings';

/**
 * Mendapatkan daftar embedding dokumen yang sedang berjalan di background.
 * Otomatis membersihkan entri yang berusia lebih dari 15 menit (failsafe).
 */
export function getActiveEmbeddings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const list = JSON.parse(raw);
    if (!Array.isArray(list)) return [];
    
    const now = Date.now();
    const valid = list.filter((item) => now - (item.startedAt || 0) < 15 * 60 * 1000);
    if (valid.length !== list.length) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(valid));
    }
    return valid;
  } catch (err) {
    console.error('Failed to get active embeddings:', err);
    return [];
  }
}

/**
 * Daftarkan proses embedding dokumen untuk dipantau di background.
 */
export function trackActiveEmbedding({ documentId, title }) {
  try {
    const current = getActiveEmbeddings();
    const idNum = Number(documentId);
    const filtered = current.filter((item) => Number(item.documentId) !== idNum);
    const updated = [
      ...filtered,
      {
        documentId: idNum,
        title: title || `Dokumen #${idNum}`,
        startedAt: Date.now(),
      },
    ];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    window.dispatchEvent(new CustomEvent('app-active-embeddings-changed'));
  } catch (err) {
    console.error('Failed to track active embedding:', err);
  }
}

/**
 * Hapus pendaftaran embedding dokumen setelah selesai atau gagal.
 */
export function clearActiveEmbedding(documentId) {
  try {
    const current = getActiveEmbeddings();
    const idNum = Number(documentId);
    const updated = current.filter((item) => Number(item.documentId) !== idNum);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    window.dispatchEvent(new CustomEvent('app-active-embeddings-changed'));
  } catch (err) {
    console.error('Failed to clear active embedding:', err);
  }
}
