import { useState, useEffect, useRef } from 'react'
import { Calendar, Bell, MessageSquare, Bot, Cpu, Check, ExternalLink, Mic, Trash2, Star, Play, Plus, Volume2 } from 'lucide-react'
import { api } from '../api'

interface ToggleProps {
  enabled: boolean;
  onChange: (val: boolean) => void;
  label: string;
  description?: string;
}

interface Voice {
  id: string;
  name: string;
  provider: string;
  is_default: boolean;
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

  // Voices
  const [voices, setVoices] = useState<Voice[]>([]);
  const [showAddVoice, setShowAddVoice] = useState(false);
  const [newVoiceId, setNewVoiceId] = useState('');
  const [newVoiceName, setNewVoiceName] = useState('');
  const [previewingVoice, setPreviewingVoice] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    api.voices().then(r => setVoices(r.voices || [])).catch(console.error);
  }, []);

  const showSaved = (section: string) => {
    setSaved(section);
    setTimeout(() => setSaved(null), 2000);
  };

  const handleSave = (section: string) => {
    showSaved(section);
  };

  const handleAddVoice = async () => {
    if (!newVoiceId.trim() || !newVoiceName.trim()) return;
    try {
      const r = await api.addVoice(newVoiceId.trim(), newVoiceName.trim());
      setVoices(r.voices || []);
      setNewVoiceId('');
      setNewVoiceName('');
      setShowAddVoice(false);
      showSaved('voices');
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDeleteVoice = async (voiceId: string) => {
    try {
      const r = await api.deleteVoice(voiceId);
      setVoices(r.voices || []);
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleSetDefault = async (voiceId: string) => {
    try {
      const r = await api.updateVoice(voiceId, { is_default: true });
      setVoices(r.voices || []);
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handlePreview = async (voiceId: string) => {
    // B10 fix: stop any currently playing preview
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setPreviewingVoice(voiceId);
    try {
      const r = await api.previewVoice(voiceId);
      if (r.error) {
        alert(`Preview failed: ${r.error}`);
        return;
      }
      if (r.audio) {
        const audio = new Audio(`data:audio/wav;base64,${r.audio}`);
        audioRef.current = audio;
        audio.play();
        audio.onended = () => setPreviewingVoice(null);
      }
    } catch (err: any) {
      alert(err.message);
    } finally {
      if (!audioRef.current) setPreviewingVoice(null);
    }
  };

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-2xl font-bold">Settings</h2>
      </div>

      <div className="space-y-6">
        {/* Voice Management */}
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-100 rounded-lg">
                <Volume2 size={20} className="text-indigo-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">Voice Management</h3>
                <p className="text-xs text-gray-400">Configure ElevenLabs voices for Gneva</p>
              </div>
            </div>
            <button
              onClick={() => setShowAddVoice(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 transition-colors"
            >
              <Plus size={14} />
              Add Voice
            </button>
          </div>

          {/* Add voice form */}
          {showAddVoice && (
            <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Voice Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Sarah"
                    value={newVoiceName}
                    onChange={e => setNewVoiceName(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">ElevenLabs Voice ID</label>
                  <input
                    type="text"
                    placeholder="e.g. OUBnvvuqEKdDWtapoJFn"
                    value={newVoiceId}
                    onChange={e => setNewVoiceId(e.target.value)}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none text-sm"
                  />
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => { setShowAddVoice(false); setNewVoiceId(''); setNewVoiceName(''); }}
                  className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddVoice}
                  disabled={!newVoiceId.trim() || !newVoiceName.trim()}
                  className="px-4 py-1.5 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                >
                  Add
                </button>
              </div>
            </div>
          )}

          {/* Voice list */}
          <div className="space-y-2">
            {voices.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">No voices configured</p>
            ) : (
              voices.map(v => (
                <div
                  key={v.id}
                  className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                    v.is_default ? 'border-indigo-200 bg-indigo-50' : 'border-gray-100 bg-white hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      v.is_default ? 'bg-indigo-200 text-indigo-700' : 'bg-gray-100 text-gray-500'
                    }`}>
                      <Mic size={14} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-800">{v.name}</span>
                        {v.is_default && (
                          <span className="px-1.5 py-0.5 bg-indigo-100 text-indigo-700 text-[10px] font-semibold rounded-full uppercase tracking-wide">
                            Default
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 font-mono">{v.id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handlePreview(v.id)}
                      disabled={previewingVoice === v.id}
                      title="Preview voice"
                      className="p-1.5 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors disabled:opacity-50"
                    >
                      <Play size={14} className={previewingVoice === v.id ? 'animate-pulse text-indigo-600' : ''} />
                    </button>
                    {!v.is_default && (
                      <button
                        onClick={() => handleSetDefault(v.id)}
                        title="Set as default"
                        className="p-1.5 text-gray-400 hover:text-amber-500 hover:bg-amber-50 rounded-lg transition-colors"
                      >
                        <Star size={14} />
                      </button>
                    )}
                    <button
                      onClick={() => handleDeleteVoice(v.id)}
                      title="Remove voice"
                      className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

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
