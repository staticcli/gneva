import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { X, CheckCheck, Bell, MessageSquare, AlertTriangle, CheckCircle, Calendar } from 'lucide-react'
import { api } from '../api'

interface Notification {
  id: string;
  type: string;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
  meeting_id: string | null;
  action_item_id: string | null;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onCountUpdate: (count: number) => void;
}

export default function NotificationPanel({ open, onClose, onCountUpdate }: Props) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    if (open) {
      setLoading(true);
      api.notifications()
        .then((data) => {
          const items = Array.isArray(data) ? data : data.notifications || [];
          setNotifications(items);
          onCountUpdate(items.filter((n: Notification) => !n.read).length);
        })
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [open, onCountUpdate]);

  const handleMarkRead = async (id: string) => {
    try {
      await api.markRead(id);
      setNotifications(prev =>
        prev.map(n => n.id === id ? { ...n, read: true } : n)
      );
      onCountUpdate(notifications.filter(n => !n.read && n.id !== id).length);
    } catch (err) {
      console.error(err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.markAllRead();
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
      onCountUpdate(0);
    } catch (err) {
      console.error(err);
    }
  };

  const handleClick = (n: Notification) => {
    if (!n.read) handleMarkRead(n.id);
    if (n.meeting_id) {
      navigate(`/meetings/${n.meeting_id}`);
      onClose();
    } else if (n.action_item_id) {
      navigate('/actions');
      onClose();
    }
  };

  const getIcon = (type: string) => {
    switch (type) {
      case 'meeting_complete': return <MessageSquare size={16} className="text-gneva-600" />;
      case 'action_item_due': return <CheckCircle size={16} className="text-green-600" />;
      case 'follow_up_reminder': return <Calendar size={16} className="text-blue-600" />;
      case 'weekly_digest': return <Bell size={16} className="text-gneva-500" />;
      case 'contradiction_detected': return <AlertTriangle size={16} className="text-amber-600" />;
      default: return <Bell size={16} className="text-gray-500" />;
    }
  };

  const timeAgo = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 h-full w-96 bg-white shadow-2xl z-50 flex flex-col border-l border-gray-200">
        <div className="flex items-center justify-between p-4 border-b border-gray-100">
          <h3 className="text-lg font-semibold">Notifications</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={handleMarkAllRead}
              className="text-sm text-gneva-600 hover:text-gneva-700 flex items-center gap-1"
            >
              <CheckCheck size={14} />
              Mark all read
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X size={20} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-20 text-gray-400">
              Loading...
            </div>
          ) : notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <Bell size={40} className="mb-3 opacity-40" />
              <p>No notifications</p>
            </div>
          ) : (
            <div>
              {notifications.map(n => (
                <button
                  key={n.id}
                  onClick={() => handleClick(n)}
                  className={`w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors flex gap-3 ${
                    !n.read ? 'bg-gneva-50/50' : ''
                  }`}
                >
                  <div className="mt-0.5 flex-shrink-0">
                    {getIcon(n.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <p className={`text-sm ${!n.read ? 'font-semibold text-gray-900' : 'text-gray-700'}`}>
                        {n.title}
                      </p>
                      {!n.read && (
                        <span className="w-2 h-2 rounded-full bg-gneva-500 flex-shrink-0 mt-1.5" />
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5 truncate">{n.body}</p>
                    <p className="text-xs text-gray-400 mt-1">{timeAgo(n.created_at)}</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
