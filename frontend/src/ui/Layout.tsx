import { NavLink } from 'react-router-dom'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { BookOpen, ChevronDown, CircleHelp, Command, FileText, LayoutDashboard, LogOut, Moon, Settings, Shield, Sun } from 'lucide-react'
import type { User } from '../api'

export function Layout({ user, onSignOut, children }: { user: User; onSignOut: () => void; children: ReactNode }) {
  const [dark, setDark] = useState(localStorage.getItem('theme') === 'dark')
  const [menu, setMenu] = useState(false)
  useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light' }, [dark])
  const toggleTheme = () => {
    const value = !dark
    setDark(value)
    localStorage.setItem('theme', value ? 'dark' : 'light')
    document.documentElement.dataset.theme = value ? 'dark' : 'light'
  }
  return <div className="app-shell">
    <header className="topbar">
      <NavLink to="/" className="brand"><span className="brand-mark"><Command size={19} strokeWidth={2.4} /></span><span>atlas<span className="brand-dot">.</span><small>KNOWLEDGE</small></span></NavLink>
      <nav aria-label="Main navigation" className="main-nav">
        <NavLink to="/" end><LayoutDashboard size={16} /> Overview</NavLink>
        <NavLink to="/documents"><FileText size={16} /> Documents</NavLink>
        {user.role === 'admin' && <NavLink to="/admin"><Shield size={16} /> Admin</NavLink>}
      </nav>
      <div className="topbar-actions">
        <button className="icon-button" title="Toggle appearance" aria-label="Toggle appearance" onClick={toggleTheme}>{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
        <button className="user-menu" onClick={() => setMenu(!menu)} aria-expanded={menu}>
          <span className="avatar">{user.full_name.split(' ').map(n => n[0]).join('').slice(0, 2)}</span>
          <span className="user-label"><b>{user.full_name}</b><small>{user.role === 'admin' ? 'Administrator' : 'Workspace member'}</small></span>
          <ChevronDown size={15} />
        </button>
        {menu && <div className="popover user-popover"><NavLink to="/settings" onClick={() => setMenu(false)}><Settings size={15} /> Settings</NavLink><button onClick={onSignOut}><LogOut size={15} /> Sign out</button></div>}
      </div>
    </header>
    <main className="page-content">{children}</main>
    <footer className="app-footer"><span><span className="status-dot" /> Your workspace is private</span><span><BookOpen size={14} /> Knowledge Assistant <span className="footer-sep">·</span> <a href="mailto:support@example.com"><CircleHelp size={14} /> Help</a></span></footer>
  </div>
}
