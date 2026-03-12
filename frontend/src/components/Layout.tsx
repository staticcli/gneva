import { useState, useEffect, useCallback } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Home, Brain, MessageCircle, LogOut, CalendarDays, CheckSquare,
  BarChart3, Settings, Bell, Users, TrendingUp, AlertCircle, Bot,
  Menu, X,
} from 'lucide-react'
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
  { path: '/agents', label: 'Agents', icon: Bot },
  { path: '/memory', label: 'Memory', icon: Brain },
  { path: '/ask', label: 'Ask Gneva', icon: MessageCircle },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export default function Layout({ user, onLogout, children }: Props) {
  const location = useLocation();
  const [notifOpen, setNotifOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

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
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-40 w-64 bg-gneva-800 text-white flex flex-col flex-shrink-0
          transform transition-transform duration-200 ease-in-out
          lg:relative lg:translate-x-0 lg:pointer-events-auto
          ${sidebarOpen ? 'translate-x-0 pointer-events-auto' : '-translate-x-full pointer-events-none lg:pointer-events-auto'}
        `}
        role="navigation"
        aria-label="Main navigation"
      >
        <div className="p-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Gneva</h1>
            <p className="text-gneva-300 text-sm mt-1">{user.org_name}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setNotifOpen(true)}
              className="relative text-gneva-300 hover:text-white transition-colors"
              aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
            >
              <Bell size={20} />
              {unreadCount > 0 && (
                <span className="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center" aria-hidden="true">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden text-gneva-300 hover:text-white transition-colors ml-1"
              aria-label="Close navigation"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        <nav className="flex-1 px-4 overflow-y-auto" aria-label="Primary">
          {NAV.map(({ path, label, icon: Icon }) => {
            const active = path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);
            return (
              <Link
                key={path}
                to={path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 transition-colors ${
                  active
                    ? 'bg-gneva-600 text-white'
                    : 'text-gneva-200 hover:bg-gneva-700'
                }`}
                aria-current={active ? 'page' : undefined}
              >
                <Icon size={18} aria-hidden="true" />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-gneva-700">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gneva-300 truncate">{user.name}</span>
            <button
              onClick={onLogout}
              className="text-gneva-400 hover:text-white transition-colors"
              aria-label="Log out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile header */}
        <header className="lg:hidden flex items-center gap-3 px-4 py-3 bg-white border-b border-gray-200 sticky top-0 z-20">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-gray-600 hover:text-gray-900 transition-colors"
            aria-label="Open navigation menu"
          >
            <Menu size={24} />
          </button>
          <h1 className="text-lg font-bold text-gneva-800">Gneva</h1>
          <button
            onClick={() => setNotifOpen(true)}
            className="relative ml-auto text-gray-500 hover:text-gray-700"
            aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
          >
            <Bell size={20} />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold rounded-full w-4 h-4 flex items-center justify-center" aria-hidden="true">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-auto" role="main">
          {children}
        </main>
      </div>

      {/* Notification panel */}
      <NotificationPanel
        open={notifOpen}
        onClose={() => setNotifOpen(false)}
        onCountUpdate={handleCountUpdate}
      />
    </div>
  );
}
