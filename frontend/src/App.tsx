import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Home from './pages/Home'
import Login from './pages/Login'
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Chatbot = lazy(() => import('./pages/Chatbot'))
const AcneAnalysis = lazy(() => import('./pages/AcneAnalysis'))
const SkinAssessment = lazy(() => import('./pages/SkinAssessment'))
const ProductGuide = lazy(() => import('./pages/ProductGuide'))
const Journal = lazy(() => import('./pages/Journal'))
const Reports = lazy(() => import('./pages/Reports'))
const Routines = lazy(() => import('./pages/Routines'))
const Profile = lazy(() => import('./pages/Profile'))
import Splash from './components/Splash'

// Pages load on demand so the first visit downloads less code.
function Page({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <Suspense fallback={<p className="py-12 text-center text-slate-400">Loading…</p>}>{children}</Suspense>
    </ProtectedRoute>
  )
}

// Signed-in users land on their dashboard, not the marketing page.
function HomeRoute() {
  const { user } = useAuth()
  return user ? <Navigate to="/dashboard" replace /> : <Home />
}

export default function App() {
  return (
    <AuthProvider>
      <Splash />
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<HomeRoute />} />
          <Route path="login" element={<Login />} />

          <Route path="dashboard" element={<Page><Dashboard /></Page>} />
          <Route path="chat" element={<Page><Chatbot /></Page>} />
          <Route path="acne-analysis" element={<Page><AcneAnalysis /></Page>} />
          <Route path="skin-assessment" element={<Page><SkinAssessment /></Page>} />
          <Route path="products" element={<Page><ProductGuide /></Page>} />
          <Route path="journal" element={<Page><Journal /></Page>} />
          <Route path="routines" element={<Page><Routines /></Page>} />
          <Route path="profile" element={<Page><Profile /></Page>} />
          <Route path="reports" element={<Page><Reports /></Page>} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}
