import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Video, Clock, Users, Sparkles } from 'lucide-react'
import { api } from '../api'

interface Meeting {
  id: string;
  platform: string;
  title: string | null;
  status: string;
  scheduled_at: string | null;
  started_at: string | null;
  duration_sec: number | null;
  participant_count: number | null;
  created_at: string;
}

export default function Dashboard() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [showJoin, setShowJoin] = useState(false);
  const [meetingUrl, setMeetingUrl] = useState('');
  const [meetingTitle, setMeetingTitle] = useState('');
  const [botName, setBotName] = useState('Gneva');
  const [joining, setJoining] = useState(false);
  const [loadingDemo, setLoadingDemo] = useState(false);

  useEffect(() => {
    api.meetings().then(r => setMeetings(r.meetings)).catch(console.error);

    // Poll for status updates when there are active meetings
    const interval = setInterval(() => {
      api.meetings().then(r => setMeetings(r.meetings)).catch(console.error);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setJoining(true);
    try {
      await api.joinMeeting(meetingUrl, 'auto', meetingTitle || undefined, botName || undefined);
      setShowJoin(false);
      setMeetingUrl('');
      setMeetingTitle('');
      // Refresh meetings list
      const r = await api.meetings();
      setMeetings(r.meetings);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setJoining(false);
    }
  };

  const statusColors: Record<string, string> = {
    scheduled: 'bg-blue-100 text-blue-700',
    joining: 'bg-yellow-100 text-yellow-700',
    active: 'bg-green-100 text-green-700',
    processing: 'bg-purple-100 text-purple-700',
    complete: 'bg-gray-100 text-gray-700',
    failed: 'bg-red-100 text-red-700',
  };

  const formatDuration = (sec: number) => {
    const m = Math.floor(sec / 60);
    return `${m}m`;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-2xl font-bold">Meetings</h2>
        <div className="flex gap-3">
          <button
            onClick={async () => {
              setLoadingDemo(true);
              try {
                await api.createDemoMeeting();
                const r = await api.meetings();
                setMeetings(r.meetings);
              } catch (err: any) {
                alert(err.message);
              } finally {
                setLoadingDemo(false);
              }
            }}
            disabled={loadingDemo}
            className="flex items-center gap-2 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50"
          >
            <Sparkles size={18} />
            {loadingDemo ? 'Processing with AI...' : 'Load Demo Meeting'}
          </button>
          <button
            onClick={() => setShowJoin(true)}
            className="flex items-center gap-2 bg-gneva-600 text-white px-4 py-2 rounded-lg hover:bg-gneva-700 transition-colors"
          >
            <Plus size={18} />
            Join Meeting
          </button>
        </div>
      </div>

      {/* Join meeting modal */}
      {showJoin && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <form onSubmit={handleJoin} className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl">
            <h3 className="text-lg font-bold mb-4">Send Gneva to a meeting</h3>
            <input
              type="url"
              placeholder="Meeting URL (Zoom, Meet, or Teams)"
              value={meetingUrl}
              onChange={e => setMeetingUrl(e.target.value)}
              className="w-full px-4 py-2.5 border rounded-lg mb-3 focus:ring-2 focus:ring-gneva-500 outline-none"
              required
            />
            <input
              type="text"
              placeholder="Meeting title (optional)"
              value={meetingTitle}
              onChange={e => setMeetingTitle(e.target.value)}
              className="w-full px-4 py-2.5 border rounded-lg mb-3 focus:ring-2 focus:ring-gneva-500 outline-none"
            />
            <input
              type="text"
              placeholder="Bot display name"
              value={botName}
              onChange={e => setBotName(e.target.value)}
              className="w-full px-4 py-2.5 border rounded-lg mb-4 focus:ring-2 focus:ring-gneva-500 outline-none"
            />
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setShowJoin(false)}
                className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={joining}
                className="flex-1 bg-gneva-600 text-white px-4 py-2 rounded-lg hover:bg-gneva-700 disabled:opacity-50"
              >
                {joining ? 'Joining...' : 'Send Gneva'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Meeting list */}
      {meetings.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <Video size={48} className="mx-auto mb-4 opacity-50" />
          <p className="text-lg">No meetings yet</p>
          <p className="text-sm mt-1">Send Gneva to a meeting to get started</p>
        </div>
      ) : (
        <div className="space-y-3">
          {meetings.map(m => (
            <Link
              key={m.id}
              to={`/meetings/${m.id}`}
              className="block bg-white rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow border border-gray-100"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold text-lg">
                    {m.title || `${m.platform} meeting`}
                  </h3>
                  <div className="flex items-center gap-4 mt-1.5 text-sm text-gray-500">
                    <span className="flex items-center gap-1">
                      <Clock size={14} />
                      {new Date(m.created_at).toLocaleDateString()}
                    </span>
                    {m.duration_sec && (
                      <span>{formatDuration(m.duration_sec)}</span>
                    )}
                    {m.participant_count && (
                      <span className="flex items-center gap-1">
                        <Users size={14} />
                        {m.participant_count}
                      </span>
                    )}
                  </div>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColors[m.status] || 'bg-gray-100'}`}>
                  {m.status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
