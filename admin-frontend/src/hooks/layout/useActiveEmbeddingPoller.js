import { useEffect } from "react";
import { getActiveEmbeddings, clearActiveEmbedding } from "../../utils/activeEmbedding";
import { documentsApi } from "../../api/documents";
import { addAppNotification } from "../../utils/notifications";

/** Poller embedding latar belakang dan dispatch event penyelesaian/kegagalan. */
export function useActiveEmbeddingPoller({ searchIndexData, fetchRealNotifications }) {
  // Background Poller for Active Embeddings (berjalan terus meskipun dialog ditutup)
  useEffect(() => {
    let pollerTimer = null;
    let isChecking = false;

    const checkActiveEmbeddings = async () => {
      if (isChecking) return;
      const activeList = getActiveEmbeddings();
      if (!activeList || activeList.length === 0) return;

      isChecking = true;
      try {
        for (const item of activeList) {
          try {
            const res = await documentsApi.getExtractionStatus(item.documentId);
            const data = res?.data || res;
            if (!data) continue;

            const currentStatus = data.status;
            const currentPersen = typeof data.persen === "number" ? data.persen : 0;
            const elapsed = Date.now() - (item.startedAt || 0);

            // Tugas embedding HANYA selesai jika:
            // 1. Persentase sudah mencapai 100%
            // 2. Atau status 'selesai'/'completed' dengan persen >= 95% setelah lewat minimal 2,5 detik
            const isCompleted =
              currentPersen >= 100 ||
              ((currentStatus === "selesai" || currentStatus === "completed") &&
                currentPersen >= 95 &&
                elapsed > 2500);

            if (isCompleted) {
              clearActiveEmbedding(item.documentId);

              // Ambil judul asli dokumen jika item.title masih berupa fallback generic
              const fallbackDoc = searchIndexData.documents?.find(
                (d) => Number(d.id) === Number(item.documentId),
              );
              const displayTitle =
                item.title && !item.title.startsWith("Dokumen #")
                  ? item.title
                  : (fallbackDoc?.title || fallbackDoc?.original_name || item.title || `Dokumen #${item.documentId}`);

              // Ekstrak jumlah chunk dari pesan worker (misal "Selesai! 15 vektor berhasil disimpan...")
              const chunkMatch = data.pesan?.match(/(\d+)\s+vektor/i);
              const chunkCount = chunkMatch ? chunkMatch[1] : (data.total_chunks || fallbackDoc?.total_chunks || "");
              const chunkText = chunkCount ? `${chunkCount} chunks` : "seluruh chunks";

              addAppNotification({
                title: "Penyimpanan Korpus Berhasil",
                message: `Vektor dokumen "${displayTitle}" (${chunkText}) berhasil disimpan ke ChromaDB. Siap digunakan AI.`,
                type: "success",
                documentId: item.documentId,
              });
              window.dispatchEvent(
                new CustomEvent("document-embedded-success", {
                  detail: { documentId: item.documentId, data },
                }),
              );
              fetchRealNotifications();
            } else if (currentStatus === "gagal" || currentStatus === "failed") {
              clearActiveEmbedding(item.documentId);
              const fallbackDoc = searchIndexData.documents?.find(
                (d) => Number(d.id) === Number(item.documentId),
              );
              const displayTitle =
                item.title && !item.title.startsWith("Dokumen #")
                  ? item.title
                  : (fallbackDoc?.title || fallbackDoc?.original_name || item.title || `Dokumen #${item.documentId}`);
              const errMsg = data.pesan || "Terjadi kesalahan saat memproses embedding.";
              addAppNotification({
                title: "Gagal Menyimpan Korpus",
                message: `Gagal menyimpan korpus untuk dokumen "${displayTitle}": ${errMsg}`,
                type: "error",
                documentId: item.documentId,
              });
              window.dispatchEvent(
                new CustomEvent("document-embedded-failed", {
                  detail: { documentId: item.documentId, error: errMsg },
                }),
              );
              fetchRealNotifications();
            }
          } catch (itemErr) {
            // Abaikan kesalahan koneksi sementara saat polling
          }
        }
      } finally {
        isChecking = false;
      }
    };

    checkActiveEmbeddings();
    pollerTimer = setInterval(checkActiveEmbeddings, 2000);

    const handleActiveChanged = () => {
      checkActiveEmbeddings();
    };

    window.addEventListener("app-active-embeddings-changed", handleActiveChanged);

    return () => {
      if (pollerTimer) clearInterval(pollerTimer);
      window.removeEventListener("app-active-embeddings-changed", handleActiveChanged);
    };
  }, []);
}
