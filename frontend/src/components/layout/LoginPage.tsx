/**
 * Login page — full-screen overlay with brand card.
 * Ported from auth.js createLoginOverlay().
 */

import { useState, useRef, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useAuth } from '../../hooks/useAuth'
import { getDefaultNamespace } from '../../lib/auth'

export function LoginPage() {
  const { isAuthenticated, user, login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [entered, setEntered] = useState(false)
  const emailRef = useRef<HTMLInputElement>(null)

  // Card entrance animation
  useEffect(() => {
    const timer = requestAnimationFrame(() => setEntered(true))
    return () => cancelAnimationFrame(timer)
  }, [])

  // Auto-focus email
  useEffect(() => {
    emailRef.current?.focus()
  }, [])

  // Redirect if already authenticated
  useEffect(() => {
    if (!isAuthenticated || !user) return

    const returnUrl = searchParams.get('return')
    if (returnUrl && returnUrl.startsWith('/') && returnUrl !== '/' && returnUrl !== '/index.html') {
      navigate(returnUrl, { replace: true })
      return
    }

    const ns = getDefaultNamespace(user)
    if (ns) {
      navigate(user.is_super_admin ? `/${ns}/admin` : `/${ns}/contacts`, { replace: true })
    }
  }, [isAuthenticated, user, navigate, searchParams])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (!email.trim() || !password) {
      setError('Email and password required.')
      return
    }

    setLoading(true)
    try {
      await login(email.trim(), password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  // Don't render login form if already authenticated (will redirect via useEffect)
  if (isAuthenticated) return null

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center overflow-hidden">
      {/* Animated mesh background */}
      <div className="absolute inset-0 bg-bg">
        <div className="absolute inset-[-50%] w-[200%] h-[200%] animate-[authMeshDrift_20s_ease-in-out_infinite_alternate]"
          style={{
            background: 'radial-gradient(ellipse at 30% 20%, rgba(110,44,139,.18) 0%, transparent 50%), radial-gradient(ellipse at 70% 80%, rgba(0,184,207,.12) 0%, transparent 50%), radial-gradient(ellipse at 50% 50%, rgba(74,29,94,.1) 0%, transparent 60%)',
          }}
        />
      </div>

      {/* Grid overlay */}
      <div className="absolute inset-0"
        style={{
          backgroundImage: 'linear-gradient(rgba(110,44,139,.04) 1px, transparent 1px), linear-gradient(90deg, rgba(110,44,139,.04) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
          maskImage: 'radial-gradient(ellipse at center, black 30%, transparent 70%)',
        }}
      />

      {/* Vignette */}
      <div className="absolute inset-0"
        style={{ background: 'radial-gradient(ellipse at center, transparent 40%, rgba(13,15,20,.8) 100%)' }}
      />

      {/* Card */}
      <div className={`relative w-full max-w-[400px] px-10 py-11 bg-surface/85 backdrop-blur-[24px] saturate-150 border border-accent/20 rounded-[20px] shadow-2xl transition-all duration-700 ${
        entered ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-5 scale-[0.98]'
      }`}>
        {/* Brand */}
        <div className="text-center mb-7">
          <div className="flex justify-center mb-4">
            <img src="/visionvolve-logo-white.svg" alt="VisionVolve" className="h-10 w-auto" />
          </div>
          <div className="font-title text-2xl font-bold tracking-tight text-text">Leadgen</div>
          <div className="font-body text-[0.75rem] font-normal tracking-[0.12em] uppercase text-text-muted/70 mt-2">
            Pipeline Command Center
          </div>
        </div>

        {/* Divider */}
        <div className="h-px mb-7"
          style={{ background: 'linear-gradient(90deg, transparent, rgba(110,44,139,.3) 30%, rgba(0,184,207,.2) 70%, transparent)' }}
        />

        {/* Form */}
        <form onSubmit={handleSubmit} className="font-body">
          <div className="mb-5">
            <label htmlFor="auth_email" className="block text-[0.75rem] font-medium tracking-[0.06em] uppercase text-text-muted/80 mb-2">
              Email address
            </label>
            <input
              ref={emailRef}
              id="auth_email"
              type="email"
              autoComplete="email"
              required
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3.5 py-3 bg-bg/60 border border-accent/20 rounded-[10px] text-text text-[0.9rem] font-body outline-none placeholder:text-text-muted/35 focus:border-accent/50 focus:shadow-[0_0_0_3px_rgba(110,44,139,.08),0_0_20px_-4px_rgba(110,44,139,.15)] transition-all"
            />
          </div>

          <div className="mb-5">
            <label htmlFor="auth_password" className="block text-[0.75rem] font-medium tracking-[0.06em] uppercase text-text-muted/80 mb-2">
              Password
            </label>
            <input
              id="auth_password"
              type="password"
              autoComplete="current-password"
              required
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3.5 py-3 bg-bg/60 border border-accent/20 rounded-[10px] text-text text-[0.9rem] font-body outline-none placeholder:text-text-muted/35 focus:border-accent/50 focus:shadow-[0_0_0_3px_rgba(110,44,139,.08),0_0_20px_-4px_rgba(110,44,139,.15)] transition-all"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="text-error text-[0.82rem] text-center mb-3.5 px-3.5 py-2.5 bg-error/6 border border-error/15 rounded-lg animate-[authShake_0.4s_ease]">
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="relative w-full py-3.5 border-none rounded-[10px] cursor-pointer overflow-hidden font-body text-[0.9rem] font-semibold text-white tracking-[0.02em] disabled:opacity-60 disabled:cursor-not-allowed hover:translate-y-[-1px] hover:shadow-[0_4px_20px_-2px_rgba(110,44,139,.5)] active:translate-y-0 transition-all"
            style={{ background: 'linear-gradient(135deg, #6E2C8B, #4A1D5E)', boxShadow: '0 2px 12px -2px rgba(110,44,139,.4), inset 0 1px 0 rgba(255,255,255,.08)' }}
          >
            {loading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>

        {/* Secure badge */}
        <div className="flex items-center justify-center gap-1.5 mt-6 text-[0.72rem] tracking-[0.04em] text-text-muted/45">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="opacity-50">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <span>Encrypted connection</span>
        </div>
      </div>
    </div>
  )
}
