import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Video, Clock, Users, Volume2, MessageCircle } from 'lucide-react'
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

interface Voice {
  id: string;
  name: string;
  provider: string;
  is_default: boolean;
}

interface GreetingMode {
  id: string;
  label: string;
  preview: string;
}

export default function Dashboard() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [showJoin, setShowJoin] = useState(false);
  const [meetingUrl, setMeetingUrl] = useState('');
  const [meetingTitle, setMeetingTitle] = useState('');
  const [botName, setBotName] = useState('Gneva');
  const [joining, setJoining] = useState(false);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [selectedVoice, setSelectedVoice] = useState('');
  const [greetingModes, setGreetingModes] = useState<GreetingMode[]>([]);
  const [selectedGreeting, setSelectedGreeting] = useState('personalized');

  useEffect(() => {
    api.meetings().then(r => setMeetings(r.meetings)).catch(console.error);
    api.voices().then(r => {
      const v = r.voices || [];
      setVoices(v);
      const def = v.find((x: Voice) => x.is_default);
      if (def) setSelectedVoice(def.id);
    }).catch(console.error);
    api.greetingModes().then(r => {
      setGreetingModes(r.modes || []);
    }).catch(console.error);

    // Poll for status updates only when there are active meetings
    const interval = setInterval(() => {
      api.meetings().then(r => {
        setMeetings(r.meetings);
      }).catch(console.error);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // B11: could optimize to only poll when active meetings exist
  // but keeping simple for now since the interval is already modest

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setJoining(true);
    try {
      await api.joinMeeting(meetingUrl, 'auto', meetingTitle || undefined, botName || undefined, selectedVoice || undefined, selectedGreeting || undefined);
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
              className="w-full px-4 py-2.5 border rounded-lg mb-3 focus:ring-2 focus:ring-gneva-500 outline-none"
            />
            {voices.length > 0 && (
              <div className="mb-3">
                <label className="flex items-center gap-1.5 text-sm font-medium text-gray-600 mb-1.5">
                  <Volume2 size={14} />
                  Voice
                </label>
                <select
                  value={selectedVoice}
                  onChange={e => setSelectedVoice(e.target.value)}
                  className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-gneva-500 outline-none bg-white text-sm"
                >
                  {voices.map(v => (
                    <option key={v.id} value={v.id}>
                      {v.name}{v.is_default ? ' (default)' : ''}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="mb-4">
              <label className="flex items-center gap-1.5 text-sm font-medium text-gray-600 mb-1.5">
                <MessageCircle size={14} />
                Greeting Style
              </label>
              <select
                value={selectedGreeting}
                onChange={e => setSelectedGreeting(e.target.value)}
                className="w-full px-4 py-2.5 border rounded-lg focus:ring-2 focus:ring-gneva-500 outline-none bg-white text-sm"
              >
                {greetingModes.length > 0 ? (
                  greetingModes.map(m => (
                    <option key={m.id} value={m.id}>{m.label}</option>
                  ))
                ) : (
                  <>
                    <option value="personalized">Personalized (AI picks based on memory)</option>
                    <option value="professional">Professional</option>
                    <option value="casual">Casual & Friendly</option>
                    <option value="energetic">Energetic & Pumped</option>
                    <option value="funny">Funny / Sarcastic</option>
                    <option value="monday">Monday Vibes</option>
                    <option value="friday">Friday Energy</option>
                    <option value="standup">Standup / Daily Sync</option>
                    <option value="silent">Silent (Client Mode)</option>
                  </>
                )}
              </select>
              {selectedGreeting !== 'personalized' && selectedGreeting !== 'silent' && (
                <p className="text-xs text-gray-400 mt-1 italic">
                  {greetingModes.find(m => m.id === selectedGreeting)?.preview || ''}
                </p>
              )}
              {selectedGreeting === 'silent' && (
                <p className="text-xs text-amber-500 mt-1">Gneva will join silently — ideal for client meetings</p>
              )}
            </div>
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
