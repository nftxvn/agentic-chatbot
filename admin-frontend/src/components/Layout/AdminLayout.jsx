import { useState, useEffect, useRef, useMemo } from "react";
import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import gsap from "gsap";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../context/ThemeContext";
import ConfirmModal from "../ConfirmModal";
import komdigiLogo from "../../assets/komdigi-logo.svg";
import bandaAcehLogo from "../../assets/banda-aceh-logo.svg";
import { documentsApi } from "../../api/documents";
import { categoriesApi } from "../../api/categories";
import { getWhatsappSettings } from "../../api/settings";
import { getActiveEmbeddings, clearActiveEmbedding } from "../../utils/activeEmbedding";
import { addAppNotification } from "../../utils/notifications";
import SettingsModal from "../Settings/SettingsModal";
import { SystemHealthIndicator } from "../UI/SystemHealthIndicator";

function formatRelativeTime(dateString) {
  if (!dateString) return "Baru saja";
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return "Baru saja";
  const diffSec = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diffSec < 60) return "Baru saja";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} menit lalu`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} jam lalu`;
  return `${Math.floor(diffSec / 86400)} hari lalu`;
}

const NAV_ITEMS = [
  {
    to: "/dashboard",
    label: "Dashboard",
    icon: (
      <svg
        className="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.75}
          d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"
        />
      </svg>
    ),
  },
  {
    to: "/categories",
    label: "Kategori",
    icon: (
      <svg
        className="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.75}
          d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z"
        />
      </svg>
    ),
  },
  {
    to: "/live-chat",
    label: "Live Chat & Tiket",
    icon: (
      <svg
        className="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.75}
          d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a.75.75 0 01-.774-.823l.235-2.115C3.301 16.597 2.25 14.43 2.25 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
        />
      </svg>
    ),
  },
  {
    to: "/settings/chatbot",
    label: "Chatbot & RAG",
    icon: (
      <svg
        className="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.75}
          d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a.75.75 0 01-.774-.823l.235-2.115C3.301 16.597 2.25 14.43 2.25 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
        />
      </svg>
    ),
  },
  {
    to: "/integrations",
    label: "Integrasi",
    icon: (
      <svg
        className="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.75}
          d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244"
        />
      </svg>
    ),
  },
  {
    to: "/monitoring",
    label: "Monitoring",
    icon: (
      <svg
        className="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.75}
          d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
        />
      </svg>
    ),
  },
];

const QUICK_FEATURES = [
  {
    id: "f-dashboard",
    label: "Dashboard",
    desc: "Ringkasan dokumen RAG & statistik pengindeksan",
    to: "/dashboard",
  },
  {
    id: "f-categories",
    label: "Kategori",
    desc: "Kelola profil OCR, prompt ekstraksi & variabel dokumen",
    to: "/categories",
  },
  {
    id: "f-live-chat",
    label: "Live Chat & Tiket",
    desc: "Balas pesan percakapan warga yang dialihkan (Human Handoff) secara langsung",
    to: "/live-chat",
  },
  {
    id: "f-chatbot",
    label: "Chatbot & RAG",
    desc: "Editor prompt, tuning parameter RAG, live chat testing & chunk inspector",
    to: "/settings/chatbot",
  },
  {
    id: "f-integrations",
    label: "Integrasi",
    desc: "Kelola kunci API, bot WhatsApp, Telegram & webhook",
    to: "/integrations",
  },
  {
    id: "f-monitoring",
    label: "Monitoring",
    desc: "Telemetri kueri layanan, beban latensi, utilisasi GPU VRAM & status runtime Ollama",
    to: "/monitoring",
  },
];

export default function AdminLayout() {
  const { user, logout, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem("sidebar_collapsed") === "true";
    } catch {
      return false;
    }
  });

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("sidebar_collapsed", String(next));
      } catch {}
      return next;
    });
  };

  // Global Keyboard Shortcut: Ctrl + B / Cmd + B to toggle sidebar
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === "b" || e.key === "B")) {
        e.preventDefault();
        toggleSidebar();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const [showLogoutModal, setShowLogoutModal] = useState(false);
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

  // Search System States & Optimization
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchIndexData, setSearchIndexData] = useState({
    documents: [],
    categories: [],
  });

  const { theme, toggleTheme, isDark } = useTheme();
  const isDarkMode = isDark;

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const userMenuRef = useRef(null);
  const userMenuDropdownRef = useRef(null);
  const isUserMenuClosingRef = useRef(false);

  // Settings Modal State
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [activeSettingsTab, setActiveSettingsTab] = useState("profile"); // 'profile' | 'security' | 'preferences'

  const wrapperRef = useRef(null);
  const sidebarRef = useRef(null);
  const mainRef = useRef(null);
  const progressBarRef = useRef(null);
  const notificationRef = useRef(null);
  const dropdownRef = useRef(null);
  const contentRef = useRef(null);
  const navRef = useRef(null);
  const navItemsRef = useRef([]);
  const activePillRef = useRef(null);
  const searchContainerRef = useRef(null);
  const searchIconRef = useRef(null);
  const searchCardRef = useRef(null);

  // Pre-fetch search index asynchronously in background
  useEffect(() => {
    let isMounted = true;
    const prepareSearchIndex = async () => {
      try {
        const [docRes, catRes] = await Promise.all([
          documentsApi.list(1).catch(() => null),
          categoriesApi.list().catch(() => null),
        ]);
        if (!isMounted) return;
        const docs = docRes?.data?.documents || docRes?.documents || [];
        const cats = catRes?.data || catRes || [];
        setSearchIndexData({
          documents: docs,
          categories: Array.isArray(cats) ? cats : cats.data || [],
        });
      } catch (e) {
        console.error("Failed to prepare search index", e);
      }
    };
    prepareSearchIndex();
    return () => {
      isMounted = false;
    };
  }, [location.pathname]);

  // Fast In-Memory Search Filtering
  const filteredSearchResults = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) {
      return {
        features: QUICK_FEATURES,
        documents: searchIndexData.documents.slice(0, 4),
        categories: searchIndexData.categories.slice(0, 3),
      };
    }

    const matchedFeatures = QUICK_FEATURES.filter(
      (f) =>
        f.label.toLowerCase().includes(q) || f.desc.toLowerCase().includes(q),
    );

    const matchedDocs = searchIndexData.documents
      .filter(
        (doc) =>
          (doc.title && doc.title.toLowerCase().includes(q)) ||
          (doc.original_filename &&
            doc.original_filename.toLowerCase().includes(q)) ||
          (doc.category_name && doc.category_name.toLowerCase().includes(q)),
      )
      .slice(0, 5);

    const matchedCats = searchIndexData.categories
      .filter(
        (cat) =>
          (cat.name && cat.name.toLowerCase().includes(q)) ||
          (cat.description && cat.description.toLowerCase().includes(q)),
      )
      .slice(0, 4);

    return {
      features: matchedFeatures,
      documents: matchedDocs,
      categories: matchedCats,
    };
  }, [searchQuery, searchIndexData]);

  const isSearchClosingRef = useRef(false);

  const closeSearch = () => {
    if (isSearchClosingRef.current) return;
    if (searchCardRef.current) {
      isSearchClosingRef.current = true;
      gsap.killTweensOf(searchCardRef.current);
      gsap.to(searchCardRef.current, {
        opacity: 0,
        scale: 0.85,
        y: -14,
        duration: 0.22,
        ease: "power2.in",
        onComplete: () => {
          setIsSearchOpen(false);
          isSearchClosingRef.current = false;
        },
      });
    } else {
      setIsSearchOpen(false);
    }
  };

  // GSAP animation for Search Dropdown Card (Spring back.out interaction identical to Notification)
  useEffect(() => {
    if (isSearchOpen && searchCardRef.current) {
      isSearchClosingRef.current = false;
      gsap.killTweensOf(searchCardRef.current);
      gsap.fromTo(
        searchCardRef.current,
        { opacity: 0, scale: 0.85, y: -14, transformOrigin: "top center" },
        { opacity: 1, scale: 1, y: 0, duration: 0.38, ease: "back.out(1.7)" },
      );
    }
  }, [isSearchOpen]);

  const closeUserMenu = () => {
    if (isUserMenuClosingRef.current) return;
    if (userMenuDropdownRef.current) {
      isUserMenuClosingRef.current = true;
      gsap.killTweensOf(userMenuDropdownRef.current);
      gsap.to(userMenuDropdownRef.current, {
        opacity: 0,
        scale: 0.85,
        y: -14,
        duration: 0.22,
        ease: "power2.in",
        onComplete: () => {
          setIsUserMenuOpen(false);
          isUserMenuClosingRef.current = false;
        },
      });
    } else {
      setIsUserMenuOpen(false);
    }
  };

  const toggleUserMenu = () => {
    if (isUserMenuOpen) {
      closeUserMenu();
    } else {
      isUserMenuClosingRef.current = false;
      setIsUserMenuOpen(true);
    }
  };

  // GSAP animation for User Profile Dropdown Menu (Spring back.out interaction)
  useEffect(() => {
    if (isUserMenuOpen && userMenuDropdownRef.current) {
      isUserMenuClosingRef.current = false;
      gsap.killTweensOf(userMenuDropdownRef.current);
      gsap.fromTo(
        userMenuDropdownRef.current,
        { opacity: 0, scale: 0.85, y: -14, transformOrigin: "top right" },
        { opacity: 1, scale: 1, y: 0, duration: 0.38, ease: "back.out(1.7)" },
      );
    }
  }, [isUserMenuOpen]);

  // GSAP Smooth Route Transition Animation on Menu Switch
  useEffect(() => {
    if (!contentRef.current) return;

    gsap.killTweensOf(contentRef.current);
    gsap.fromTo(
      contentRef.current,
      {
        opacity: 0,
        scale: 0.99,
      },
      {
        opacity: 1,
        scale: 1,
        duration: 0.35,
        ease: "power2.out",
        clearProps: "all",
      },
    );
  }, [location.pathname]);

  // GSAP Fluid Active Menu Highlight Pill Slider
  const updateActivePill = (animate = true) => {
    if (authLoading) return;
    const activeIndex = NAV_ITEMS.findIndex((item) => {
      if (item.to === "/dashboard")
        return location.pathname === "/dashboard" || location.pathname === "/";
      return location.pathname.startsWith(item.to);
    });

    if (
      activeIndex !== -1 &&
      navItemsRef.current[activeIndex] &&
      activePillRef.current
    ) {
      const targetEl = navItemsRef.current[activeIndex];
      const top = targetEl.offsetTop;
      const height = targetEl.offsetHeight;
      const left = targetEl.offsetLeft;
      const width = targetEl.offsetWidth;

      if (animate) {
        gsap.killTweensOf(activePillRef.current);
        gsap.to(activePillRef.current, {
          top,
          height,
          left,
          width,
          opacity: 1,
          duration: 0.45,
          ease: "power3.out",
        });
      } else {
        gsap.set(activePillRef.current, {
          top,
          height,
          left,
          width,
          opacity: 1,
        });
      }
    } else if (activePillRef.current) {
      gsap.to(activePillRef.current, { opacity: 0, duration: 0.2 });
    }
  };

  // Smooth GSAP slide between routes
  useEffect(() => {
    updateActivePill(true);
  }, [location.pathname, authLoading]);

  // Continuous tracking during sidebar expand/collapse transition (550ms)
  useEffect(() => {
    let animationFrameId;
    const startTime = performance.now();
    const duration = 550;

    const trackPill = (currentTime) => {
      const elapsed = currentTime - startTime;
      updateActivePill(false);
      if (elapsed < duration) {
        animationFrameId = requestAnimationFrame(trackPill);
      } else {
        updateActivePill(false);
      }
    };

    animationFrameId = requestAnimationFrame(trackPill);
    return () => cancelAnimationFrame(animationFrameId);
  }, [isSidebarCollapsed]);

  // Resize handler to maintain exact position
  useEffect(() => {
    const handleResize = () => updateActivePill(false);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // GSAP animation for Notification Dropdown (Spring back.out interaction)
  useEffect(() => {
    if (isNotificationOpen && dropdownRef.current) {
      gsap.killTweensOf(dropdownRef.current);
      gsap.fromTo(
        dropdownRef.current,
        { opacity: 0, scale: 0.85, y: -14, transformOrigin: "top right" },
        { opacity: 1, scale: 1, y: 0, duration: 0.38, ease: "back.out(1.7)" },
      );
    }
  }, [isNotificationOpen]);

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

  useEffect(() => {
    fetchRealNotifications();
    const interval = setInterval(fetchRealNotifications, 10000);

    const handleUpdateEvent = () => fetchRealNotifications();
    window.addEventListener("app-notification-update", handleUpdateEvent);

    return () => {
      clearInterval(interval);
      window.removeEventListener("app-notification-update", handleUpdateEvent);
    };
  }, []);

  // Floating Toasts State & Event Listener
  const [toasts, setToasts] = useState([]);

  const addToast = (toast) => {
    const id = toast.id || `toast-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    const newToast = { ...toast, id };
    setToasts((prev) => [...prev.slice(-2), newToast]); // Maksimal 3 toast bersamaan

    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5500);
  };

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  useEffect(() => {
    const handleGlobalToast = (e) => {
      if (e.detail) {
        addToast(e.detail);
      }
    };
    window.addEventListener("app-global-toast", handleGlobalToast);
    return () => {
      window.removeEventListener("app-global-toast", handleGlobalToast);
    };
  }, []);

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

  const isClosingRef = useRef(false);

  const closeNotification = () => {
    if (isClosingRef.current) return;
    if (dropdownRef.current) {
      isClosingRef.current = true;
      gsap.killTweensOf(dropdownRef.current);
      gsap.to(dropdownRef.current, {
        opacity: 0,
        scale: 0.85,
        y: -14,
        duration: 0.22,
        ease: "power2.in",
        onComplete: () => {
          setIsNotificationOpen(false);
          isClosingRef.current = false;
        },
      });
    } else {
      setIsNotificationOpen(false);
    }
  };

  const toggleNotification = () => {
    if (isNotificationOpen) {
      closeNotification();
    } else {
      isClosingRef.current = false;
      setIsNotificationOpen(true);
    }
  };

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        isNotificationOpen &&
        notificationRef.current &&
        !notificationRef.current.contains(event.target)
      ) {
        closeNotification();
      }
      if (
        isSearchOpen &&
        searchContainerRef.current &&
        !searchContainerRef.current.contains(event.target)
      ) {
        closeSearch();
      }
      if (
        isUserMenuOpen &&
        userMenuRef.current &&
        !userMenuRef.current.contains(event.target)
      ) {
        closeUserMenu();
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        closeSearch();
        closeUserMenu();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isNotificationOpen, isSearchOpen, isUserMenuOpen]);

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

  useEffect(() => {
    if (progressBarRef.current) {
      gsap.killTweensOf(progressBarRef.current);
      gsap.set(progressBarRef.current, { width: "0%", opacity: 1 });
      gsap.to(progressBarRef.current, {
        width: "70%",
        duration: 0.4,
        ease: "power2.out",
      });

      setTimeout(() => {
        gsap.to(progressBarRef.current, {
          width: "100%",
          duration: 0.3,
          ease: "power2.in",
          onComplete: () => {
            gsap.to(progressBarRef.current, { opacity: 0, duration: 0.2 });
          },
        });
      }, 400);
    }
  }, [location.pathname]);

  const initial = (user?.name?.charAt(0) || "A").toUpperCase();

  return (
    <>
      <div
        ref={progressBarRef}
        className="fixed top-0 left-0 z-[9999] h-[3px] bg-gradient-to-r from-sky-400 via-blue-500 to-blue-600 w-0 opacity-0"
      />

      <div
        className="flex min-h-screen bg-[var(--bg-main)] overflow-x-clip"
        ref={wrapperRef}
      >
        {mobileMenuOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />
        )}

        <aside
          className={`bg-[var(--bg-sidebar)] border-r border-[var(--border-color)] flex flex-col fixed h-screen z-50 top-0 left-0 transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] shadow-xl lg:shadow-none ${
            mobileMenuOpen
              ? "translate-x-0 w-[285px]"
              : "-translate-x-full lg:translate-x-0"
          } ${isSidebarCollapsed ? "lg:w-[72px]" : "lg:w-[285px]"}`}
          ref={sidebarRef}
        >
          {/* Floating Circular Edge Toggle Button (Vertically Centered on Sidebar Border) */}
          <button
            onClick={toggleSidebar}
            title={
              isSidebarCollapsed
                ? "Perluas Menu Utama (Ctrl + B)"
                : "Perkecil Menu Utama (Ctrl + B)"
            }
            className="hidden lg:flex absolute -right-4 top-1/2 -translate-y-1/2 z-50 w-8 h-8 rounded-full bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-secondary)] hover:text-sky-500 hover:border-sky-500 shadow-md items-center justify-center cursor-pointer transition-all duration-300 hover:scale-115 group"
          >
            <svg
              className="w-4.5 h-4.5 transition-transform duration-500 ease-[cubic-bezier(0.16,1,0.3,1)]"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2.25}
                d={
                  isSidebarCollapsed
                    ? "M8.25 4.5l7.5 7.5-7.5 7.5"
                    : "M15.75 19.5L8.25 12l7.5-7.5"
                }
              />
            </svg>
          </button>

          {/* Sidebar Header */}
          <div className="h-[85px] px-3 border-b border-[var(--border-color)] flex items-center justify-center overflow-hidden relative">
            <div
              className={`flex items-center gap-1 overflow-hidden transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
                isSidebarCollapsed
                  ? "opacity-0 max-w-0 -translate-x-4 pointer-events-none"
                  : "opacity-100 max-w-[260px] translate-x-0"
              }`}
            >
              <div className="p-1.5 rounded-xl flex items-center justify-center shrink-0">
                <img
                  src={bandaAcehLogo}
                  alt="Logo Kota Banda Aceh"
                  className="h-11 w-auto object-contain"
                />
              </div>
              <div className="p-1 rounded-xl flex items-center justify-center shrink-0">
                <img
                  src={komdigiLogo}
                  alt="Logo Komdigi"
                  className="h-8 w-auto object-contain"
                />
              </div>
              <div className="overflow-hidden whitespace-nowrap">
                <h2 className="text-base font-black text-[var(--text-primary)] leading-tight tracking-tight uppercase">
                  DISKOMINFOTIK
                </h2>
                <p className="text-[15.5px] text-[var(--text-muted)] font-semibold leading-tight">
                  Kota Banda Aceh
                </p>
              </div>
            </div>

            {/* Mobile Close Button */}
            <button
              onClick={() => setMobileMenuOpen(false)}
              className="lg:hidden text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg cursor-pointer"
            >
              ✕
            </button>
          </div>

          <nav
            className={`flex-1 ${isSidebarCollapsed ? "px-2" : "px-3"} py-3 flex flex-col gap-1.5 overflow-y-auto relative`}
            ref={navRef}
          >
            {/* GSAP Fluid Sliding Active Highlight Pill */}
            <div
              ref={activePillRef}
              className="absolute pointer-events-none z-0 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-200 dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 shadow-md shadow-sky-500/25 border-0 outline-none opacity-0"
            />

            {authLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div
                    key={i}
                    className={`flex items-center ${isSidebarCollapsed ? "justify-center w-11 h-11 mx-auto p-0" : "gap-3 px-3.5 py-3 w-full"} rounded-xl bg-[var(--bg-input)]/40 border border-[var(--border-color)]/30`}
                  >
                    <div className="skeleton w-5 h-5 rounded-md shrink-0" />
                    {!isSidebarCollapsed && (
                      <div className="skeleton h-4 w-32 rounded-md" />
                    )}
                  </div>
                ))}
              </div>
            ) : (
              NAV_ITEMS.map((item, index) => (
                <NavLink
                  key={item.label}
                  to={item.to}
                  title={isSidebarCollapsed ? item.label : undefined}
                  ref={(el) => (navItemsRef.current[index] = el)}
                  onClick={(e) => {
                    setMobileMenuOpen(false);
                    gsap.fromTo(
                      e.currentTarget,
                      { scale: 0.96 },
                      { scale: 1, duration: 0.3, ease: "back.out(2)" },
                    );
                  }}
                  onMouseEnter={(e) => {
                    gsap.to(e.currentTarget, {
                      scale: 1.04,
                      duration: 0.2,
                      ease: "power2.out",
                    });
                  }}
                  onMouseLeave={(e) => {
                    gsap.to(e.currentTarget, {
                      scale: 1,
                      duration: 0.2,
                      ease: "power2.out",
                    });
                  }}
                  className={({ isActive }) =>
                    `flex items-center ${
                      isSidebarCollapsed
                        ? "justify-center w-11 h-11 mx-auto p-0"
                        : "gap-3 px-3.5 py-3 w-full"
                    } rounded-xl text-sm font-bold border-0 outline-none focus:outline-none focus:ring-0 relative z-10 group select-none transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ` +
                    (isActive
                      ? "text-white font-extrabold"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-input)]")
                  }
                >
                  <div className="shrink-0 flex items-center justify-center">
                    {item.icon}
                  </div>
                  <span
                    className={`truncate whitespace-nowrap transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] ${
                      isSidebarCollapsed
                        ? "opacity-0 max-w-0 -translate-x-3 pointer-events-none"
                        : "opacity-100 max-w-[200px] translate-x-0"
                    }`}
                  >
                    {item.label}
                  </span>
                </NavLink>
              ))
            )}
          </nav>

          {/* Sidebar Bottom Health Dock */}
          <div className={`px-4 py-3 border-t border-[var(--border-color)] ${isSidebarCollapsed ? "flex justify-center px-2" : ""}`}>
            <SystemHealthIndicator isSidebar={true} isCollapsed={isSidebarCollapsed} />
          </div>
        </aside>

        <main
          className={`flex-1 min-h-screen transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] w-full ${
            isSidebarCollapsed ? "ml-0 lg:ml-[72px]" : "ml-0 lg:ml-[285px]"
          }`}
          ref={mainRef}
        >
          <header className="sticky top-0 z-30 h-[85px] px-4 lg:px-6 bg-[var(--bg-sidebar)]/90 backdrop-blur-md border-b border-[var(--border-color)] flex items-center justify-between gap-3 shadow-xs">
            <div className="flex items-center gap-3 shrink-0">
              {/* Mobile Hamburger Button */}
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="lg:hidden p-2 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] hover:text-sky-500 transition-colors shrink-0 cursor-pointer"
                title="Buka Navigasi"
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 6h16M4 12h16M4 18h16"
                  />
                </svg>
              </button>

              {/* Header Branding Logo & Title: Visible on mobile, and on desktop smoothly when sidebar is collapsed */}
              <div
                className={`items-center gap-1 overflow-hidden transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] flex ${
                  isSidebarCollapsed
                    ? "opacity-100 max-w-[320px] translate-x-0"
                    : "max-lg:opacity-100 max-lg:max-w-[320px] max-lg:translate-x-0 lg:opacity-0 lg:max-w-0 lg:-translate-x-4 lg:pointer-events-none"
                }`}
              >
                <div className="flex items-center gap-1 overflow-hidden shrink-0">
                  <div className="p-1.5 rounded-xl flex items-center justify-center shrink-0">
                    <img
                      src={bandaAcehLogo}
                      alt="Logo Kota Banda Aceh"
                      className="h-11 w-auto object-contain"
                    />
                  </div>
                  <div className="p-1 rounded-xl flex items-center justify-center shrink-0">
                    <img
                      src={komdigiLogo}
                      alt="Logo Komdigi"
                      className="h-8 w-auto object-contain"
                    />
                  </div>
                  <div className="hidden sm:block overflow-hidden whitespace-nowrap">
                    <h2 className="text-base font-black text-[var(--text-primary)] leading-tight tracking-tight uppercase">
                      DISKOMINFOTIK
                    </h2>
                    <p className="text-[15.5px] text-[var(--text-muted)] font-semibold leading-tight">
                      Kota Banda Aceh
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div
              ref={searchContainerRef}
              className="relative w-full max-w-md mx-auto"
            >
              <svg
                ref={searchIconRef}
                className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none z-10"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              <input
                type="text"
                placeholder="Cari dokumen, kategori, atau fitur..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  if (!isSearchOpen) setIsSearchOpen(true);
                }}
                onFocus={() => {
                  setIsSearchOpen(true);
                  if (!searchContainerRef.current || !searchIconRef.current)
                    return;
                  gsap.killTweensOf([
                    searchContainerRef.current,
                    searchIconRef.current,
                  ]);
                  const tl = gsap.timeline();
                  tl.to(searchContainerRef.current, {
                    scale: 1.02,
                    duration: 0.25,
                    ease: "power2.out",
                  });
                  tl.to(
                    searchIconRef.current,
                    {
                      scale: 1.15,
                      rotate: 90,
                      color: "#0ea5e9",
                      duration: 0.25,
                    },
                    "-=0.2",
                  );
                }}
                onBlur={() => {
                  if (!searchContainerRef.current || !searchIconRef.current)
                    return;
                  gsap.killTweensOf([
                    searchContainerRef.current,
                    searchIconRef.current,
                  ]);
                  const tl = gsap.timeline();
                  tl.to(searchContainerRef.current, {
                    scale: 1.0,
                    duration: 0.25,
                    ease: "power2.out",
                  });
                  tl.to(
                    searchIconRef.current,
                    {
                      scale: 1.0,
                      rotate: 0,
                      color: "var(--text-muted)",
                      duration: 0.2,
                    },
                    "-=0.2",
                  );
                }}
                className="w-full !pl-11 pr-8 py-2.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 transition-all shadow-sm"
              />
              {searchQuery && (
                <button
                  onClick={() => {
                    setSearchQuery("");
                    closeSearch();
                  }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] text-xs font-bold z-10"
                >
                  ✕
                </button>
              )}

              {/* Floating Search Results Dropdown Card */}
              {isSearchOpen && (
                <div
                  ref={searchCardRef}
                  className="absolute left-0 right-0 top-full mt-2 bg-[var(--bg-card)] border border-[var(--border-color)] shadow-2xl rounded-xl overflow-hidden z-50 divide-y divide-[var(--border-color)]"
                >
                  <div className="max-h-96 overflow-y-auto p-2 space-y-3">
                    {/* Check if all empty */}
                    {filteredSearchResults.features.length === 0 &&
                    filteredSearchResults.documents.length === 0 &&
                    filteredSearchResults.categories.length === 0 ? (
                      <div className="p-6 text-center text-xs text-[var(--text-muted)]">
                        <p className="font-semibold text-[var(--text-primary)] mb-1">
                          Hasil Tidak Ditemukan
                        </p>
                        <p>
                          Tidak ada dokumen, kategori, atau fitur yang cocok
                          dengan "
                          <span className="text-sky-500 font-bold">
                            {searchQuery}
                          </span>
                          ".
                        </p>
                      </div>
                    ) : (
                      <>
                        {/* FITUR & MENU */}
                        {filteredSearchResults.features.length > 0 && (
                          <div>
                            <p className="text-xs font-extrabold uppercase tracking-wider text-[var(--text-muted)] px-3 py-1">
                              MENU & HALAMAN
                            </p>
                            <div className="space-y-0.5">
                              {filteredSearchResults.features.map((feat) => (
                                <button
                                  key={feat.id || feat.label}
                                  onClick={() => {
                                    closeSearch();
                                    if (feat.to) navigate(feat.to);
                                  }}
                                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-[var(--bg-input)] transition-colors flex items-center justify-between group cursor-pointer"
                                >
                                  <div>
                                    <p className="text-xs font-bold text-[var(--text-primary)] group-hover:text-sky-500 transition-colors">
                                      {feat.label}
                                    </p>
                                    <p className="text-xs text-[var(--text-muted)] truncate max-w-[280px]">
                                      {feat.desc}
                                    </p>
                                  </div>
                                  <span className="text-xs font-semibold text-sky-500 opacity-0 group-hover:opacity-100 transition-opacity">
                                    Buka →
                                  </span>
                                </button>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* DOKUMEN RAG */}
                        {filteredSearchResults.documents.length > 0 && (
                          <div>
                            <p className="text-xs font-extrabold uppercase tracking-wider text-[var(--text-muted)] px-3 py-1">
                              DOKUMEN RAG
                            </p>
                            <div className="space-y-0.5">
                              {filteredSearchResults.documents.map((doc) => (
                                <button
                                  key={doc.id}
                                  onClick={() => {
                                    closeSearch();
                                    navigate(`/documents/${doc.id}`);
                                  }}
                                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-[var(--bg-input)] transition-colors flex items-center justify-between group cursor-pointer"
                                >
                                  <div className="min-w-0 pr-2">
                                    <p className="text-xs font-bold text-[var(--text-primary)] group-hover:text-sky-500 transition-colors truncate">
                                      {doc.title}
                                    </p>
                                    <p className="text-xs text-[var(--text-muted)] font-mono truncate">
                                      {doc.original_filename} •{" "}
                                      {doc.category_name}
                                    </p>
                                  </div>
                                  <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-[var(--bg-card)] text-sky-500 border border-[var(--border-color)] shrink-0">
                                    {doc.status_label || doc.status}
                                  </span>
                                </button>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* KATEGORI AI */}
                        {filteredSearchResults.categories.length > 0 && (
                          <div>
                            <p className="text-xs font-extrabold uppercase tracking-wider text-[var(--text-muted)] px-3 py-1">
                              KATEGORI AI
                            </p>
                            <div className="space-y-0.5">
                              {filteredSearchResults.categories.map((cat) => (
                                <button
                                  key={cat.id}
                                  onClick={() => {
                                    closeSearch();
                                    navigate("/categories");
                                  }}
                                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-[var(--bg-input)] transition-colors flex items-center justify-between group cursor-pointer"
                                >
                                  <div className="min-w-0 pr-2">
                                    <p className="text-xs font-bold text-[var(--text-primary)] group-hover:text-sky-500 transition-colors">
                                      {cat.name}
                                    </p>
                                    <p className="text-xs text-[var(--text-muted)] truncate max-w-[280px]">
                                      {cat.description || "Kategori dokumen"}
                                    </p>
                                  </div>
                                  <span className="text-xs font-semibold text-sky-500 opacity-0 group-hover:opacity-100 transition-opacity">
                                    Buka →
                                  </span>
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  {/* Search Card Footer */}
                  <div className="px-3 py-2 bg-[var(--bg-input)] flex items-center justify-between text-xs text-[var(--text-muted)] font-medium">
                    <span>
                      {searchQuery
                        ? `Hasil pencarian: "${searchQuery}"`
                        : "Pencarian Instan"}
                    </span>
                    <span className="font-mono">Esc untuk menutup</span>
                  </div>
                </div>
              )}
            </div>

            {/* Top Header Right Actions (Notification + Theme Switch + User Account Info) */}
            <div className="flex items-center gap-2.5 sm:gap-3 shrink-0">
              {/* Notification Dropdown Button */}
              <div className="relative" ref={notificationRef}>
                <button
                  onClick={(e) => {
                    toggleNotification();
                    gsap.fromTo(
                      e.currentTarget,
                      { scale: 0.85 },
                      { scale: 1, duration: 0.35, ease: "back.out(2.2)" },
                    );
                  }}
                  className="p-3 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] hover:border-sky-500 hover:text-sky-500 transition-all flex items-center justify-center cursor-pointer relative"
                  title="Notifikasi"
                >
                  <svg
                    className="w-5 h-5 text-[var(--text-primary)] hover:text-sky-500"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.75}
                      d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
                    />
                  </svg>
                  {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red-500 text-white text-xs font-black flex items-center justify-center shadow-md animate-pulse">
                      {unreadCount}
                    </span>
                  )}
                </button>

                {/* Notification Dropdown Window */}
                {isNotificationOpen && (
                  <div
                    ref={dropdownRef}
                    className="absolute right-0 mt-3 w-80 sm:w-96 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-2xl z-50 overflow-hidden"
                  >
                    {/* Header */}
                    <div className="p-4 border-b border-[var(--border-color)] flex items-center justify-between bg-[var(--bg-input)]">
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-sm text-[var(--text-primary)]">
                          Notifikasi
                        </h3>
                        {unreadCount > 0 && (
                          <span className="px-2 py-0.5 rounded-full text-xs font-extrabold bg-[var(--bg-card)] text-sky-500 border border-[var(--border-color)]">
                            {unreadCount} Baru
                          </span>
                        )}
                      </div>
                      {notifications.length > 0 && (
                        <div className="flex items-center gap-3">
                          {unreadCount > 0 && (
                            <button
                              onClick={markAllAsRead}
                              className="text-xs font-semibold text-sky-600 hover:text-sky-500 dark:text-sky-400 transition-colors"
                            >
                              Tandai Dibaca
                            </button>
                          )}
                          <button
                            onClick={clearAllNotifications}
                            className="text-xs font-semibold text-[var(--text-muted)] hover:text-red-500 transition-colors"
                          >
                            Bersihkan
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Notification List */}
                    <div className="max-h-80 overflow-y-auto divide-y divide-[var(--border-color)]">
                      {notifications.length === 0 ? (
                        <div className="p-8 text-center flex flex-col items-center justify-center">
                          <div className="w-14 h-14 rounded-2xl bg-[var(--bg-input)] border border-[var(--border-color)] text-sky-500 flex items-center justify-center mb-3">
                            <svg
                              className="w-7 h-7"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={1.75}
                                d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
                              />
                            </svg>
                          </div>
                          <h4 className="text-sm font-bold text-[var(--text-primary)]">
                            Belum Ada Notifikasi Baru
                          </h4>
                          <p className="text-xs text-[var(--text-muted)] mt-1 max-w-[240px] leading-relaxed">
                            Tidak ada pemberitahuan atau riwayat aktivitas
                            dokumen saat ini.
                          </p>
                        </div>
                      ) : (
                        notifications.map((item) => (
                          <div
                            key={item.id}
                            onClick={() => markAsRead(item.id)}
                            className={`p-4 transition-colors cursor-pointer flex gap-3 items-start ${
                              item.unread
                                ? "bg-[var(--bg-input)]"
                                : "hover:bg-[var(--bg-input)] opacity-75"
                            }`}
                          >
                            {/* Status Icon */}
                            <div className="shrink-0 mt-0.5">
                              {item.type === "success" && (
                                <div className="w-8 h-8 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] text-emerald-500 flex items-center justify-center">
                                  <svg
                                    className="w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M4.5 12.75l6 6 9-13.5"
                                    />
                                  </svg>
                                </div>
                              )}
                              {item.type === "info" && (
                                <div className="w-8 h-8 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] text-sky-500 flex items-center justify-center">
                                  <svg
                                    className="w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
                                    />
                                  </svg>
                                </div>
                              )}
                              {item.type === "warning" && (
                                <div className="w-8 h-8 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] text-amber-500 flex items-center justify-center">
                                  <svg
                                    className="w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                                    />
                                  </svg>
                                </div>
                              )}
                              {item.type === "error" && (
                                <div className="w-8 h-8 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] text-rose-500 flex items-center justify-center">
                                  <svg
                                    className="w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M6 18L18 6M6 6l12 12"
                                    />
                                  </svg>
                                </div>
                              )}
                              {item.type === "system" && (
                                <div className="w-8 h-8 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] text-purple-500 flex items-center justify-center">
                                  <svg
                                    className="w-4 h-4"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
                                    />
                                  </svg>
                                </div>
                              )}
                            </div>

                            {/* Content */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-2">
                                <p className="text-xs font-bold text-[var(--text-primary)] truncate">
                                  {item.title}
                                </p>
                                <span className="text-xs text-[var(--text-muted)] shrink-0 font-medium">
                                  {item.time}
                                </span>
                              </div>
                              <p className="text-xs text-[var(--text-secondary)] mt-1 leading-snug">
                                {item.message}
                              </p>
                            </div>

                            {/* Unread Indicator */}
                            {item.unread && (
                              <span className="w-2 h-2 rounded-full bg-sky-500 shrink-0 mt-2" />
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Dark & Light Mode Toggle Button */}
              <button
                onClick={(e) => {
                  toggleTheme();
                  gsap.fromTo(
                    e.currentTarget,
                    { scale: 0.82, rotate: -15 },
                    {
                      scale: 1,
                      rotate: 0,
                      duration: 0.35,
                      ease: "back.out(2.2)",
                    },
                  );
                }}
                className="p-3 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] hover:border-sky-500 hover:text-sky-500 transition-all flex items-center justify-center cursor-pointer"
                title={isDarkMode ? "Mode Terang" : "Mode Gelap"}
              >
                {isDarkMode ? (
                  <svg
                    className="w-5 h-5 text-amber-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.75}
                      d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z"
                    />
                  </svg>
                ) : (
                  <svg
                    className="w-5 h-5 text-sky-600"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.75}
                      d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z"
                    />
                  </svg>
                )}
              </button>

              {/* User Account Info & Interactive Profile Dropdown Menu */}
              {authLoading ? (
                <div className="flex items-center gap-3 pl-3 border-l border-[var(--border-color)]">
                  <div className="skeleton w-10 h-10 rounded-xl shrink-0" />
                  <div className="hidden sm:flex flex-col space-y-1.5 min-w-0">
                    <div className="skeleton h-4 w-28 rounded-md" />
                    <div className="skeleton h-3 w-36 rounded-md" />
                  </div>
                </div>
              ) : (
                <div className="relative" ref={userMenuRef}>
                  <button
                    onClick={(e) => {
                      toggleUserMenu();
                      gsap.fromTo(
                        e.currentTarget,
                        { scale: 0.95 },
                        { scale: 1, duration: 0.3, ease: "back.out(2)" },
                      );
                    }}
                    className="flex items-center gap-2.5 pl-3 border-l border-[var(--border-color)] text-left hover:opacity-90 transition-opacity cursor-pointer group"
                    title="Menu Akun Admin"
                  >
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sky-500 via-sky-500 to-sky-100 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 text-sm font-bold flex items-center justify-center shadow-sm shrink-0">
                      {initial}
                    </div>
                    <div className="hidden sm:flex flex-col min-w-0">
                      <span className="text-xs font-bold text-[var(--text-primary)] group-hover:text-sky-500 transition-colors truncate max-w-[140px]">
                        {user?.name || "Admin Diskominfotik"}
                      </span>
                      <span className="text-xs text-[var(--text-muted)] truncate max-w-[140px]">
                        {user?.email || "admin@diskominfotik.go.id"}
                      </span>
                    </div>
                    <svg
                      className={`w-4 h-4 text-[var(--text-muted)] group-hover:text-[var(--text-primary)] transition-transform duration-200 ${
                        isUserMenuOpen ? "rotate-180 text-sky-500" : ""
                      }`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19.5 8.25l-7.5 7.5-7.5-7.5"
                      />
                    </svg>
                  </button>

                  {/* User Profile Dropdown Menu Window */}
                  {isUserMenuOpen && (
                    <div
                      ref={userMenuDropdownRef}
                      className="absolute right-0 mt-3 w-64 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-2xl z-50 overflow-hidden divide-y divide-[var(--border-color)]"
                    >
                      {/* User Header Info in Dropdown */}
                      <div className="p-3.5 bg-[var(--bg-input)] flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sky-500 via-sky-500 to-sky-100 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 text-sm font-bold flex items-center justify-center shrink-0 shadow-sm">
                          {initial}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-[var(--text-primary)] truncate">
                            {user?.name || "Admin Diskominfotik"}
                          </p>
                          <p className="text-xs text-[var(--text-muted)] truncate">
                            {user?.email || "admin@diskominfotik.go.id"}
                          </p>
                        </div>
                      </div>

                      {/* Navigation Actions */}
                      <div className="p-1.5 space-y-0.5">
                        {/* 1. Profil Pengguna */}
                        <button
                          onClick={() => {
                            closeUserMenu();
                            setActiveSettingsTab("profile");
                            setShowSettingsModal(true);
                          }}
                          className="w-full px-3 py-2 rounded-lg text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-input)] hover:text-sky-500 transition-colors flex items-center gap-2.5 text-left group cursor-pointer"
                        >
                          <svg
                            className="w-4 h-4 text-sky-500 group-hover:scale-110 transition-transform"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={1.75}
                              d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
                            />
                          </svg>
                          <span>Profil Akun</span>
                        </button>

                        {/* 2. Keamanan & Sandi */}
                        <button
                          onClick={() => {
                            closeUserMenu();
                            setPassError("");
                            setPassSuccess("");
                            setActiveSettingsTab("security");
                            setShowSettingsModal(true);
                          }}
                          className="w-full px-3 py-2 rounded-lg text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-input)] hover:text-sky-500 transition-colors flex items-center gap-2.5 text-left group cursor-pointer"
                        >
                          <svg
                            className="w-4 h-4 text-sky-500 group-hover:scale-110 transition-transform"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={1.75}
                              d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
                            />
                          </svg>
                          <span>Keamanan & Sandi</span>
                        </button>

                        {/* 3. Preferensi Sistem */}
                        <button
                          onClick={() => {
                            closeUserMenu();
                            setActiveSettingsTab("preferences");
                            setShowSettingsModal(true);
                          }}
                          className="w-full px-3 py-2 rounded-lg text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-input)] hover:text-sky-500 transition-colors flex items-center gap-2.5 text-left group cursor-pointer"
                        >
                          <svg
                            className="w-4 h-4 text-sky-500 group-hover:scale-110 transition-transform"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={1.75}
                              d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z"
                            />
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={1.75}
                              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                            />
                          </svg>
                          <span>Preferensi Sistem</span>
                        </button>

                        {/* 4. Pintasan Integrasi API */}
                        <button
                          onClick={() => {
                            closeUserMenu();
                            navigate("/integrations");
                          }}
                          className="w-full px-3 py-2 rounded-lg text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-input)] hover:text-sky-500 transition-colors flex items-center gap-2.5 text-left group cursor-pointer"
                        >
                          <svg
                            className="w-4 h-4 text-sky-500 group-hover:scale-110 transition-transform"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={1.75}
                              d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244"
                            />
                          </svg>
                          <span>Integrasi & Kunci API</span>
                        </button>
                      </div>

                      {/* Logout Action */}
                      <div className="p-1.5">
                        <button
                          onClick={() => {
                            closeUserMenu();
                            setShowLogoutModal(true);
                          }}
                          className="w-full px-3 py-2 rounded-lg text-xs font-bold text-red-500 hover:bg-[var(--bg-input)] transition-colors flex items-center gap-2.5 text-left group cursor-pointer"
                        >
                          <svg
                            className="w-4 h-4 text-red-500 group-hover:scale-110 transition-transform"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={1.75}
                              d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75"
                            />
                          </svg>
                          <span>Keluar / Logout</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </header>

          <div ref={contentRef} key={location.pathname}>
            <Outlet />
          </div>
        </main>

        <ConfirmModal
          isOpen={showLogoutModal}
          title="Konfirmasi Keluar"
          message="Apakah Anda yakin ingin keluar dari aplikasi?"
          onConfirm={handleLogout}
          onCancel={() => setShowLogoutModal(false)}
          confirmText="Keluar"
        />

        {/* Settings Modal (Modular & Reusable) */}
        <SettingsModal
          isOpen={showSettingsModal}
          onClose={() => setShowSettingsModal(false)}
          initialTab={activeSettingsTab}
          user={user}
        />

        {/* Global Floating Toast Stack */}
        <div className="fixed bottom-6 right-6 z-[99999] flex flex-col gap-2.5 max-w-sm w-full pointer-events-none px-4 sm:px-0">
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className="pointer-events-auto bg-[var(--bg-card)] border border-[var(--border-color)] shadow-2xl rounded-2xl p-4 flex items-start gap-3.5 transition-all duration-300 animate-in fade-in slide-in-from-bottom-5"
            >
              {/* Type Icon */}
              <div
                className={`w-8 h-8 rounded-xl border flex items-center justify-center shrink-0 mt-0.5 ${
                  toast.type === "success"
                    ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-500"
                    : toast.type === "error"
                    ? "bg-rose-500/10 border-rose-500/20 text-rose-500"
                    : toast.type === "warning"
                    ? "bg-amber-500/10 border-amber-500/20 text-amber-500"
                    : "bg-sky-500/10 border-sky-500/20 text-sky-500"
                }`}
              >
                {toast.type === "success" ? (
                  <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                ) : toast.type === "error" ? (
                  <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                ) : toast.type === "warning" ? (
                  <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                ) : (
                  <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                )}
              </div>
              <div className="flex-1 min-w-0 pr-1">
                <div className="flex items-center justify-between gap-2">
                  <h4 className="text-[var(--text-primary)] text-xs font-bold truncate">{toast.title}</h4>
                  <span className="text-[10px] text-[var(--text-muted)] font-medium shrink-0">Baru saja</span>
                </div>
                <p className="text-[var(--text-secondary)] text-xs leading-relaxed font-medium mt-0.5 line-clamp-2">
                  {toast.message}
                </p>
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg text-xs transition-colors cursor-pointer shrink-0"
                title="Tutup"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
