import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import AdminLayout from './components/Layout/AdminLayout'
import LoginPage from './pages/LoginPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import DashboardPage from './pages/DashboardPage'
import CategoriesPage from './pages/CategoriesPage'
import DocumentDetailPage from './pages/DocumentDetailPage'
import ChatbotSettingsPage from './pages/ChatbotSettingsPage'
import IntegrationsPage from './pages/IntegrationsPage'
import MonitoringPage from './pages/MonitoringPage'

function AppLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-main)]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 border-4 border-[var(--border-color)] border-t-sky-500 rounded-full animate-spin" />
      </div>
    </div>
  )
}

/** Route yang hanya bisa diakses saat belum login */
function GuestRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <AppLoader />
  return user ? <Navigate to="/dashboard" replace /> : children
}

/** Route yang hanya bisa diakses saat sudah login */
function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <AdminLayoutSkeleton />
  return user ? children : <Navigate to="/login" replace />
}

function AdminLayoutSkeleton() {
  return (
    <div className="flex min-h-screen bg-[var(--bg-main)] overflow-x-hidden">
      {/* Sidebar Skeleton */}
      <aside className="w-[285px] bg-[var(--bg-sidebar)] border-r border-[var(--border-color)] flex flex-col fixed h-screen z-50 top-0 left-0 hidden lg:flex">
        <div className="h-[85px] px-4 border-b border-[var(--border-color)] flex items-center gap-3">
          <div className="skeleton w-10 h-10 rounded-xl shrink-0" />
          <div className="space-y-1.5 flex-1">
            <div className="skeleton h-3.5 w-24 rounded-md" />
            <div className="skeleton h-2.5 w-28 rounded-md" />
          </div>
        </div>
        <div className="flex-1 px-3 py-4 space-y-3">
          <div className="skeleton h-3 w-20 rounded-md mb-4 ml-2" />
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 px-3.5 py-3 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)]">
              <div className="skeleton w-5 h-5 rounded-md shrink-0" />
              <div className="skeleton h-4 w-32 rounded-md" />
            </div>
          ))}
        </div>
      </aside>

      {/* Main Content Skeleton */}
      <main className="ml-0 lg:ml-[285px] flex-1 min-h-screen w-full min-w-0 lg:w-[calc(100%-285px)]">
        {/* Header Skeleton */}
        <header className="h-[85px] px-4 lg:px-6 bg-[var(--bg-card)] border-b border-[var(--border-color)] flex items-center justify-between gap-3">
          <div className="skeleton h-10 w-full max-w-md rounded-xl" />
          <div className="flex items-center gap-3">
            <div className="skeleton w-10 h-10 rounded-xl" />
            <div className="flex items-center gap-3 pl-3 border-l border-[var(--border-color)]">
              <div className="skeleton w-10 h-10 rounded-xl shrink-0" />
              <div className="hidden sm:flex flex-col space-y-1.5">
                <div className="skeleton h-4 w-28 rounded-md" />
                <div className="skeleton h-3 w-36 rounded-md" />
              </div>
            </div>
          </div>
        </header>

        {/* Dashboard Content Skeleton */}
        <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
          <div className="p-6 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-sm space-y-2">
            <div className="skeleton h-6 w-64 rounded-md" />
            <div className="skeleton h-4 w-96 rounded-md" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="p-6 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl flex items-center gap-4">
                <div className="skeleton w-12 h-12 rounded-2xl shrink-0" />
                <div className="space-y-2 flex-1">
                  <div className="skeleton h-3 w-20 rounded-md" />
                  <div className="skeleton h-7 w-16 rounded-md" />
                </div>
              </div>
            ))}
          </div>
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-6 space-y-4">
            <div className="skeleton h-6 w-48 rounded-md" />
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="skeleton h-10 w-full rounded-xl" />
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
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
            <Route path="/settings/chatbot"   element={<ChatbotSettingsPage />} />
            <Route path="/integrations"       element={<IntegrationsPage />} />
            <Route path="/monitoring"         element={<MonitoringPage />} />
            {/* Backward compatibility redirects */}
            <Route path="/chat-logs"          element={<Navigate to="/monitoring?tab=telemetri" replace />} />
            <Route path="/mesin"              element={<Navigate to="/monitoring?tab=hardware" replace />} />
            <Route path="/settings/whatsapp"  element={<Navigate to="/integrations" replace />} />
            <Route path="/settings/api-keys"  element={<Navigate to="/integrations" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </ThemeProvider>
  )
}
