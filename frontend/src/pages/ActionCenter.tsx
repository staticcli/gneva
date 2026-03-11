import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { CheckSquare, AlertTriangle, Clock, ArrowRight, User, CalendarDays, ExternalLink } from 'lucide-react'
import { api } from '../api'

interface ActionItem {
  id: string;
  description: string;
  assignee_id: string | null;
  due_date: string | null;
  priority: string;
  status: string;
  meeting_id: string | null;
  created_at: string;
}

interface FollowUp {
  id: string;
  description: string;
  status: string;
  due_date: string | null;
  completed_at: string | null;
  meeting_id: string | null;
}

type TabKey = 'all' | 'mine' | 'overdue' | 'followups';

export default function ActionCenter() {
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [followUps, setFollowUps] = useState<FollowUp[]>([]);
  const [activeTab, setActiveTab] = useState<TabKey>('all');
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    api.me().then(data => setUserId(data.id)).catch(() => {});
  }, []);

  useEffect(() => {
    Promise.all([
      api.actionItems().catch(() => []),
      api.followUps().catch(() => []),
    ]).then(([actionsData, followUpsData]) => {
      const items = Array.isArray(actionsData) ? actionsData : actionsData?.action_items || [];
      setActions(items);
      const fups = Array.isArray(followUpsData) ? followUpsData : followUpsData?.follow_ups || [];
      setFollowUps(fups);
    }).finally(() => setLoading(false));
  }, []);

  const isOverdue = (item: ActionItem) => {
    if (!item.due_date || item.status === 'done') return false;
    return new Date(item.due_date) < new Date();
  };

  const overdueItems = actions.filter(isOverdue);
  const openCount = actions.filter(a => a.status === 'open').length;
  const inProgressCount = actions.filter(a => a.status === 'in_progress').length;
  const overdueCount = overdueItems.length;

  const filteredActions = () => {
    switch (activeTab) {
      case 'mine':
        return actions.filter(a => a.assignee_id === userId || a.assignee_id === null);
      case 'overdue':
        return overdueItems;
      default:
        return actions;
    }
  };

  const handleStatusCycle = async (item: ActionItem) => {
    const next: Record<string, string> = {
      open: 'in_progress',
      in_progress: 'done',
      done: 'open',
    };
    const newStatus = next[item.status] || 'open';
    try {
      await api.updateAction(item.id, { status: newStatus });
      setActions(prev =>
        prev.map(a => a.id === item.id ? { ...a, status: newStatus } : a)
      );
    } catch (err) {
      console.error(err);
    }
  };

  const handleFollowUpComplete = async (id: string) => {
    try {
      await api.updateFollowUp(id, { status: 'done' });
      setFollowUps(prev =>
        prev.map(f => f.id === id ? { ...f, status: 'done', completed_at: new Date().toISOString() } : f)
      );
    } catch (err) {
      console.error(err);
    }
  };

  const priorityBadge = (priority: string) => {
    const colors: Record<string, string> = {
      high: 'bg-red-100 text-red-700',
      medium: 'bg-yellow-100 text-yellow-700',
      low: 'bg-green-100 text-green-700',
    };
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[priority] || 'bg-gray-100 text-gray-700'}`}>
        {priority}
      </span>
    );
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      open: 'bg-blue-100 text-blue-700',
      in_progress: 'bg-yellow-100 text-yellow-700',
      done: 'bg-green-100 text-green-700',
    };
    const labels: Record<string, string> = {
      open: 'Open',
      in_progress: 'In Progress',
      done: 'Done',
    };
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-700'}`}>
        {labels[status] || status}
      </span>
    );
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return null;
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  };

  const tabs: { key: TabKey; label: string; count?: number }[] = [
    { key: 'all', label: 'All', count: actions.length },
    { key: 'mine', label: 'My Items' },
    { key: 'overdue', label: 'Overdue', count: overdueCount },
    { key: 'followups', label: 'Follow-ups', count: followUps.length },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-400">
        Loading actions...
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-2xl font-bold">Action Center</h2>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-100 flex items-center gap-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <CheckSquare size={20} className="text-blue-600" />
          </div>
          <div>
            <p className="text-2xl font-bold">{openCount}</p>
            <p className="text-sm text-gray-500">Open</p>
          </div>
        </div>
        <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-100 flex items-center gap-3">
          <div className="p-2 bg-yellow-100 rounded-lg">
            <Clock size={20} className="text-yellow-600" />
          </div>
          <div>
            <p className="text-2xl font-bold">{inProgressCount}</p>
            <p className="text-sm text-gray-500">In Progress</p>
          </div>
        </div>
        <div className="bg-white rounded-xl p-4 shadow-sm border border-gray-100 flex items-center gap-3">
          <div className="p-2 bg-red-100 rounded-lg">
            <AlertTriangle size={20} className="text-red-600" />
          </div>
          <div>
            <p className="text-2xl font-bold">{overdueCount}</p>
            <p className="text-sm text-gray-500">Overdue</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? 'border-gneva-600 text-gneva-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className={`ml-1.5 px-1.5 py-0.5 rounded-full text-xs ${
                activeTab === tab.key ? 'bg-gneva-100 text-gneva-700' : 'bg-gray-100 text-gray-500'
              }`}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Follow-ups tab */}
      {activeTab === 'followups' ? (
        <div>
          {followUps.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <CheckSquare size={40} className="mx-auto mb-3 opacity-40" />
              <p>No follow-ups yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {followUps.map(fu => (
                <div
                  key={fu.id}
                  className={`bg-white rounded-xl p-5 shadow-sm border border-gray-100 ${
                    fu.status === 'done' ? 'opacity-60' : ''
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <p className={`font-medium ${fu.status === 'done' ? 'line-through text-gray-400' : 'text-gray-900'}`}>
                        {fu.description}
                      </p>
                      <div className="flex items-center gap-3 mt-2 text-sm text-gray-500">
                        {fu.due_date && (
                          <span className="flex items-center gap-1">
                            <CalendarDays size={14} />
                            {formatDate(fu.due_date)}
                          </span>
                        )}
                        {fu.meeting_id && (
                          <Link
                            to={`/meetings/${fu.meeting_id}`}
                            className="flex items-center gap-1 text-gneva-600 hover:text-gneva-700"
                          >
                            <ExternalLink size={12} />
                            Source meeting
                          </Link>
                        )}
                        {fu.completed_at && (
                          <span className="text-green-600">
                            Completed {formatDate(fu.completed_at)}
                          </span>
                        )}
                      </div>
                    </div>
                    {fu.status !== 'completed' && (
                      <button
                        onClick={() => handleFollowUpComplete(fu.id)}
                        className="text-sm text-gneva-600 hover:text-gneva-700 font-medium flex-shrink-0 ml-4"
                      >
                        Mark Complete
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* Action items list */
        <div>
          {filteredActions().length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <CheckSquare size={40} className="mx-auto mb-3 opacity-40" />
              <p>No action items{activeTab === 'overdue' ? ' overdue' : ''}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredActions().map(item => (
                <div
                  key={item.id}
                  className={`bg-white rounded-xl p-5 shadow-sm border transition-shadow hover:shadow-md ${
                    isOverdue(item)
                      ? 'border-red-200 bg-red-50/30'
                      : 'border-gray-100'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        {priorityBadge(item.priority)}
                        {statusBadge(item.status)}
                        {isOverdue(item) && (
                          <span className="flex items-center gap-1 text-xs text-red-600 font-medium">
                            <AlertTriangle size={12} />
                            Overdue
                          </span>
                        )}
                      </div>
                      <p className={`font-medium mt-2 ${item.status === 'done' ? 'line-through text-gray-400' : 'text-gray-900'}`}>
                        {item.description}
                      </p>
                      <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                        <span className="flex items-center gap-1">
                          <User size={14} />
                          {item.assignee_id ? (item.assignee_id === userId ? 'Me' : item.assignee_id.slice(0, 8)) : 'Unassigned'}
                        </span>
                        {item.due_date && (
                          <span className={`flex items-center gap-1 ${isOverdue(item) ? 'text-red-600' : ''}`}>
                            <CalendarDays size={14} />
                            {formatDate(item.due_date)}
                          </span>
                        )}
                        {item.meeting_id && (
                          <Link
                            to={`/meetings/${item.meeting_id}`}
                            className="flex items-center gap-1 text-gneva-600 hover:text-gneva-700"
                          >
                            <ExternalLink size={12} />
                            Source meeting
                          </Link>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => handleStatusCycle(item)}
                      className="flex items-center gap-1 text-sm text-gneva-600 hover:text-gneva-700 font-medium flex-shrink-0 ml-4 px-3 py-1.5 rounded-lg hover:bg-gneva-50 transition-colors"
                      title={`Move to ${item.status === 'open' ? 'In Progress' : item.status === 'in_progress' ? 'Done' : 'Open'}`}
                    >
                      {item.status === 'open' && <>Start <ArrowRight size={14} /></>}
                      {item.status === 'in_progress' && <>Complete <ArrowRight size={14} /></>}
                      {item.status === 'done' && <>Reopen</>}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
