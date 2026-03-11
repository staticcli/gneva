import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { CalendarDays, RefreshCw, Plus, Users, Video, ExternalLink, ToggleLeft, ToggleRight } from 'lucide-react'
import { api } from '../api'

interface CalendarEvent {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  platform: string | null;
  meeting_url: string | null;
  attendees: Array<{ email: string; name: string }>;
  auto_join: boolean;
  meeting_id: string | null;
}

export default function Calendar() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    loadEvents();
  }, []);

  const loadEvents = () => {
    setLoading(true);
    api.calendarEvents()
      .then(data => {
        const items = Array.isArray(data) ? data : data.events || [];
        setEvents(items);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.calendarSync();
      await loadEvents();
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSyncing(false);
    }
  };

  const handleToggleAutoJoin = async (id: string, current: boolean) => {
    try {
      await api.calendarToggleAutoJoin(id, !current);
      setEvents(prev =>
        prev.map(e => e.id === id ? { ...e, auto_join: !current } : e)
      );
    } catch (err: any) {
      alert(err.message);
    }
  };

  const groupByDay = (events: CalendarEvent[]) => {
    const groups: Record<string, CalendarEvent[]> = {};
    events.forEach(e => {
      const day = new Date(e.start_time).toLocaleDateString('en-US', {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
      });
      if (!groups[day]) groups[day] = [];
      groups[day].push(e);
    });
    return groups;
  };

  const formatTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const formatDuration = (start: string, end: string) => {
    const ms = new Date(end).getTime() - new Date(start).getTime();
    const minutes = Math.round(ms / 60000);
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const rem = minutes % 60;
    return rem > 0 ? `${hours}h ${rem}m` : `${hours}h`;
  };

  const platformBadge = (platform: string | null) => {
    if (!platform) return null;
    const colors: Record<string, string> = {
      zoom: 'bg-blue-100 text-blue-700',
      meet: 'bg-green-100 text-green-700',
      google_meet: 'bg-green-100 text-green-700',
      teams: 'bg-purple-100 text-purple-700',
    };
    const labels: Record<string, string> = {
      zoom: 'Zoom',
      meet: 'Meet',
      google_meet: 'Meet',
      teams: 'Teams',
    };
    const key = platform.toLowerCase();
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[key] || 'bg-gray-100 text-gray-700'}`}>
        {labels[key] || platform}
      </span>
    );
  };

  const isToday = (dateStr: string) => {
    const d = new Date(dateStr);
    const today = new Date();
    return d.toDateString() === today.toDateString();
  };

  const grouped = groupByDay(events);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-2xl font-bold">Calendar</h2>
        <div className="flex gap-3">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="flex items-center gap-2 border border-gray-300 px-4 py-2 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={18} className={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Syncing...' : 'Sync Now'}
          </button>
          <button
            className="flex items-center gap-2 bg-gneva-600 text-white px-4 py-2 rounded-lg hover:bg-gneva-700 transition-colors"
            onClick={() => alert('Calendar connection flow coming soon')}
          >
            <Plus size={18} />
            Connect Calendar
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-gray-400">
          Loading events...
        </div>
      ) : events.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <CalendarDays size={48} className="mx-auto mb-4 opacity-50" />
          <p className="text-lg">Connect your calendar to see upcoming meetings</p>
          <p className="text-sm mt-1">Gneva will automatically detect meetings with video links</p>
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(grouped).map(([day, dayEvents]) => (
            <div key={day}>
              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                {day}
                {dayEvents.length > 0 && isToday(dayEvents[0].start_time) && (
                  <span className="bg-gneva-100 text-gneva-700 px-2 py-0.5 rounded text-xs normal-case tracking-normal">
                    Today
                  </span>
                )}
              </h3>
              <div className="space-y-3">
                {dayEvents.map(event => (
                  <div
                    key={event.id}
                    className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-1">
                          <h4 className="font-semibold text-lg">{event.title}</h4>
                          {platformBadge(event.platform)}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-gray-500 mt-1.5">
                          <span>{formatTime(event.start_time)} - {formatTime(event.end_time)}</span>
                          <span className="text-gray-300">|</span>
                          <span>{formatDuration(event.start_time, event.end_time)}</span>
                          {event.attendees && event.attendees.length > 0 && (
                            <>
                              <span className="text-gray-300">|</span>
                              <span className="flex items-center gap-1">
                                <Users size={14} />
                                {event.attendees.length} attendee{event.attendees.length !== 1 ? 's' : ''}
                              </span>
                            </>
                          )}
                          {event.attendees && event.attendees.length > 0 && event.attendees[0].name && (
                            <>
                              <span className="text-gray-300">|</span>
                              <span className="text-gray-400">by {event.attendees[0].name}</span>
                            </>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-4 ml-4">
                        {event.meeting_id && (
                          <Link
                            to={`/meetings/${event.meeting_id}`}
                            className="flex items-center gap-1 text-sm text-gneva-600 hover:text-gneva-700"
                          >
                            <Video size={14} />
                            View Meeting
                            <ExternalLink size={12} />
                          </Link>
                        )}
                        <button
                          onClick={() => handleToggleAutoJoin(event.id, event.auto_join)}
                          className="flex items-center gap-2 text-sm"
                          title={event.auto_join ? 'Auto-join enabled' : 'Auto-join disabled'}
                        >
                          <span className="text-gray-500 text-xs">Auto-join</span>
                          {event.auto_join ? (
                            <ToggleRight size={24} className="text-gneva-600" />
                          ) : (
                            <ToggleLeft size={24} className="text-gray-300" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
