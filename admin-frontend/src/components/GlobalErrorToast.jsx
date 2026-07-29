import { useState, useEffect } from 'react';
import styles from './GlobalErrorToast.module.css';

export default function GlobalErrorToast() {
  const [error, setError] = useState(null);

  useEffect(() => {
    const handleError = (e) => {
      setError(e.detail);
      // Auto-hide after 5 seconds
      setTimeout(() => setError(null), 5000);
    };

    window.addEventListener('backend-error', handleError);
    return () => window.removeEventListener('backend-error', handleError);
  }, []);

  if (!error) return null;

  return (
    <div className={styles.toastWrapper}>
      <div className={styles.toastContainer}>
        <div className={styles.iconWrapper}>
          <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
        </div>
        <div className={styles.contentWrapper}>
          <h4 className={styles.title}>Koneksi Bermasalah</h4>
          <p className={styles.message}>{error}</p>
        </div>
        <button className={styles.closeButton} onClick={() => setError(null)}>✕</button>
      </div>
    </div>
  );
}
