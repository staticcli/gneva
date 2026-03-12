import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Video, Clock, Users, Phone } from 'lucide-react'
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
  const [meetingInfo, setMeetingInfo] = useState('');
  const [meetingTitle, setMeetingTitle] = useState('');
  const [joining, setJoining] = useState(false);
  const [joinProgress, setJoinProgress] = useState<{botId: string; status: string; message: string} | null>(null);

  useEffect(() => {
    api.meetings().then(r => setMeetings(r.meetings)).catch(console.error);

    const interval = setInterval(() => {
      api.meetings().then(r => {
        setMeetings(r.meetings);
      }).catch(console.error);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setJoining(true);
    setJoinProgress({ botId: '', status: 'sending', message: 'Sending join request...' });
    try {
      const res = await api.joinMeeting(meetingUrl, 'auto', meetingTitle || undefined, undefined, undefined, undefined, meetingInfo || undefined);
      const botId = res.bot_id;
      setShowJoin(false);
      setMeetingUrl('');
      setMeetingInfo('');
      setMeetingTitle('');
      setJoinProgress({ botId, status: 'joining', message: 'Dialing in...' });

      // Poll bot status for live updates
      const pollStatus = setInterval(async () => {
        try {
          const s = await api.botStatus(botId);
          setJoinProgress({ botId, status: s.state, message: s.status_message || s.state });
          if (s.state === 'recording' || s.state === 'in_meeting' || s.state === 'failed' || s.state === 'ended') {
            clearInterval(pollStatus);
            if (s.state === 'recording' || s.state === 'in_meeting') {
              setTimeout(() => setJoinProgress(null), 3000);
            }
            if (s.state === 'failed') {
              setTimeout(() => setJoinProgress(null), 5000);
            }
          }
        } catch {
          // Bot may not be found yet or was cleaned up
        }
      }, 1500);

      setTimeout(() => { clearInterval(pollStatus); }, 120000);

      const r = await api.meetings();
      setMeetings(r.meetings);
    } catch (err: any) {
      setJoinProgress({ botId: '', status: 'failed', message: err.message });
      setTimeout(() => setJoinProgress(null), 5000);
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

  // Detect whether pasted info has dial-in details
  const hasDialin = !!meetingInfo.match(/\+[\d\s\-()]+,,\d/);
  const hasUrl = !!meetingInfo.match(/teams\.microsoft\.com/) || !!meetingUrl;

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-2xl font-bold">Meetings</h2>
        <div className="flex gap-3">
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
          <form onSubmit={handleJoin} className="bg-white rounded-2xl p-6 w-full max-w-lg shadow-2xl">
            <h3 className="text-lg font-bold mb-1">Send Raj to a meeting</h3>
            <p className="text-sm text-gray-500 mb-4">Paste the Teams meeting info — Raj will dial in by phone and join the browser for screen awareness.</p>

            {/* Paste meeting info */}
            <div className="mb-3">
              <label className="flex items-center gap-1.5 text-sm font-medium text-gray-600 mb-1.5">
                <Phone size={14} />
                Meeting Info
              </label>
              <textarea
                placeholder={"Paste Teams meeting info here.\n\nFrom the Teams invite, click \"Copy meeting info\" and paste the whole block."}
                value={meetingInfo}
                onChange={e => {
                  setMeetingInfo(e.target.value);
                  const urlMatch = e.target.value.match(/https:\/\/teams\.microsoft\.com\/\S+/);
                  if (urlMatch && !meetingUrl) {
                    setMeetingUrl(urlMatch[0].replace(/\)$/, ''));
                  }
                }}
                rows={5}
                className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-gneva-500 outline-none text-sm font-mono resize-none"
              />
              {meetingInfo && (
                <div className="flex items-center gap-2 mt-1.5">
                  <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${hasDialin ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {hasDialin ? 'Phone number + conference ID' : 'No dial-in found'}
                  </span>
                  <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${hasUrl ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {hasUrl ? 'Meeting URL' : 'No URL found'}
                  </span>
                </div>
              )}
            </div>

            {/* Fallback URL input */}
            {!meetingInfo && (
              <>
                <div className="relative mb-3">
                  <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200" /></div>
                  <div className="relative flex justify-center text-xs"><span className="bg-white px-2 text-gray-400">or enter URL directly</span></div>
                </div>
                <input
                  type="url"
                  placeholder="Meeting URL (Teams, Zoom, or Meet)"
                  value={meetingUrl}
                  onChange={e => setMeetingUrl(e.target.value)}
                  className="w-full px-4 py-2.5 border rounded-lg mb-3 focus:ring-2 focus:ring-gneva-500 outline-none"
                />
              </>
            )}

            <input
              type="text"
              placeholder="Meeting title (optional)"
              value={meetingTitle}
              onChange={e => setMeetingTitle(e.target.value)}
              className="w-full px-4 py-2.5 border rounded-lg mb-4 focus:ring-2 focus:ring-gneva-500 outline-none"
            />

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => { setShowJoin(false); setMeetingInfo(''); setMeetingUrl(''); }}
                className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={joining || (!meetingUrl && !meetingInfo)}
                className="flex-1 bg-gneva-600 text-white px-4 py-2 rounded-lg hover:bg-gneva-700 disabled:opacity-50"
              >
                {joining ? 'Joining...' : hasDialin ? 'Dial In' : 'Join Meeting'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Join progress indicator */}
      {joinProgress && (
        <div className={`mb-4 rounded-xl p-4 border ${
          joinProgress.status === 'failed' ? 'bg-red-50 border-red-200' :
          joinProgress.status === 'recording' || joinProgress.status === 'in_meeting' ? 'bg-green-50 border-green-200' :
          'bg-blue-50 border-blue-200'
        }`}>
          <div className="flex items-center gap-3">
            {joinProgress.status !== 'failed' && joinProgress.status !== 'recording' && joinProgress.status !== 'in_meeting' && (
              <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            )}
            {joinProgress.status === 'recording' || joinProgress.status === 'in_meeting' ? (
              <div className="w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
              </div>
            ) : null}
            {joinProgress.status === 'failed' && (
              <div className="w-5 h-5 bg-red-500 rounded-full flex items-center justify-center">
                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" /></svg>
              </div>
            )}
            <div>
              <p className={`font-medium text-sm ${
                joinProgress.status === 'failed' ? 'text-red-700' :
                joinProgress.status === 'recording' || joinProgress.status === 'in_meeting' ? 'text-green-700' :
                'text-blue-700'
              }`}>
                {joinProgress.message}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Meeting list */}
      {meetings.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <Video size={48} className="mx-auto mb-4 opacity-50" />
          <p className="text-lg">No meetings yet</p>
          <p className="text-sm mt-1">Send Raj to a meeting to get started</p>
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
                      {new Date(m.created_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true })}
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
