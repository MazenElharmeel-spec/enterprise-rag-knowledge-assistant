import { ChangeEvent, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ChevronRight, FileText, FolderOpen, LockKeyhole, Plus, RefreshCw, Shield, Trash2, UploadCloud } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, type Document } from '../api'

export function Documents() {
  const client = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploadError, setUploadError] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [visibility, setVisibility] = useState('private')
  const query = useQuery({
    queryKey: ['documents'], queryFn: () => api<Document[]>('/documents'),
    refetchInterval: query => query.state.data?.some(d => ['uploaded', 'parsing', 'chunking', 'embedding'].includes(d.status)) ? 2500 : false,
  })
  const upload = useMutation({
    mutationFn: async (file: File) => { const form = new FormData(); form.append('file', file); form.append('visibility', 'private'); return api<Document>('/documents', { method: 'POST', body: form }) },
    onSuccess: () => { client.invalidateQueries({ queryKey: ['documents'] }); setUploadError('') }, onError: error => setUploadError(error.message),
  })
  const retire = useMutation({ mutationFn: (id: string) => api<void>(`/documents/${id}`, { method: 'DELETE' }), onSuccess: () => client.invalidateQueries({ queryKey: ['documents'] }) })
  async function choose(event: ChangeEvent<HTMLInputElement>) { const file = event.target.files?.[0]; if (file) upload.mutate(file); event.target.value = '' }
  async function saveAccess(doc: Document) {
    try { await api<Document>(`/documents/${doc.id}/acl`, { method: 'PUT', body: JSON.stringify({ visibility, grants: [] }) }); setEditingId(null); await client.invalidateQueries({ queryKey: ['documents'] }) }
    catch (error) { setUploadError(error instanceof Error ? error.message : 'Unable to update document access') }
  }
  return <div className="page-stack">
    <div className="page-title-row"><div><div className="eyebrow">KNOWLEDGE LIBRARY</div><h1>Documents</h1><p>Manage the files used to answer questions in your workspace.</p></div><button className="primary-button" onClick={() => inputRef.current?.click()} disabled={upload.isPending}><Plus size={17} /> {upload.isPending ? 'Uploading…' : 'Add document'}</button><input ref={inputRef} className="visually-hidden" type="file" accept=".pdf,.docx,.md,.markdown,.html,.htm,.txt" onChange={choose} /></div>
    {uploadError && <div className="alert error-alert">{uploadError}</div>}
    <div className="library-info"><div><span className="info-icon"><Shield size={18} /></span><span><b>Private by default</b><small>New documents are only visible to you until you change their access.</small></span></div><div className="supported-formats">PDF · DOCX · MD · HTML · TXT <span>Up to 25 MB</span></div></div>
    <section className="panel library-panel">
      <div className="library-toolbar"><div className="toolbar-left"><span className="count-pill">{query.data?.length ?? 0} files</span><span className="panel-meta">Latest uploads first</span></div><span className="panel-meta"><LockKeyhole size={14} /> Access filtered for your account</span></div>
      {query.isLoading ? <div className="skeleton-list">{[1, 2, 3, 4].map(i => <div className="skeleton-row" key={i} />)}</div> : query.data?.length ? <div className="library-table">
        <div className="table-head"><span>DOCUMENT</span><span>ACCESS</span><span>STATUS</span><span>ADDED</span><span /></div>
        {query.data.map(doc => <div key={doc.id}>
          <div className="table-row">
            <Link className="table-doc" to={`/documents/${doc.id}`}><span className={`file-icon ${doc.filename.endsWith('.pdf') ? 'pdf' : 'text'}`}><FileText size={17} /></span><span><b>{doc.title}</b><small>{doc.filename}</small></span></Link>
            <span className="access-label"><span className={`access-dot ${doc.visibility}`} />{doc.visibility === 'org' ? 'Everyone' : doc.visibility === 'group' ? 'Group' : 'Only me'}</span>
            <span className={`status-badge ${doc.status}`}>{doc.status === 'indexed' ? <><Check size={12} /> Ready</> : doc.status}</span>
            <span className="table-date">{new Date(doc.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</span>
            <div className="row-actions">
              {doc.status === 'failed' && <button title="Retry indexing" onClick={() => api<Document>(`/documents/${doc.id}/retry`, { method: 'POST' }).then(() => client.invalidateQueries({ queryKey: ['documents'] }))}><RefreshCw size={15} /></button>}
              <button title="Change access" aria-label={`Change access for ${doc.title}`} onClick={() => { setEditingId(editingId === doc.id ? null : doc.id); setVisibility(doc.visibility) }}><Shield size={15} /></button>
              <button title="Delete document" aria-label={`Delete ${doc.title}`} onClick={() => { if (window.confirm(`Delete ${doc.title}?`)) retire.mutate(doc.id) }}><Trash2 size={15} /></button>
            </div>
            {doc.stage_error && <div className="row-error">{doc.stage_error}</div>}
          </div>
          {editingId === doc.id && <div className="acl-editor"><label>Who can access this file<select value={visibility} onChange={event => setVisibility(event.target.value)}><option value="private">Only me</option><option value="group">My groups</option><option value="org">Everyone in workspace</option></select></label><button className="primary-button" onClick={() => void saveAccess(doc)}>Save access</button><span>Changing access rebuilds the searchable index.</span></div>}
        </div>)}
      </div> : <div className="empty-library"><span><FolderOpen size={25} /></span><h3>No documents yet</h3><p>Add a PDF, Word document, Markdown, HTML, or text file to get started.</p><button className="secondary-button" onClick={() => inputRef.current?.click()}><UploadCloud size={16} /> Upload a document</button></div>}
    </section>
    <div className="workspace-footnote"><span>Documents are processed asynchronously; larger files can take a moment.</span><Link to="/" className="text-link">Ask a question <ChevronRight size={14} /></Link></div>
  </div>
}
