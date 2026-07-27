import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './contexts/ThemeContext'
import { AuthProvider } from './contexts/AuthContext'
import { ProfileDataProvider } from './contexts/ProfileDataContext'
import ProtectedRoute from './components/auth/routing/ProtectedRoute'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import DashboardPage from './pages/DashboardPage'
import BuildProfilePage from './pages/BuildProfilePage'
import JobAnalyzerPage from './pages/JobAnalyzerPage'
import CareerPlannerPage from './pages/CareerPlannerPage'
import InterviewPrepPage from './pages/InterviewPrepPage'
import ProfilePage from './pages/ProfilePage'

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ProfileDataProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/signup" element={<SignupPage />} />
              <Route path="/build-profile" element={<ProtectedRoute><BuildProfilePage /></ProtectedRoute>} />
              <Route path="/home" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
              <Route path="/jobs" element={<ProtectedRoute><JobAnalyzerPage /></ProtectedRoute>} />
              <Route path="/career-planner" element={<ProtectedRoute><CareerPlannerPage /></ProtectedRoute>} />
              <Route path="/interview" element={<ProtectedRoute><InterviewPrepPage /></ProtectedRoute>} />
              <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
            </Routes>
          </BrowserRouter>
        </ProfileDataProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App