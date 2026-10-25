import { useState, useEffect, useRef } from "react";

/** Ukuran, orientasi, fit, zoom, pan, dan listener viewport citra editor. */
export function useCorrectionViewport({ currentText, originalSavedText, pageSizes, currentPage }) {
  const [fitMode, setFitMode] = useState("auto");

  // 'auto' | 'width' | 'custom'
  const [zoomScale, setZoomScale] = useState(100);

  // Percentage: 25% - 400%
  const [splitViewMode, setSplitViewMode] = useState("split");

  // 'split' | 'image' | 'editor'
  const [imgNaturalDim, setImgNaturalDim] = useState({ width: 0, height: 0 });
  const hasUnsavedChanges = currentText !== originalSavedText;

  // Mouse Pan / Dragging & Zooming State
  const imageContainerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(600);
  const [containerHeight, setContainerHeight] = useState(700);
  const [isPanning, setIsPanning] = useState(false);

  const panStartRef = useRef({
    startX: 0,
    startY: 0,
    scrollLeft: 0,
    scrollTop: 0,
  });

  // Measure container dimensions accurately for pixel-perfect zoom calculations
  useEffect(() => {
    const container = imageContainerRef.current;
    if (!container) return;

    const updateDimensions = () => {
      if (imageContainerRef.current) {
        setContainerWidth(imageContainerRef.current.clientWidth);
        setContainerHeight(imageContainerRef.current.clientHeight);
      }
    };
    updateDimensions();

    const ro = new ResizeObserver(updateDimensions);
    ro.observe(container);
    return () => ro.disconnect();
  }, []);

  // Determine current page orientation (Landscape vs Portrait)
  const currentPageSize = pageSizes.find((p) => p.page_number === currentPage);

  const isLandscape =
    currentPageSize?.orientasi === "lanskap" ||
    (currentPageSize
      ? currentPageSize.lebar >= currentPageSize.tinggi
      : false) ||
    (imgNaturalDim.width > 0 && imgNaturalDim.width >= imgNaturalDim.height);

  // Natural or fallback dimensions (2x default render scale)
  const natW = imgNaturalDim.width || (currentPageSize?.lebar ? currentPageSize.lebar * 2 : 800);
  const natH = imgNaturalDim.height || (currentPageSize?.tinggi ? currentPageSize.tinggi * 2 : 1130);

  // Available viewport space with padding (p-6 => 48px padding total)
  const availW = Math.max(200, containerWidth - 48);
  const availH = Math.max(200, containerHeight - 48);

  // Base scale to fit entirely within viewport (100% Fit Page)
  const fitPageScale = Math.min(availW / natW, availH / natH, 1.0);
  const fitWidthScale = availW / natW;
  let computedWidth = Math.round(natW * fitPageScale);
  let computedHeight = Math.round(natH * fitPageScale);

  if (fitMode === "width") {
    computedWidth = Math.round(natW * fitWidthScale);
    computedHeight = Math.round(natH * fitWidthScale);
  } else if (fitMode === "custom") {
    const effectiveScale = fitPageScale * (zoomScale / 100);
    computedWidth = Math.round(natW * effectiveScale);
    computedHeight = Math.round(natH * effectiveScale);
  }

  const handleZoomIn = () => {
    setFitMode("custom");
    setZoomScale((prev) => Math.min(400, (Math.floor(prev / 25) + 1) * 25));
  };

  const handleZoomOut = () => {
    setFitMode("custom");
    setZoomScale((prev) => Math.max(25, (Math.ceil(prev / 25) - 1) * 25));
  };

  const handleResetZoom = () => {
    setFitMode("auto");
    setZoomScale(100);
  };

  // Mouse Drag / Pan handlers
  const handleMouseDown = (e) => {
    if (e.button !== 0 || !imageContainerRef.current) return;
    setIsPanning(true);
    panStartRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      scrollLeft: imageContainerRef.current.scrollLeft,
      scrollTop: imageContainerRef.current.scrollTop,
    };
  };

  useEffect(() => {
    if (!isPanning) return;

    const handleMouseMove = (e) => {
      if (!imageContainerRef.current) return;
      e.preventDefault();
      const deltaX = e.clientX - panStartRef.current.startX;
      const deltaY = e.clientY - panStartRef.current.startY;
      imageContainerRef.current.scrollLeft =
        panStartRef.current.scrollLeft - deltaX;
      imageContainerRef.current.scrollTop =
        panStartRef.current.scrollTop - deltaY;
    };

    const handleMouseUp = () => {
      setIsPanning(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isPanning]);

  const handleDoubleClick = () => {
    if (fitMode === "auto") {
      setFitMode("custom");
      setZoomScale(150);
    } else {
      handleResetZoom();
    }
  };

  // Non-passive wheel zoom & boundary scroll isolation listener
  useEffect(() => {
    const container = imageContainerRef.current;
    if (!container) return;

    const onWheel = (e) => {
      if (e.ctrlKey || e.metaKey) {
        // Zoom on Ctrl + Wheel or Pinch
        e.preventDefault();
        const delta = e.deltaY < 0 ? 20 : -20;
        setFitMode("custom");
        setZoomScale((prev) => Math.max(25, Math.min(400, prev + delta)));
      } else {
        // Prevent scroll chaining to parent page when reaching top or bottom boundary
        const { scrollTop, scrollHeight, clientHeight } = container;
        const isAtTop = scrollTop <= 0;
        const isAtBottom =
          Math.ceil(scrollTop + clientHeight) >= scrollHeight - 1;

        if ((e.deltaY < 0 && isAtTop) || (e.deltaY > 0 && isAtBottom)) {
          e.preventDefault();
        }
      }
    };

    container.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      container.removeEventListener("wheel", onWheel);
    };
  }, []);

  return {
    fitMode,
    setFitMode,
    zoomScale,
    setZoomScale,
    splitViewMode,
    setSplitViewMode,
    setImgNaturalDim,
    hasUnsavedChanges,
    imageContainerRef,
    isPanning,
    availW,
    availH,
    computedWidth,
    computedHeight,
    handleZoomIn,
    handleZoomOut,
    handleResetZoom,
    handleMouseDown,
    handleDoubleClick,
  };
}
