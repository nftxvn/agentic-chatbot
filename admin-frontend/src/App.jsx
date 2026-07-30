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
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-main)]">
      <div className="w-10 h-10 border-[3px] border-[var(--border-color)] border-t-[var(--brand-primary)] rounded-full spin" />
    </div>
  )
}

import { ThemeProvider } from './context/ThemeContext'
import ThemeToggle from './components/ThemeToggle'

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ThemeToggle className="fixed bottom-6 left-6 z-[9999]" />
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
