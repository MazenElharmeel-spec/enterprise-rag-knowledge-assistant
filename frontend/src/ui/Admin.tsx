import { useQuery } from '@tanstack/react-query'
import { FileText, Users, UsersRound, Activity, ShieldCheck } from 'lucide-react'
import { api } from '../api'

type Overview = { users: number; documents: number; groups: number; indexed_documents: number }
type Member = { id: string; name: string; email: string; role: string }
export function Admin() {
  const stats = useQuery({ queryKey: ['admin-overview'], queryFn: () => api<Overview>('/admin/overview') })
  const members = useQuery({ queryKey: ['admin-users'], queryFn: () => api<Member[]>('/admin/users') })
  return <div className="page-stack"><div className="page-title-row"><div><div className="eyebrow">WORKSPACE CONTROL</div><h1>Admin overview</h1><p>Manage the people and content in your organization.</p></div><span className="verified-label"><ShieldCheck size={14} /> ADMIN ACCESS</span></div>
    <div className="stat-grid">{[{ label: 'Workspace members', value: stats.data?.users, icon: Users }, { label: 'Documents', value: stats.data?.documents, icon: FileText }, { label: 'Access groups', value: stats.data?.groups, icon: UsersRound }, { label: 'Indexed and searchable', value: stats.data?.indexed_documents, icon: Activity }].map(card => <div className="panel stat-card" key={card.label}><span className="stat-icon"><card.icon size={18} /></span><span className="stat-number">{card.value ?? '—'}</span><span className="stat-label">{card.label}</span></div>)}</div>
    <section className="panel admin-members"><div className="panel-heading"><div><div className="eyebrow">PEOPLE</div><h2>Workspace members</h2></div><span className="count-pill">{members.data?.length ?? 0} members</span></div>{members.isError && <div className="alert error-alert">{members.error.message}</div>}<div className="member-list">{members.data?.map(member => <div className="member-row" key={member.id}><span className="avatar">{member.name.split(' ').map(n => n[0]).join('').slice(0, 2)}</span><span className="member-name"><b>{member.name}</b><small>{member.email}</small></span><span className={`role-pill ${member.role}`}>{member.role}</span></div>)}</div><p className="panel-note">Accounts and group membership are seeded for the demo. User provisioning can be connected to your identity provider.</p></section>
  </div>
}
