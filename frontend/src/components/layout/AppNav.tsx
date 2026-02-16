/**
 * Two-tier pillar navigation — React port of nav.js.
 * Tier 1: pillar icons + brand + user/gear
 * Tier 2: sub-page links for active pillar
 */

import { useState, useEffect, useRef } from 'react'
import { Link, useLocation } from 'react-router'
import { useAuth } from '../../hooks/useAuth'
import { useNamespace } from '../../hooks/useNamespace'
import { type Role } from '../../lib/auth'
import { apiFetch } from '../../api/client'

// ---- Pillar config ----

interface PageDef {
  id: string
  label: string
  path: string
  minRole: Role
}

interface PillarDef {
  id: string
  label: string
  icon: React.ReactNode
  pages: PageDef[]
}

const PILLARS: PillarDef[] = [
  {
    id: 'playbook',
    label: 'Playbook',
    icon: (
      <svg viewBox="0 0 24 24" className="w-[18px] h-[18px]" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /><path d="M8 7h8M8 11h6" />
      </svg>
    ),
    pages: [{ id: 'playbook', label: 'ICP Summary', path: 'playbook', minRole: 'viewer' }],
  },
  {
    id: 'radar',
    label: 'Radar',
    icon: (
      <svg viewBox="0 0 24 24" className="w-[18px] h-[18px]" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /><path d="M12 2v4M12 18v4" />
      </svg>
    ),
    pages: [
      { id: 'contacts', label: 'Contacts', path: 'contacts', minRole: 'viewer' },
      { id: 'companies', label: 'Companies', path: 'companies', minRole: 'viewer' },
      { id: 'import', label: 'Import', path: 'import', minRole: 'editor' },
      { id: 'enrich', label: 'Enrich', path: 'enrich', minRole: 'editor' },
    ],
  },
  {
    id: 'reach',
    label: 'Reach',
    icon: (
      <svg viewBox="0 0 24 24" className="w-[18px] h-[18px]" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 2L11 13" /><path d="M22 2L15 22l-4-9-9-4z" />
      </svg>
    ),
    pages: [
      { id: 'campaigns', label: 'Campaigns', path: 'campaigns', minRole: 'viewer' },
      { id: 'messages', label: 'Messages', path: 'messages', minRole: 'viewer' },
    ],
  },
  {
    id: 'echo',
    label: 'Echo',
    icon: (
      <svg viewBox="0 0 24 24" className="w-[18px] h-[18px]" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 20V10" /><path d="M12 20V4" /><path d="M6 20v-6" />
      </svg>
    ),
    pages: [{ id: 'echo', label: 'Dashboard Demo', path: 'echo', minRole: 'viewer' }],
  },
]

interface GearItem {
  id: string
  label: string
  path: string
  minRole: Role
  superOnly?: boolean
}

const GEAR_ITEMS: GearItem[] = [
  { id: 'admin', label: 'Users & Roles', path: '/admin', minRole: 'admin' },
  { id: 'llm-costs', label: 'LLM Costs', path: '/llm-costs', minRole: 'admin', superOnly: true },
]

// ---- Component ----

export function AppNav() {
  const { user, hasRole, logout } = useAuth()
  const namespace = useNamespace()
  const location = useLocation()
  const [gearOpen, setGearOpen] = useState(false)
  const gearRef = useRef<HTMLDivElement>(null)

  // Derive active pillar/page from URL
  const pathSegments = location.pathname.split('/').filter(Boolean)
  // URL shape: /{namespace}/{page} or /{root-page}
  const currentPage = namespace ? pathSegments[1] ?? '' : pathSegments[0] ?? ''

  const activePillar = PILLARS.find((p) =>
    p.pages.some((pg) => pg.path === currentPage),
  )

  // Close gear on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (gearRef.current && !gearRef.current.contains(e.target as Node)) {
        setGearOpen(false)
      }
    }
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [])

  function makePath(pagePath: string) {
    return namespace ? `/${namespace}/${pagePath}` : `/${pagePath}`
  }

  return (
    <div className="app-nav">
      {/* Tier 1 */}
      <div className="flex items-center gap-2 px-6 py-3 bg-surface border-b border-border">
        {/* Brand */}
        <Link to="/" className="flex items-center gap-2.5 no-underline">
          <img src="/visionvolve-icon-color.svg" alt="VisionVolve" className="h-[26px] w-auto" />
          <span className="font-title text-[1.05rem] font-bold tracking-tight text-text">Leadgen</span>
        </Link>

        {/* Pillars */}
        <div className="flex gap-1 ml-6">
          {PILLARS.map((pillar) => {
            const isActive = pillar.id === activePillar?.id
            const defaultPage = pillar.pages[0]!
            if (!hasRole(defaultPage.minRole)) return null

            return (
              <Link
                key={pillar.id}
                to={makePath(defaultPage.path)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[0.82rem] font-medium no-underline transition-colors ${
                  isActive
                    ? 'text-accent-cyan bg-accent-cyan/8'
                    : 'text-text-muted hover:text-text hover:bg-accent/8'
                }`}
              >
                <span className="opacity-70">{pillar.icon}</span>
                <span>{pillar.label}</span>
              </Link>
            )
          })}
        </div>

        {/* Right section */}
        <div className="flex items-center gap-3 ml-auto">
          {/* Namespace switcher */}
          <NamespaceSwitcher />

          {/* User name */}
          {user && (
            <span className="text-[0.82rem] text-text-muted">
              {user.display_name || user.email}
              {user.is_super_admin && (
                <span className="ml-1.5 text-[0.65rem] font-semibold text-accent-cyan bg-accent-cyan/10 px-1.5 py-0.5 rounded">
                  Super
                </span>
              )}
            </span>
          )}

          {/* Gear */}
          {hasRole('admin') && (
            <div ref={gearRef} className="relative">
              <button
                onClick={(e) => { e.stopPropagation(); setGearOpen(!gearOpen) }}
                className={`p-1.5 rounded-md border border-border text-text-muted hover:text-text hover:border-accent transition-colors bg-transparent cursor-pointer ${
                  user?.is_super_admin ? 'relative' : ''
                }`}
                aria-label="Settings"
              >
                <svg viewBox="0 0 24 24" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
                {user?.is_super_admin && (
                  <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-accent-cyan rounded-full" />
                )}
              </button>

              {gearOpen && (
                <div className="absolute right-0 top-full mt-1 bg-surface border border-border-solid rounded-lg py-1 min-w-[180px] shadow-lg z-50">
                  {GEAR_ITEMS.filter((item) => {
                    if (!hasRole(item.minRole)) return false
                    if (item.superOnly && !user?.is_super_admin) return false
                    return true
                  }).map((item) => (
                    <Link
                      key={item.id}
                      to={item.path}
                      className="block px-4 py-2 text-[0.82rem] text-text-muted no-underline hover:bg-surface-alt hover:text-text transition-colors"
                      onClick={() => setGearOpen(false)}
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Logout */}
          <button
            onClick={logout}
            className="bg-transparent border border-border text-text-muted text-[0.75rem] px-2.5 py-1 rounded cursor-pointer hover:border-error hover:text-error transition-colors"
          >
            Logout
          </button>
        </div>
      </div>

      {/* Tier 2 — sub-nav for active pillar */}
      {activePillar && activePillar.pages.length > 1 && (
        <div className="flex gap-1 px-6 py-1.5 bg-surface-alt border-b border-border">
          {activePillar.pages.map((page) => {
            if (!hasRole(page.minRole)) return null
            const isActive = page.path === currentPage

            // Pages served by vanilla HTML need full-page navigation
            const isExternal = page.path === 'enrich' || page.path === 'import'
            const linkProps = {
              key: page.id,
              className: `px-3 py-1 rounded text-[0.78rem] font-medium no-underline transition-colors ${
                isActive
                  ? 'text-accent-cyan bg-accent-cyan/10'
                  : 'text-text-muted hover:text-text hover:bg-accent/8'
              }`,
            }

            return isExternal ? (
              <a {...linkProps} href={makePath(page.path)}>
                {page.label}
              </a>
            ) : (
              <Link {...linkProps} to={makePath(page.path)}>
                {page.label}
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ---- Namespace switcher sub-component ----

function NamespaceSwitcher() {
  const { user } = useAuth()
  const namespace = useNamespace()
  const [namespaces, setNamespaces] = useState<string[]>([])

  useEffect(() => {
    if (!user) return

    const userNs = Object.keys(user.roles)
    setNamespaces(userNs)

    // Super admin: fetch all tenants
    if (user.is_super_admin) {
      apiFetch<Array<{ slug: string; is_active: boolean }>>('/tenants')
        .then((tenants) => {
          const slugs = tenants.filter((t) => t.is_active).map((t) => t.slug)
          if (slugs.length > 0) setNamespaces(slugs)
        })
        .catch(() => { /* keep user namespaces */ })
    }
  }, [user])

  const showSwitcher = user && (user.is_super_admin || namespaces.length > 1)
  if (!showSwitcher) return null

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const newNs = e.target.value
    if (!newNs || newNs === namespace) return

    // Preserve current sub-page
    const path = window.location.pathname
    let subPage = ''
    if (namespace) {
      const prefix = `/${namespace}`
      if (path.startsWith(prefix)) {
        subPage = path.substring(prefix.length)
      }
    }
    if (!subPage || subPage === '/') subPage = '/contacts'
    window.location.href = `/${newNs}${subPage}`
  }

  return (
    <select
      value={namespace ?? ''}
      onChange={handleChange}
      className="bg-surface border border-border rounded px-2 py-1 text-[0.78rem] text-text font-body cursor-pointer outline-none hover:border-accent focus:border-accent transition-colors"
    >
      {namespaces.map((slug) => (
        <option key={slug} value={slug} className="bg-surface text-text">
          {slug}
        </option>
      ))}
    </select>
  )
}
