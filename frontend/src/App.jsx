import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ThemeProvider } from './contexts/ThemeContext'
import { AuthProvider } from './contexts/AuthContext'
import { ProfileDataProvider } from './contexts/ProfileDataContext'
import ProtectedRoute from './components/auth/routing/ProtectedRoute'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import HomePage from './pages/HomePage'
import BuildProfilePage from './pages/BuildProfilePage'

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
              <Route
                path="/build-profile"
                element={
                  <ProtectedRoute>
                    <BuildProfilePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/home"
                element={
                  <ProtectedRoute>
                    <HomePage />
                  </ProtectedRoute>
                }
              />
            </Routes>
          </BrowserRouter>
        </ProfileDataProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App