import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, FileText, ListChecks, GitBranch } from 'lucide-react'
import { api } from '../api'

export default function MeetingDetail() {
  const { id } = useParams<{ id: string }>();
  const [meeting, setMeeting] = useState<any>(null);
  const [tab, setTab] = useState<'summary' | 'transcript' | 'actions' | 'decisions'>('summary');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    api.meeting(id).then(setMeeting).catch(console.error).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    setData(null);
    const fetcher = {
      summary: () => api.summary(id),
      transcript: () => api.transcript(id),
      actions: () => api.meetingActions(id),
      decisions: () => api.meetingDecisions(id),
    }[tab];
    fetcher().then(setData).catch(() => setData(null));
  }, [id, tab]);

  if (loading) return <div className="text-gray-400">Loading...</div>;
  if (!meeting) return <div className="text-red-500">Meeting not found</div>;

  const TABS = [
    { key: 'summary', label: 'Summary', icon: FileText },
    { key: 'transcript', label: 'Transcript', icon: FileText },
    { key: 'actions', label: 'Action Items', icon: ListChecks },
    { key: 'decisions', label: 'Decisions', icon: GitBranch },
  ] as const;

  return (
    <div>
      <Link to="/" className="flex items-center gap-2 text-gneva-600 mb-4 hover:underline">
        <ArrowLeft size={16} /> Back to meetings
      </Link>

      <h2 className="text-2xl font-bold mb-1">{meeting.title || `${meeting.platform} meeting`}</h2>
      <p className="text-gray-500 mb-6">
        {new Date(meeting.created_at).toLocaleString()} &middot; {meeting.status}
      </p>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg w-fit">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === key ? 'bg-white shadow-sm text-gneva-700' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
        {!data ? (
          <p className="text-gray-400">
            {meeting.status === 'processing' ? 'Processing... check back soon.' : 'Not available yet.'}
          </p>
        ) : tab === 'summary' ? (
          <div>
            <p className="text-lg mb-4">{data.tldr}</p>
            {data.key_decisions?.length > 0 && (
              <div className="mb-4">
                <h4 className="font-semibold mb-2">Key Decisions</h4>
                <ul className="list-disc pl-5 space-y-1">
                  {data.key_decisions.map((d: string, i: number) => <li key={i}>{d}</li>)}
                </ul>
              </div>
            )}
            {data.topics_covered?.length > 0 && (
              <div className="flex gap-2 flex-wrap">
                {data.topics_covered.map((t: string, i: number) => (
                  <span key={i} className="bg-gneva-50 text-gneva-700 px-3 py-1 rounded-full text-sm">{t}</span>
                ))}
              </div>
            )}
          </div>
        ) : tab === 'transcript' ? (
          <div className="space-y-3 max-h-[600px] overflow-y-auto">
            {data.segments?.map((s: any) => (
              <div key={s.id} className="flex gap-3">
                <span className="text-xs text-gray-400 w-20 shrink-0 pt-0.5">
                  {Math.floor(s.start_ms / 60000)}:{String(Math.floor((s.start_ms % 60000) / 1000)).padStart(2, '0')}
                </span>
                <div>
                  <span className="text-xs font-medium text-gneva-600">{s.speaker_label || 'Unknown'}</span>
                  <p className="text-sm">{s.text}</p>
                </div>
              </div>
            ))}
          </div>
        ) : tab === 'actions' ? (
          <div className="space-y-3">
            {data.action_items?.map((a: any) => (
              <div key={a.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                <input type="checkbox" checked={a.status === 'done'} readOnly className="accent-gneva-600" />
                <div className="flex-1">
                  <p className={a.status === 'done' ? 'line-through text-gray-400' : ''}>{a.description}</p>
                  <div className="flex gap-3 text-xs text-gray-500 mt-1">
                    {a.due_date && <span>Due: {a.due_date}</span>}
                    <span className={`px-2 py-0.5 rounded ${
                      a.priority === 'high' ? 'bg-red-100 text-red-700' :
                      a.priority === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>{a.priority}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {data.decisions?.map((d: any) => (
              <div key={d.id} className="p-3 bg-gray-50 rounded-lg">
                <p className="font-medium">{d.statement}</p>
                {d.rationale && <p className="text-sm text-gray-500 mt-1">{d.rationale}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
