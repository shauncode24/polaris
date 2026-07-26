import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import './SocialAuthButtons.css'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID

function SocialAuthButtons({ onError }) {
  const { loginWithGoogle } = useAuth()
  const navigate = useNavigate()
  const buttonRef = useRef(null)

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !window.google?.accounts?.id || !buttonRef.current) return

    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: async ({ credential }) => {
        try {
          await loginWithGoogle(credential)
          navigate('/home')
        } catch (err) {
          onError?.(err.message)
        }
      },
    })

    window.google.accounts.id.renderButton(buttonRef.current, {
      theme: 'outline',
      size: 'large',
      width: 320,
      shape: 'pill',
    })
  }, [loginWithGoogle, onError])

  if (!GOOGLE_CLIENT_ID) {
    return (
      <p className="social-auth__unconfigured">
        Google sign-in isn't configured yet — set VITE_GOOGLE_CLIENT_ID to enable it.
      </p>
    )
  }

  return (
    <div className="social-auth">
      <div className="social-auth__divider"><span>Or continue with</span></div>
      <div className="social-auth__google" ref={buttonRef} />
    </div>
  )
}

export default SocialAuthButtons