import { FormEvent, useState } from 'react'
import { ArrowRight, Command, LockKeyhole, Mail } from 'lucide-react'
import { api, type User } from '../api'

export function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState('alice@acme-demo.com')
  const [password, setPassword] = useState('demo-pass-123')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const result = await api<{ access_token: string; refresh_token: string; user: User }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
      localStorage.setItem('access_token', result.access_token)
      localStorage.setItem('refresh_token', result.refresh_token)
      localStorage.setItem('user', JSON.stringify(result.user))
      onLogin(result.user)
    } catch (err) { setError(err instanceof Error ? err.message : 'Unable to sign in') } finally { setBusy(false) }
  }
  return <main className="login-wrap"><section className="login-card">
    <div className="login-brand"><span className="brand-mark"><Command size={19} /></span><span>atlas<span className="brand-dot">.</span><small>KNOWLEDGE</small></span></div>
    <div className="eyebrow">YOUR PRIVATE WORKSPACE</div><h1>Welcome back</h1><p className="muted">Sign in to search your organization’s knowledge.</p>
    <form onSubmit={submit} className="login-form">
      <label>Email address<span className="field"><Mail size={16} /><input type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required /></span></label>
      <label>Password<span className="field"><LockKeyhole size={16} /><input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></span></label>
      {error && <div className="alert error-alert">{error}</div>}
      <button className="primary-button full-button" disabled={busy}>{busy ? 'Signing in…' : <>Sign in <ArrowRight size={16} /></>}</button>
    </form>
    <div className="demo-note"><span className="status-dot" /><span><b>Demo workspace</b><br />Alice · Strategy member<br /><small>alice@acme-demo.com / demo-pass-123</small></span></div>
    <p className="login-privacy">Protected with workspace-level access controls.</p>
  </section><div className="login-blurb"><div className="blur-orb" /><p>Find the answers<br />already <em>inside</em> your work.</p><span>One trusted place for your team’s knowledge.</span></div></main>
}
