import { useState } from "react";
import { documentsApi } from "../../api/documents";
import { categoriesApi } from "../../api/categories";
import { getWhatsappSettings } from "../../api/settings";

/** State notifikasi, pemetaan aktivitas, dan tindakan baca/hapus notifikasi lokal. */
export function useAdminNotifications({ formatRelativeTime }) {
  const [isNotificationOpen, setIsNotificationOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);

  const [readIds, setReadIds] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("read_notifications") || "[]");
    } catch {
      return [];
    }
  });

  const [clearedIds, setClearedIds] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("cleared_notifications") || "[]");
    } catch {
      return [];
    }
  });

  const fetchRealNotifications = async () => {
    try {
      const docRes = await documentsApi.list(1).catch(() => null);
      const docs = docRes?.data?.documents || docRes?.documents || [];

      const catRes = await categoriesApi.list().catch(() => null);
      const cats = catRes?.data || catRes || [];

      const waRes = await getWhatsappSettings().catch(() => null);

      const realList = [];

      docs.forEach((doc) => {
        const docTime = doc.processed_at || doc.updated_at || doc.created_at;
        const timeMs = docTime ? new Date(docTime).getTime() : 0;

        if (doc.status === "completed") {
          realList.push({
            id: `doc-${doc.id}-completed-${timeMs}`,
            title: `Dokumen "${doc.title}" Ter-index`,
            message: `Dokumen ${doc.original_filename || doc.original_name || ""} (${doc.total_chunks || 0} chunks) siap digunakan AI.`,
            time: formatRelativeTime(docTime),
            timestamp: timeMs,
            type: "success",
            documentId: doc.id,
          });
        } else if (doc.status === "processing") {
          realList.push({
            id: `doc-${doc.id}-processing-${timeMs}`,
            title: `Memproses "${doc.title}"`,
            message: `Proses ekstraksi RAG & OCR sedang berjalan ke ChromaDB.`,
            time: formatRelativeTime(docTime),
            timestamp: timeMs,
            type: "info",
            documentId: doc.id,
          });
        } else if (doc.status === "failed") {
          realList.push({
            id: `doc-${doc.id}-failed-${timeMs}`,
            title: `Gagal Memproses Dokumen`,
            message: `Dokumen "${doc.title}" mengalami kesalahan saat di-index.`,
            time: formatRelativeTime(docTime),
            timestamp: timeMs,
            type: "error",
            documentId: doc.id,
          });
        }
      });

      if (waRes) {
        realList.push({
          id: "wa-status-notification",
          title: `WhatsApp Bot ${waRes.wa_status ? "Aktif" : "Nonaktif"}`,
          message: waRes.wa_status
            ? `Layanan otomatis WhatsApp Diskominfo (${waRes.wa_phone_number || "API Connected"}) siap melayani masyarakat.`
            : `Layanan WhatsApp Bot saat ini dinonaktifkan di sistem.`,
          time: "Realtime",
          timestamp: Date.now(),
          type: waRes.wa_status ? "system" : "warning",
        });
      }

      if (cats && (cats.length > 0 || (cats.data && cats.data.length > 0))) {
        const catList = cats.data || cats;
        catList.forEach((cat) => {
          const catTime = cat.updated_at || cat.created_at;
          realList.push({
            id: `cat-${cat.id}-added`,
            title: `Kategori AI Baru`,
            message: `Anda baru saja menambahkan kategori "${cat.name}"`,
            time: formatRelativeTime(catTime),
            timestamp: catTime ? new Date(catTime).getTime() : 0,
            type: "info",
          });
        });
      }

      const actionLogs = JSON.parse(
        localStorage.getItem("action_notifications") || "[]",
      );
      const formattedActions = actionLogs.map((item) => ({
        ...item,
        time: formatRelativeTime(item.timestamp),
      }));

      // Identifikasi ID dokumen yang baru saja diproses via tindakan pengguna dalam 5 menit terakhir
      const recentActionDocIds = new Set(
        actionLogs
          .filter((a) => Date.now() - (a.timestamp || 0) < 300000)
          .map((a) => a.documentId)
          .filter(Boolean),
      );

      // Saring realList agar tidak duplikat dengan riwayat aksi pengguna yang baru saja terjadi
      const filteredRealList = realList.filter(
        (item) => !item.documentId || !recentActionDocIds.has(item.documentId),
      );

      // Gabungkan dan urutkan berdasarkan waktu terbaru ke terlama
      const combined = [...formattedActions, ...filteredRealList].sort((a, b) => {
        const timeA = typeof a.timestamp === "number" ? a.timestamp : new Date(a.timestamp || 0).getTime();
        const timeB = typeof b.timestamp === "number" ? b.timestamp : new Date(b.timestamp || 0).getTime();
        return timeB - timeA;
      });

      const savedReadIds = JSON.parse(
        localStorage.getItem("read_notifications") || "[]",
      );
      const savedClearedIds = JSON.parse(
        localStorage.getItem("cleared_notifications") || "[]",
      );

      // Filter out cleared items & limit to top 15 most recent notifications
      const visibleList = combined
        .filter((item) => !savedClearedIds.includes(item.id))
        .slice(0, 15)
        .map((item) => ({
          ...item,
          unread: !savedReadIds.includes(item.id),
        }));

      setNotifications(visibleList);
    } catch (err) {
      console.error("Failed to fetch real notifications:", err);
    }
  };

  const unreadCount = notifications.filter((n) => n.unread).length;

  const markAllAsRead = () => {
    const allIds = notifications.map((n) => n.id);
    localStorage.setItem("read_notifications", JSON.stringify(allIds));
    setReadIds(allIds);
    setNotifications((prev) => prev.map((n) => ({ ...n, unread: false })));
  };

  const clearAllNotifications = () => {
    const allCurrentIds = notifications.map((n) => n.id);
    const updatedCleared = Array.from(
      new Set([...clearedIds, ...allCurrentIds]),
    );
    localStorage.setItem(
      "cleared_notifications",
      JSON.stringify(updatedCleared),
    );
    setClearedIds(updatedCleared);
    setNotifications([]);
  };

  const markAsRead = (id) => {
    const updated = [...readIds, id];
    localStorage.setItem("read_notifications", JSON.stringify(updated));
    setReadIds(updated);
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, unread: false } : n)),
    );
  };

  return {
    isNotificationOpen,
    setIsNotificationOpen,
    notifications,
    fetchRealNotifications,
    unreadCount,
    markAllAsRead,
    clearAllNotifications,
    markAsRead,
  };
}
