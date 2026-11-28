import { Navigate } from 'react-router-dom'
import { useAuth } from '../../../contexts/AuthContext'
import Button from '../../common/Button'

function ProtectedRoute({ children }) {
  const { token, loading, unreachable, retry } = useAuth()

  if (loading) return null
  if (!token && unreachable) {
    // Not the sign-in page: the user may well still be signed in.
    return (
      <div role="alert" style={{ padding: '4rem 1.5rem', textAlign: 'center' }}>
        <p style={{ marginBottom: '1rem' }}>Couldn&apos;t check your sign-in. The server may be unavailable for a moment.</p>
        <Button variant="primary" size="md" onClick={retry}>Try again</Button>
      </div>
    )
  }
  if (!token) return <Navigate to="/login" replace />

  return children
}

export default ProtectedRoute
