import { useState } from 'react'
import { Bell, Check, KeyRound, Moon, Shield, UserRound } from 'lucide-react'
import type { User } from '../api'

export function SettingsPage({ user }: { user: User }) {
  const [saved, setSaved] = useState(false)
  return <div className="page-stack"><div className="page-title-row"><div><div className="eyebrow">PREFERENCES</div><h1>Settings</h1><p>Manage your profile and workspace experience.</p></div></div>
    <div className="settings-layout"><nav className="settings-nav"><a className="active"><UserRound size={16} /> Profile</a><a><Shield size={16} /> Security</a><a><Bell size={16} /> Notifications</a><a><Moon size={16} /> Appearance</a></nav>
      <section className="panel settings-panel"><div className="panel-heading"><div><div className="eyebrow">ACCOUNT</div><h2>Profile details</h2></div></div><label className="settings-field">Full name<input value={user.full_name} readOnly /></label><label className="settings-field">Work email<input value={user.email} readOnly /></label><div className="settings-field">Workspace role<div className="readonly-field"><KeyRound size={15} /> {user.role === 'admin' ? 'Administrator' : 'Member'}</div></div><div className="settings-info"><Shield size={16} /><span>Profile changes are managed by your workspace administrator.</span></div><button className="secondary-button" onClick={() => { setSaved(true); window.setTimeout(() => setSaved(false), 2500) }}>{saved ? <><Check size={15} /> Preferences saved</> : 'Save preferences'}</button></section>
    </div>
  </div>
}
