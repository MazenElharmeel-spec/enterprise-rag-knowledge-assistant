import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './Layout'
import { Login } from './Login'
import { Dashboard } from './Dashboard'
import { Documents } from './Documents'
import { SettingsPage } from './Settings'
import { Admin } from './Admin'
import { Viewer } from './Viewer'
import { clearAuth, type User } from '../api'

export function currentUser(): User | null {
  const raw = localStorage.getItem('user')
  if (!raw) return null
  try { return JSON.parse(raw) as User } catch { return null }
}

export default function App() {
  const [user, setUser] = useState<User | null>(currentUser)
  useEffect(() => {
    const sync = () => setUser(currentUser())
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [])
  const signOut = () => { clearAuth(); setUser(null) }
  if (!user) return <Routes><Route path="*" element={<Login onLogin={setUser} />} /></Routes>
  return <Layout user={user} onSignOut={signOut}><Routes>
    <Route path="/" element={<Dashboard />} />
    <Route path="/documents" element={<Documents />} />
    <Route path="/documents/:id" element={<Viewer />} />
    <Route path="/settings" element={<SettingsPage user={user} />} />
    <Route path="/admin" element={user.role === 'admin' ? <Admin /> : <Navigate to="/" replace />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></Layout>
}
