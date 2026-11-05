import { FormEvent, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowUp, ChevronRight, FileText, Globe2, LoaderCircle, Search, Sparkles, ThumbsDown, ThumbsUp, WandSparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { api, ask, type Citation, type Document } from '../api'

type ChatResult = Awaited<ReturnType<typeof ask>>

export function Dashboard() {
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<ChatResult | null>(null)
  const [streamingAnswer, setStreamingAnswer] = useState('')
  const [deep, setDeep] = useState(false)
  const docs = useQuery({ queryKey: ['documents'], queryFn: () => api<Document[]>('/documents') })
  const mutation = useMutation({ mutationFn: (value: string) => ask(value, undefined, deep, piece => setStreamingAnswer(previous => previous + piece)), onMutate: () => { setResult(null); setStreamingAnswer('') }, onSuccess: value => { setResult(value); setStreamingAnswer('') } })
  function submit(event: FormEvent) { event.preventDefault(); if (question.trim()) mutation.mutate(question.trim()) }
  const sources = result?.citations ?? []
  return <div className="dashboard-page">
    <section className="welcome-row"><div><div className="eyebrow"><span className="status-dot" /> YOUR WORKSPACE</div><h1>Good morning, <span>ready to find something?</span></h1><p>Ask a question across the documents you can access.</p></div><div className="date-label">KNOWLEDGE SEARCH <span>·</span> PRIVATE BY DEFAULT</div></section>
    <section className="search-panel">
      <form className="ask-form" onSubmit={submit}>
        <Search className="ask-search-icon" size={20} />
        <input aria-label="Ask your knowledge base" placeholder="Ask a question about your team’s knowledge…" value={question} onChange={event => setQuestion(event.target.value)} />
        <button type="button" className={`deep-toggle ${deep ? 'selected' : ''}`} onClick={() => setDeep(!deep)} title="Search more passages"><Globe2 size={16} /><span>Deep search</span></button>
        <button className="submit-ask" disabled={!question.trim() || mutation.isPending} aria-label="Ask question">{mutation.isPending ? <LoaderCircle size={18} className="spin" /> : <ArrowUp size={19} />}</button>
      </form>
      <div className="search-hint"><span><Sparkles size={14} /> Answers grounded in your permitted documents</span><span>{deep ? 'Expanded retrieval' : 'Press Enter to search'}</span></div>
      {mutation.isError && <div className="alert error-alert">{mutation.error.message}</div>}
    </section>
    <div className="dashboard-grid">
      <div className="left-column">
        <section className="panel source-panel">
          <div className="panel-heading"><div><div className="eyebrow">YOUR LIBRARY</div><h2>Source documents <span className="count-pill">{docs.data?.length ?? '—'}</span></h2></div><Link to="/documents" className="text-link">View library <ChevronRight size={15} /></Link></div>
          {docs.isLoading ? <div className="skeleton-list">{[1, 2, 3].map(i => <div className="skeleton-row" key={i} />)}</div> : docs.data?.length ? <div className="document-list">{docs.data.slice(0, 5).map(doc => <DocumentRow key={doc.id} doc={doc} />)}</div> : <div className="empty-state"><FileText size={22} /><b>Your library is ready</b><span>Upload documents to ask grounded questions.</span><Link to="/documents" className="text-link">Add a document <ChevronRight size={14} /></Link></div>}
        </section>
        <section className="panel recent-panel"><div className="panel-heading"><div><div className="eyebrow">RETRIEVAL PREVIEW</div><h2>Source passages</h2></div><span className="panel-meta">{sources.length ? `${sources.length} cited` : 'Citations appear here'}</span></div>
          {sources.length ? <div className="chunk-list">{sources.slice(0, 4).map((citation: Citation) => <Link to={`/documents/${citation.document_id}?chunk=${citation.id}`} className="chunk-card" key={citation.id}><div className="chunk-top"><span className="citation-chip">[{citation.marker}]</span><span>{citation.title}</span><ChevronRight size={15} /></div><p>{citation.snippet}</p><div className="chunk-meta">{citation.heading_path.join(' / ') || 'Document'}{citation.page_start ? ` · Page ${citation.page_start}` : ''}</div></Link>)}</div> : <div className="empty-inline"><WandSparkles size={18} /><span>Ask a question to see the passages behind the answer.</span></div>}
        </section>
      </div>
      <section className="panel answer-panel"><div className="panel-heading"><div><div className="eyebrow">KNOWLEDGE ASSISTANT</div><h2><span className="ai-spark"><Sparkles size={15} /></span> Answer</h2></div><span className="verified-label"><span className="status-dot" /> GROUNDED</span></div>
        {mutation.isPending ? streamingAnswer ? <div className="answer-copy"><ReactMarkdown>{streamingAnswer}</ReactMarkdown><span className="stream-cursor" /></div> : <div className="answer-loading"><span className="thinking-orb"><Sparkles size={20} /></span><b>Looking through your sources</b><span>Checking documents you’re allowed to access…</span><div className="loading-line" /></div> : result ? <><div className="answer-copy"><ReactMarkdown>{result.answer}</ReactMarkdown></div>{sources.length > 0 ? <div className="citation-summary"><div className="eyebrow">REFERENCES <span>{sources.length}</span></div>{sources.map(citation => <Link className="reference-row" key={citation.id} to={`/documents/${citation.document_id}?chunk=${citation.id}`}><span className="reference-icon"><FileText size={16} /></span><span className="reference-copy"><b>[{citation.marker}] {citation.title}</b><small>{citation.heading_path.join(' / ') || 'Source passage'}{citation.page_start ? ` · p. ${citation.page_start}` : ''}</small></span><ChevronRight size={15} /></Link>)}</div> : <div className="abstain-note">No source passage was strong enough to support an answer.</div>}<div className="answer-feedback"><span>Was this answer helpful?</span><button aria-label="Helpful" onClick={() => api(`/chat/messages/${result.messageId}/feedback`, { method: 'POST', body: JSON.stringify({ value: 'up' }) }).catch(() => undefined)}><ThumbsUp size={15} /></button><button aria-label="Not helpful" onClick={() => api(`/chat/messages/${result.messageId}/feedback`, { method: 'POST', body: JSON.stringify({ value: 'down' }) }).catch(() => undefined)}><ThumbsDown size={15} /></button></div></> : <div className="answer-empty"><div className="answer-illustration"><span><Sparkles size={24} /></span><i /><i /><i /></div><h3>Your answer, with its sources</h3><p>Ask a question to get a concise response linked to the exact passages that support it.</p><div className="trust-note"><span className="status-dot" /> Only documents you have permission to see are searched.</div></div>}
      </section>
    </div>
    <div className="workspace-footnote"><span><span className="status-dot" /> Access-aware retrieval is on</span><span>Answers may be incomplete when source evidence is limited.</span></div>
  </div>
}

function DocumentRow({ doc }: { doc: Document }) {
  const icon = doc.filename.toLowerCase().endsWith('.pdf') ? 'pdf' : doc.filename.toLowerCase().endsWith('.docx') ? 'doc' : 'text'
  return <Link to={`/documents/${doc.id}`} className="doc-row"><span className={`file-icon ${icon}`}><FileText size={16} /></span><span className="doc-row-name"><b>{doc.title}</b><small>{doc.filename}</small></span><span className={`status-badge ${doc.status}`}>{doc.status === 'indexed' ? 'Ready' : doc.status}</span><span className="doc-date">{new Date(doc.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span></Link>
}
