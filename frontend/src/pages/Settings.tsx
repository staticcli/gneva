import { useState } from 'react'
import { Calendar, Bell, MessageSquare, Bot, Cpu, Check, ExternalLink } from 'lucide-react'

interface ToggleProps {
  enabled: boolean;
  onChange: (val: boolean) => void;
  label: string;
  description?: string;
}

function Toggle({ enabled, onChange, label, description }: ToggleProps) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <p className="text-sm font-medium text-gray-700">{label}</p>
        {description && <p className="text-xs text-gray-400 mt-0.5">{description}</p>}
      </div>
      <button
        onClick={() => onChange(!enabled)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
          enabled ? 'bg-gneva-600' : 'bg-gray-300'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            enabled ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
}

export default function Settings() {
  // Calendar
  const [googleConnected, setGoogleConnected] = useState(false);
  const [outlookConnected, setOutlookConnected] = useState(false);

  // Notifications
  const [emailNotifs, setEmailNotifs] = useState(true);
  const [inAppNotifs, setInAppNotifs] = useState(true);

  // Slack
  const [slackConnected, setSlackConnected] = useState(false);
  const [slackChannel, setSlackChannel] = useState('#general');

  // Bot
  const [botName, setBotName] = useState('Gneva');
  const [consentMessage, setConsentMessage] = useState('This meeting is being recorded and transcribed by Gneva.');
  const [autoJoin, setAutoJoin] = useState(false);

  // AI
  const [aiBackend, setAiBackend] = useState('claude');

  const [saved, setSaved] = useState<string | null>(null);

  const showSaved = (section: string) => {
    setSaved(section);
    setTimeout(() => setSaved(null), 2000);
  };

  const handleSave = (section: string) => {
    showSaved(section);
  };

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-2xl font-bold">Settings</h2>
      </div>

      <div className="space-y-6">
        {/* Calendar Integration */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-gneva-100 rounded-lg">
              <Calendar size={20} className="text-gneva-600" />
            </div>
            <h3 className="text-lg font-semibold">Calendar Integration</h3>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between py-3 border-b border-gray-50">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-white border border-gray-200 rounded-lg flex items-center justify-center">
                  <span className="text-sm font-bold text-blue-500">G</span>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-700">Google Calendar</p>
                  <p className="text-xs text-gray-400">
                    {googleConnected ? 'Connected' : 'Not connected'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  if (googleConnected) {
                    setGoogleConnected(false);
                  } else {
                    setGoogleConnected(true);
                    showSaved('calendar');
                  }
                }}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  googleConnected
                    ? 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    : 'bg-gneva-600 text-white hover:bg-gneva-700'
                }`}
              >
                {googleConnected ? 'Disconnect' : 'Connect'}
              </button>
            </div>

            <div className="flex items-center justify-between py-3">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-white border border-gray-200 rounded-lg flex items-center justify-center">
                  <span className="text-sm font-bold text-blue-700">O</span>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-700">Microsoft Outlook</p>
                  <p className="text-xs text-gray-400">
                    {outlookConnected ? 'Connected' : 'Not connected'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  if (outlookConnected) {
                    setOutlookConnected(false);
                  } else {
                    setOutlookConnected(true);
                    showSaved('calendar');
                  }
                }}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  outlookConnected
                    ? 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    : 'bg-gneva-600 text-white hover:bg-gneva-700'
                }`}
              >
                {outlookConnected ? 'Disconnect' : 'Connect'}
              </button>
            </div>
          </div>
        </div>

        {/* Notifications */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Bell size={20} className="text-blue-600" />
            </div>
            <h3 className="text-lg font-semibold">Notifications</h3>
          </div>

          <div className="divide-y divide-gray-50">
            <Toggle
              enabled={emailNotifs}
              onChange={setEmailNotifs}
              label="Email Notifications"
              description="Receive meeting summaries and action items via email"
            />
            <Toggle
              enabled={inAppNotifs}
              onChange={setInAppNotifs}
              label="In-App Notifications"
              description="Show notifications in the Gneva dashboard"
            />
          </div>

          <div className="mt-4 flex justify-end">
            <button
              onClick={() => handleSave('notifications')}
              className="px-4 py-2 bg-gneva-600 text-white text-sm rounded-lg hover:bg-gneva-700 transition-colors flex items-center gap-2"
            >
              {saved === 'notifications' ? <><Check size={14} /> Saved</> : 'Save'}
            </button>
          </div>
        </div>

        {/* Slack Integration */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-purple-100 rounded-lg">
              <MessageSquare size={20} className="text-purple-600" />
            </div>
            <h3 className="text-lg font-semibold">Slack Integration</h3>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-700">Workspace Connection</p>
                <p className="text-xs text-gray-400">
                  {slackConnected ? 'Connected to workspace' : 'Not connected'}
                </p>
              </div>
              <button
                onClick={() => {
                  if (slackConnected) {
                    setSlackConnected(false);
                  } else {
                    setSlackConnected(true);
                    showSaved('slack');
                  }
                }}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-1 ${
                  slackConnected
                    ? 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    : 'bg-purple-600 text-white hover:bg-purple-700'
                }`}
              >
                {slackConnected ? 'Disconnect' : <><ExternalLink size={14} /> Connect Slack</>}
              </button>
            </div>

            {slackConnected && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Default Channel
                </label>
                <input
                  type="text"
                  value={slackChannel}
                  onChange={e => setSlackChannel(e.target.value)}
                  placeholder="#channel-name"
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-gneva-500 outline-none text-sm"
                />
              </div>
            )}
          </div>

          {slackConnected && (
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => handleSave('slack')}
                className="px-4 py-2 bg-gneva-600 text-white text-sm rounded-lg hover:bg-gneva-700 transition-colors flex items-center gap-2"
              >
                {saved === 'slack' ? <><Check size={14} /> Saved</> : 'Save'}
              </button>
            </div>
          )}
        </div>

        {/* Meeting Bot */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-green-100 rounded-lg">
              <Bot size={20} className="text-green-600" />
            </div>
            <h3 className="text-lg font-semibold">Meeting Bot</h3>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Bot Display Name
              </label>
              <input
                type="text"
                value={botName}
                onChange={e => setBotName(e.target.value)}
                placeholder="Gneva"
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-gneva-500 outline-none text-sm"
              />
              <p className="text-xs text-gray-400 mt-1">
                This name appears when the bot joins a meeting
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Consent Message
              </label>
              <textarea
                value={consentMessage}
                onChange={e => setConsentMessage(e.target.value)}
                rows={2}
                className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-gneva-500 outline-none text-sm resize-none"
              />
              <p className="text-xs text-gray-400 mt-1">
                Displayed in chat when the bot joins a meeting
              </p>
            </div>

            <Toggle
              enabled={autoJoin}
              onChange={setAutoJoin}
              label="Auto-Join Calendar Meetings"
              description="Automatically send the bot to all meetings on your calendar"
            />
          </div>

          <div className="mt-4 flex justify-end">
            <button
              onClick={() => handleSave('bot')}
              className="px-4 py-2 bg-gneva-600 text-white text-sm rounded-lg hover:bg-gneva-700 transition-colors flex items-center gap-2"
            >
              {saved === 'bot' ? <><Check size={14} /> Saved</> : 'Save'}
            </button>
          </div>
        </div>

        {/* AI Settings */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-amber-100 rounded-lg">
              <Cpu size={20} className="text-amber-600" />
            </div>
            <h3 className="text-lg font-semibold">AI Settings</h3>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              AI Backend
            </label>
            <div className="space-y-2">
              <label className="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors">
                <input
                  type="radio"
                  name="ai_backend"
                  value="claude"
                  checked={aiBackend === 'claude'}
                  onChange={e => setAiBackend(e.target.value)}
                  className="text-gneva-600 focus:ring-gneva-500"
                />
                <div>
                  <p className="text-sm font-medium text-gray-700">Claude (Anthropic)</p>
                  <p className="text-xs text-gray-400">Cloud-based AI for summaries, action items, and analysis</p>
                </div>
              </label>
              <label className="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors">
                <input
                  type="radio"
                  name="ai_backend"
                  value="ollama"
                  checked={aiBackend === 'ollama'}
                  onChange={e => setAiBackend(e.target.value)}
                  className="text-gneva-600 focus:ring-gneva-500"
                />
                <div>
                  <p className="text-sm font-medium text-gray-700">Ollama (Local)</p>
                  <p className="text-xs text-gray-400">Self-hosted AI for privacy-sensitive deployments</p>
                </div>
              </label>
            </div>
          </div>

          <div className="mt-4 flex justify-end">
            <button
              onClick={() => handleSave('ai')}
              className="px-4 py-2 bg-gneva-600 text-white text-sm rounded-lg hover:bg-gneva-700 transition-colors flex items-center gap-2"
            >
              {saved === 'ai' ? <><Check size={14} /> Saved</> : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
