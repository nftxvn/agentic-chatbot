import { useState, useEffect, useRef } from "react";
import { documentsApi } from "../../api/documents";

/**
 * Data detail dokumen dan chunk. Polling 4 detik berjalan hanya selama proses
 * aktif; kegagalan polling setelah dokumen termuat tidak mengosongkan editor.
 * Halaman tetap memiliki toast, animasi, layout editor, dan tindakan mutasi.
 */
export function useDocumentDetail(id) {
  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [chunks, setChunks] = useState([]);
  const [loadingChunks, setLoadingChunks] = useState(false);

  const isMounted = useRef(true);
  const fetchTimeout = useRef(null);
  const docLoadedRef = useRef(false);

  const fetchDocument = async () => {
    try {
      const res = await documentsApi.get(id);
      if (!isMounted.current) return;
      const doc = res.data.document;
      setDocument(doc);
      docLoadedRef.current = true;
      setError(null);

      // Keep polling if processing or waiting for pause to complete on active page
      if (
        doc.status === "processing" ||
        doc.status === "pending" ||
        doc.ekstraksi_status === "berjalan" ||
        doc.ekstraksi_status === "antre" ||
        doc.jeda_diminta
      ) {
        if (fetchTimeout.current) clearTimeout(fetchTimeout.current);
        fetchTimeout.current = setTimeout(fetchDocument, 4000);
      }
    } catch (err) {
      if (!isMounted.current) return;
      if (!docLoadedRef.current) {
        setError(err.response?.data?.message || "Gagal memuat detail dokumen.");
      } else {
        // Resilient retry: don't blank out active editor on a single background poll glitch
        if (fetchTimeout.current) clearTimeout(fetchTimeout.current);
        fetchTimeout.current = setTimeout(fetchDocument, 4000);
      }
    } finally {
      if (isMounted.current) setLoading(false);
    }
  };

  const fetchChunks = async () => {
    setLoadingChunks(true);
    try {
      const res = await documentsApi.getChunks(id);
      if (!isMounted.current) return;
      setChunks(res.chunks || res.data?.chunks || []);
    } catch (err) {
      if (!isMounted.current) return;
      console.error("Gagal memuat chunks", err);
      setChunks([]);
    } finally {
      if (isMounted.current) setLoadingChunks(false);
    }
  };

  useEffect(() => {
    isMounted.current = true;
    fetchDocument();
    return () => {
      isMounted.current = false;
      if (fetchTimeout.current) clearTimeout(fetchTimeout.current);
    };
  }, [id]);

  return {
    document,
    loading,
    error,
    chunks,
    loadingChunks,
    fetchDocument,
    fetchChunks,
  };
}
