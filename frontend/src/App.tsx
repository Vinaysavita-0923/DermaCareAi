import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Home from './pages/Home'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Chatbot from './pages/Chatbot'
import AcneAnalysis from './pages/AcneAnalysis'
import SkinAssessment from './pages/SkinAssessment'
import ProductGuide from './pages/ProductGuide'
import Journal from './pages/Journal'
import Reports from './pages/Reports'
import Routines from './pages/Routines'
import Profile from './pages/Profile'
import Splash from './components/Splash'

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

          <Route path="dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="chat" element={<ProtectedRoute><Chatbot /></ProtectedRoute>} />
          <Route path="acne-analysis" element={<ProtectedRoute><AcneAnalysis /></ProtectedRoute>} />
          <Route path="skin-assessment" element={<ProtectedRoute><SkinAssessment /></ProtectedRoute>} />
          <Route path="products" element={<ProtectedRoute><ProductGuide /></ProtectedRoute>} />
          <Route path="journal" element={<ProtectedRoute><Journal /></ProtectedRoute>} />
          <Route path="routines" element={<ProtectedRoute><Routines /></ProtectedRoute>} />
          <Route path="profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
          <Route path="reports" element={<ProtectedRoute><Reports /></ProtectedRoute>} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}
