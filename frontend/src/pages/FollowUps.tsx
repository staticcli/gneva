import { useState, useEffect } from 'react'
import { api } from '../api'

interface ActionItem {
  id: string;
  description: string;
  assignee_id: string | null;
  due_date: string | null;
  priority: string;
  status?: string;
  meeting_id: string;
  created_at: string;
  days_overdue?: number;
}

interface OverdueData {
  total_overdue: number;
  by_assignee: Record<string, ActionItem[]>;
}

interface UpcomingData {
  total_upcoming: number;
  action_items: ActionItem[];
}

const priorityColors: Record<string, string> = {
  high: 'bg-red-100 text-red-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-gray-100 text-gray-600',
};

export default function FollowUps() {
  const [overdue, setOverdue] = useState<OverdueData | null>(null);
  const [upcoming, setUpcoming] = useState<UpcomingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [nudging, setNudging] = useState<string | null>(null);
  const [nudged, setNudged] = useState<Set<string>>(new Set());

  useEffect(() => {
    Promise.all([
      api.overdueFollowups(),
      api.upcomingFollowups(),
    ])
      .then(([o, u]) => { setOverdue(o); setUpcoming(u); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleNudge = async (id: string) => {
    setNudging(id);
    try {
      await api.nudgeAction(id);
      setNudged(prev => new Set(prev).add(id));
    } catch (e: any) {
      alert(e.message);
    } finally {
      setNudging(null);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64 text-gray-400">Loading...</div>;
  if (error) return <div className="text-red-500 p-4">Error: {error}</div>;

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Follow-ups</h2>

      {/* Overdue section */}
      <div className="mb-10">
        <div className="flex items-center gap-3 mb-4">
          <h3 className="text-lg font-semibold">Overdue Items</h3>
          {overdue && overdue.total_overdue > 0 && (
            <span className="bg-red-100 text-red-700 text-xs font-bold px-2.5 py-0.5 rounded-full">
              {overdue.total_overdue}
            </span>
          )}
        </div>

        {!overdue || overdue.total_overdue === 0 ? (
          <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-100 text-center text-gray-400">
            No overdue items
          </div>
        ) : (
          <div className="space-y-4">
            {Object.entries(overdue.by_assignee).map(([assignee, items]) => (
              <div key={assignee} className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
                <div className="bg-gray-50 px-6 py-3 border-b border-gray-100">
                  <span className="text-sm font-semibold text-gray-700">
                    {assignee === 'unassigned' ? 'Unassigned' : `Assignee: ${assignee.slice(0, 8)}...`}
                  </span>
                  <span className="text-xs text-gray-400 ml-2">({items.length} items)</span>
                </div>
                <div className="divide-y divide-gray-50">
                  {items.map(item => (
                    <div key={item.id} className="px-6 py-4 flex items-center justify-between">
                      <div className="flex-1 min-w-0 mr-4">
                        <p className="text-sm text-gray-900 truncate">{item.description}</p>
                        <div className="flex items-center gap-3 mt-1">
                          <span className={`text-xs px-2 py-0.5 rounded-full ${priorityColors[item.priority] || 'bg-gray-100'}`}>
                            {item.priority}
                          </span>
                          <span className="text-xs text-red-500 font-medium">
                            {item.days_overdue}d overdue
                          </span>
                          <span className="text-xs text-gray-400">
                            Created {new Date(item.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={() => handleNudge(item.id)}
                        disabled={nudging === item.id || nudged.has(item.id)}
                        className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                          nudged.has(item.id)
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gneva-600 text-white hover:bg-gneva-700 disabled:opacity-50'
                        }`}
                      >
                        {nudged.has(item.id) ? 'Nudged' : nudging === item.id ? '...' : 'Nudge'}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Upcoming section */}
      <div>
        <div className="flex items-center gap-3 mb-4">
          <h3 className="text-lg font-semibold">Upcoming (Next 3 Days)</h3>
          {upcoming && upcoming.total_upcoming > 0 && (
            <span className="bg-blue-100 text-blue-700 text-xs font-bold px-2.5 py-0.5 rounded-full">
              {upcoming.total_upcoming}
            </span>
          )}
        </div>

        {!upcoming || upcoming.total_upcoming === 0 ? (
          <div className="bg-white rounded-xl p-8 shadow-sm border border-gray-100 text-center text-gray-400">
            No upcoming deadlines in the next 3 days
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="divide-y divide-gray-50">
              {upcoming.action_items.map(item => (
                <div key={item.id} className="px-6 py-4 flex items-center justify-between">
                  <div className="flex-1 min-w-0 mr-4">
                    <p className="text-sm text-gray-900">{item.description}</p>
                    <div className="flex items-center gap-3 mt-1">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${priorityColors[item.priority] || 'bg-gray-100'}`}>
                        {item.priority}
                      </span>
                      <span className="text-xs text-blue-600 font-medium">
                        Due {item.due_date}
                      </span>
                      <span className="text-xs text-gray-400">{item.status}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
