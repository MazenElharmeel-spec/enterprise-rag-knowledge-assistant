import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Download, FileText, LoaderCircle, ShieldCheck } from 'lucide-react';
import { api, API, token, type Document } from '../api';

type Passage = {
  id: string;
  text: string;
  page_start: number | null;
  page_end: number | null;
  heading_path: string[];
};
export function Viewer() {
  const { id = '' } = useParams();
  const [params] = useSearchParams();
  const chunk = params.get('chunk');
  const [doc, setDoc] = useState<Document | null>(null);
  const [passage, setPassage] = useState<Passage | null>(null);
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    let objectUrl = '';
    async function load() {
      try {
        const item = await api<Document>(`/documents/${id}`);
        setDoc(item);
        const response = await fetch(`${API}/documents/${id}/file`, {
          headers: { Authorization: `Bearer ${token()}` },
        });
        if (!response.ok) throw new Error('Document file could not be loaded');
        objectUrl = URL.createObjectURL(await response.blob());
        setUrl(objectUrl);
        if (chunk) setPassage(await api<Passage>(`/documents/${id}/chunks/${chunk}`));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not load document');
      }
    }
    void load();
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id, chunk]);
  if (error)
    return (
      <div className="page-stack">
        <Link to="/documents" className="back-link">
          <ArrowLeft size={15} /> Documents
        </Link>
        <div className="alert error-alert">{error}</div>
      </div>
    );
  return (
    <div className="page-stack viewer-page">
      <Link to="/documents" className="back-link">
        <ArrowLeft size={15} /> Back to documents
      </Link>
      <div className="viewer-title">
        <div className="file-icon text">
          <FileText size={18} />
        </div>
        <div>
          <div className="eyebrow">DOCUMENT VIEWER</div>
          <h1>{doc?.title ?? 'Loading document'}</h1>
          <p>
            {doc?.filename} {doc && <span>· Version {doc.current_version}</span>}
          </p>
        </div>
        {url && (
          <a href={url} download={doc?.filename} className="secondary-button">
            <Download size={16} /> Download
          </a>
        )}
      </div>
      {passage && (
        <aside className="highlight-card">
          <div className="highlight-heading">
            <span>
              <ShieldCheck size={16} /> CITED PASSAGE
            </span>
            {passage.page_start && <span>Page {passage.page_start}</span>}
          </div>
          {passage.heading_path.length > 0 && (
            <div className="chunk-meta">{passage.heading_path.join(' / ')}</div>
          )}
          <p>{passage.text}</p>
        </aside>
      )}
      <section className="viewer-frame">
        {url ? (
          doc?.filename.toLowerCase().endsWith('.pdf') ? (
            <iframe
              title={`Preview of ${doc.title}`}
              src={`${url}#page=${passage?.page_start ?? 1}`}
            />
          ) : (
            <div className="file-preview">
              <FileText size={28} />
              <b>Document ready</b>
              <span>Download the original file to view its formatting.</span>
              <a href={url} download={doc?.filename} className="text-link">
                Download document
              </a>
            </div>
          )
        ) : (
          <div className="loading-viewer">
            <LoaderCircle className="spin" size={22} /> Loading secure preview…
          </div>
        )}
      </section>
    </div>
  );
}
