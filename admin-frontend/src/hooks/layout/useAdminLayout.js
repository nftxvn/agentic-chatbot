import { useAuth } from "../../context/AuthContext";
import { useNavigate, useLocation } from "react-router-dom";
import { useState, useEffect, useRef } from "react";
import { useAdminNotifications } from "./useAdminNotifications";
import { useTheme } from "../../context/ThemeContext";
import { useAdminSearch } from "./useAdminSearch";
import gsap from "gsap";
import { ticketsApi } from "../../api/tickets";
import { useActiveEmbeddingPoller } from "./useActiveEmbeddingPoller";

/** Orkestrasi navigasi, menu, animasi shell, badge, toast, dan komposisi hook admin. */
export function useAdminLayout({ formatRelativeTime, QUICK_FEATURES, NAV_ITEMS }) {
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

  const {
    isNotificationOpen,
    setIsNotificationOpen,
    notifications,
    fetchRealNotifications,
    unreadCount,
    markAllAsRead,
    clearAllNotifications,
    markAsRead,
  } = useAdminNotifications({ formatRelativeTime });

  // Search System States & Optimization
  const [openTicketsCount, setOpenTicketsCount] = useState(0);
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
  const [activeSettingsTab, setActiveSettingsTab] = useState("profile");

  // 'profile' | 'security' | 'preferences'

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

  const {
    filteredSearchResults,
    closeSearch,
  } = useAdminSearch({
    setSearchIndexData,
    location,
    searchQuery,
    QUICK_FEATURES,
    searchIndexData,
    searchCardRef,
    setIsSearchOpen,
    isSearchOpen,
  });

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

  const fetchTicketsCount = async () => {
    try {
      const statsRes = await ticketsApi.getStats().catch(() => null);
      if (statsRes?.success && statsRes?.data) {
        const count = (statsRes.data.open || 0) + (statsRes.data.in_progress || 0);
        setOpenTicketsCount(count);
      }
    } catch (err) {
      // silent fail
    }
  };

  useEffect(() => {
    fetchRealNotifications();
    fetchTicketsCount();
    const interval = setInterval(() => {
      fetchRealNotifications();
      fetchTicketsCount();
    }, 10000);

    const handleUpdateEvent = () => {
      fetchRealNotifications();
      fetchTicketsCount();
    };
    window.addEventListener("app-notification-update", handleUpdateEvent);
    window.addEventListener("app-tickets-updated", handleUpdateEvent);

    return () => {
      clearInterval(interval);
      window.removeEventListener("app-notification-update", handleUpdateEvent);
      window.removeEventListener("app-tickets-updated", handleUpdateEvent);
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

  useActiveEmbeddingPoller({ searchIndexData, fetchRealNotifications });

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

  return {
    user,
    authLoading,
    navigate,
    location,
    mobileMenuOpen,
    setMobileMenuOpen,
    isSidebarCollapsed,
    toggleSidebar,
    showLogoutModal,
    setShowLogoutModal,
    isNotificationOpen,
    notifications,
    unreadCount,
    markAllAsRead,
    clearAllNotifications,
    markAsRead,
    openTicketsCount,
    searchQuery,
    setSearchQuery,
    isSearchOpen,
    setIsSearchOpen,
    toggleTheme,
    isDarkMode,
    handleLogout,
    isUserMenuOpen,
    userMenuRef,
    userMenuDropdownRef,
    showSettingsModal,
    setShowSettingsModal,
    activeSettingsTab,
    setActiveSettingsTab,
    wrapperRef,
    sidebarRef,
    mainRef,
    progressBarRef,
    notificationRef,
    dropdownRef,
    contentRef,
    navRef,
    navItemsRef,
    activePillRef,
    searchContainerRef,
    searchIconRef,
    searchCardRef,
    filteredSearchResults,
    closeSearch,
    closeUserMenu,
    toggleUserMenu,
    toasts,
    removeToast,
    toggleNotification,
    initial,
  };
}
