import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import AdminLayout from './components/Layout/AdminLayout'
import LoginPage from './pages/LoginPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import DashboardPage from './pages/DashboardPage'
import CategoriesPage from './pages/CategoriesPage'
import DocumentDetailPage from './pages/DocumentDetailPage'
import WhatsappSettingsPage from './pages/WhatsappSettingsPage'

/** Route yang hanya bisa diakses saat belum login */
function GuestRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <AppLoader />
  return user ? <Navigate to="/dashboard" replace /> : children
}

/** Route yang hanya bisa diakses saat sudah login */
function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <AppLoader />
  return user ? children : <Navigate to="/login" replace />
}

function AppLoader() {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--surface-950)',
    }}>
      <div style={{
        width: 40, height: 40,
        border: '3px solid var(--surface-700)',
        borderTopColor: 'var(--brand-500)',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
      }} />
    </div>
  )
}

import { ThemeProvider } from './context/ThemeContext'
import ThemeToggle from './components/ThemeToggle'

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ThemeToggle className="theme-toggle-floating" />
        <BrowserRouter>
        <Routes>
          {/* Redirect root */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          {/* Guest-only routes */}
          <Route path="/login" element={
            <GuestRoute><LoginPage /></GuestRoute>
          } />
          <Route path="/forgot-password" element={
            <GuestRoute><ForgotPasswordPage /></GuestRoute>
          } />
          <Route path="/reset-password" element={
            <GuestRoute><ResetPasswordPage /></GuestRoute>
          } />

          {/* Protected routes dengan AdminLayout */}
          <Route element={<PrivateRoute><AdminLayout /></PrivateRoute>}>
            <Route path="/dashboard"          element={<DashboardPage />} />
            <Route path="/categories"         element={<CategoriesPage />} />
            <Route path="/documents/:id"      element={<DocumentDetailPage />} />
            <Route path="/settings/whatsapp"  element={<WhatsappSettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </ThemeProvider>
  )
}
