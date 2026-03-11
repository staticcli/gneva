import { useState, useEffect, useCallback } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Home, Brain, MessageCircle, LogOut, CalendarDays, CheckSquare, BarChart3, Settings, Bell, Users, TrendingUp, AlertCircle } from 'lucide-react'
import { api } from '../api'
import NotificationPanel from './NotificationPanel'

interface Props {
  user: { name: string; org_name: string };
  onLogout: () => void;
  children: React.ReactNode;
}

const NAV = [
  { path: '/', label: 'Meetings', icon: Home },
  { path: '/calendar', label: 'Calendar', icon: CalendarDays },
  { path: '/actions', label: 'Actions', icon: CheckSquare },
  { path: '/analytics', label: 'Analytics', icon: BarChart3 },
  { path: '/dynamics', label: 'Team Dynamics', icon: Users },
  { path: '/roi', label: 'Meeting ROI', icon: TrendingUp },
  { path: '/followups', label: 'Follow-ups', icon: AlertCircle },
  { path: '/memory', label: 'Memory', icon: Brain },
  { path: '/ask', label: 'Ask Gneva', icon: MessageCircle },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export default function Layout({ user, onLogout, children }: Props) {
  const location = useLocation();
  const [notifOpen, setNotifOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    api.unreadCount()
      .then(data => setUnreadCount(data.unread_count ?? 0))
      .catch(() => {});

    const interval = setInterval(() => {
      api.unreadCount()
        .then(data => setUnreadCount(data.unread_count ?? 0))
        .catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleCountUpdate = useCallback((count: number) => {
    setUnreadCount(count);
  }, []);

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 bg-gneva-800 text-white flex flex-col flex-shrink-0">
        <div className="p-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Gneva</h1>
            <p className="text-gneva-300 text-sm mt-1">{user.org_name}</p>
          </div>
          <button
            onClick={() => setNotifOpen(true)}
            className="relative text-gneva-300 hover:text-white transition-colors"
          >
            <Bell size={20} />
            {unreadCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>
        </div>

        <nav className="flex-1 px-4">
          {NAV.map(({ path, label, icon: Icon }) => (
            <Link
              key={path}
              to={path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-colors ${
                (path === '/' ? location.pathname === '/' : location.pathname.startsWith(path))
                  ? 'bg-gneva-600 text-white'
                  : 'text-gneva-200 hover:bg-gneva-700'
              }`}
            >
              <Icon size={18} />
              {label}
            </Link>
          ))}
        </nav>

        <div className="p-4 border-t border-gneva-700">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gneva-300">{user.name}</span>
            <button onClick={onLogout} className="text-gneva-400 hover:text-white">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 p-8 overflow-auto">
        {children}
      </main>

      {/* Notification panel */}
      <NotificationPanel
        open={notifOpen}
        onClose={() => setNotifOpen(false)}
        onCountUpdate={handleCountUpdate}
      />
    </div>
  );
}
