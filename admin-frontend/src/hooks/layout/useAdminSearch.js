import { useEffect, useRef, useMemo } from "react";
import { documentsApi } from "../../api/documents";
import { categoriesApi } from "../../api/categories";
import gsap from "gsap";

/** Indeks pencarian, pemfilteran, serta lifecycle dropdown pencarian admin. */
export function useAdminSearch({
  setSearchIndexData,
  location,
  searchQuery,
  QUICK_FEATURES,
  searchIndexData,
  searchCardRef,
  setIsSearchOpen,
  isSearchOpen,
}) {
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

  return {
    filteredSearchResults,
    closeSearch,
  };
}
