import { useState, useEffect } from 'react'
import { api } from '../api'
import {
  Bot, Plus, Settings2, Trash2, Star, ChevronDown, ChevronUp,
  Shield, BarChart3, Brain, Users, Code, Scale, Megaphone,
  TrendingUp, Target, Cpu, Briefcase, Search, X, AlertCircle, Check,
} from 'lucide-react'

interface Agent {
  id: string
  name: string
  display_name: string
  role: string
  category: string
  description: string
  tools: string[] | null
  model_default: string
  voice_config: any
  avatar_path: string | null
  proactivity_level: number
  formality_level: number
  detail_level: number
  max_talk_time_pct: number
  enabled: boolean
  is_builtin: boolean
}

interface Performance {
  agent_name: string
  meeting_count: number
  avg_composite_score: number | null
  avg_accuracy: number | null
  avg_helpfulness: number | null
  avg_timing: number | null
  avg_tone: number | null
  avg_restraint: number | null
  avg_participant_rating: number | null
}

const AGENT_ICONS: Record<string, any> = {
  tia: Bot, vex: Target, prism: BarChart3, echo: Brain, sage: Users,
  nexus: Briefcase, cipher: Code, forge: Settings2, shield: Shield,
  ledger: Scale, pulse: TrendingUp, atlas: Scale, helix: Cpu,
  orbit: Users, spark: Megaphone, quantum: Cpu,
}

const CATEGORY_COLORS: Record<string, string> = {
  core: 'bg-blue-100 text-blue-700',
  specialist: 'bg-purple-100 text-purple-700',
}

function SliderField({ label, value, onChange, min = 1, max = 5, ariaLabel }: {
  label: string; value: number; onChange: (v: number) => void; min?: number; max?: number; ariaLabel?: string
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-gray-700">{label}</span>
      <div className="flex items-center gap-3 mt-1">
        <input
          type="range" min={min} max={max} value={value}
          onChange={e => onChange(Number(e.target.value))}
          className="flex-1 accent-gneva-600"
          aria-label={ariaLabel || label}
        />
        <span className="text-sm font-semibold text-gray-600 w-6 text-center">{value}</span>
      </div>
    </label>
  )
}

function ScoreBadge({ score, label }: { score: number | null; label: string }) {
  if (score === null) return null
  const color = score >= 4 ? 'text-green-600' : score >= 3 ? 'text-yellow-600' : 'text-red-600'
  return (
    <div className="text-center">
      <div className={`text-lg font-bold ${color}`}>{score.toFixed(1)}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  )
}

export default function Agents() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null)
  const [editingAgent, setEditingAgent] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<any>({})
  const [performance, setPerformance] = useState<Record<string, Performance>>({})
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({
    name: '', display_name: '', role: '', category: 'specialist',
    description: '', proactivity_level: 3, formality_level: 3, detail_level: 3,
  })
  const [saving, setSaving] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')

  useEffect(() => {
    loadAgents()
  }, [])

  async function loadAgents() {
    setLoading(true)
    setError('')
    try {
      const data = await api.agents()
      setAgents(data)
    } catch (e: any) {
      setError(e.message || 'Failed to load agents')
    } finally {
      setLoading(false)
    }
  }

  async function loadPerformance(name: string) {
    if (performance[name]) return
    try {
      const data = await api.agentPerformance(name)
      setPerformance(prev => ({ ...prev, [name]: data }))
    } catch {
      // Performance data may not exist yet
    }
  }

  async function handleToggleExpand(name: string) {
    if (expandedAgent === name) {
      setExpandedAgent(null)
      setEditingAgent(null)
    } else {
      setExpandedAgent(name)
      await loadPerformance(name)
    }
  }

  async function handleSaveEdit(name: string) {
    setSaving(true)
    try {
      await api.updateAgent(name, editForm)
      setEditingAgent(null)
      setEditForm({})
      await loadAgents()
      showSuccess('Agent updated')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleCreate() {
    if (!createForm.name || !createForm.display_name || !createForm.role) {
      setError('Name, display name, and role are required')
      return
    }
    setSaving(true)
    try {
      await api.createAgent(createForm)
      setShowCreate(false)
      setCreateForm({
        name: '', display_name: '', role: '', category: 'specialist',
        description: '', proactivity_level: 3, formality_level: 3, detail_level: 3,
      })
      await loadAgents()
      showSuccess('Agent created')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(name: string) {
    if (!confirm(`Delete agent "${name}"? This cannot be undone.`)) return
    try {
      await api.deleteAgent(name)
      setExpandedAgent(null)
      await loadAgents()
      showSuccess('Agent deleted')
    } catch (e: any) {
      setError(e.message)
    }
  }

  function showSuccess(msg: string) {
    setSuccessMsg(msg)
    setTimeout(() => setSuccessMsg(''), 3000)
  }

  function startEdit(agent: Agent) {
    setEditingAgent(agent.name)
    setEditForm({
      display_name: agent.display_name,
      description: agent.description,
      proactivity_level: agent.proactivity_level,
      formality_level: agent.formality_level,
      detail_level: agent.detail_level,
      max_talk_time_pct: agent.max_talk_time_pct,
      enabled: agent.enabled,
    })
  }

  const filtered = agents.filter(a => {
    if (categoryFilter && a.category !== categoryFilter) return false
    if (search) {
      const q = search.toLowerCase()
      return a.name.includes(q) || a.display_name.toLowerCase().includes(q) || a.role.toLowerCase().includes(q)
    }
    return true
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" role="status">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gneva-600" />
        <span className="sr-only">Loading agents...</span>
      </div>
    )
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Agents</h1>
          <p className="text-gray-500 mt-1">{agents.length} agents available</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 bg-gneva-600 text-white px-4 py-2 rounded-lg hover:bg-gneva-700 transition-colors"
          aria-label="Create new agent"
        >
          <Plus size={18} /> New Agent
        </button>
      </div>

      {/* Feedback messages */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4 flex items-center gap-2" role="alert">
          <AlertCircle size={18} />
          <span>{error}</span>
          <button onClick={() => setError('')} className="ml-auto" aria-label="Dismiss error">
            <X size={16} />
          </button>
        </div>
      )}
      {successMsg && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg mb-4 flex items-center gap-2" role="status">
          <Check size={18} />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search agents..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gneva-500 focus:border-gneva-500"
            aria-label="Search agents"
          />
        </div>
        <div className="flex gap-2">
          {['all', 'core', 'specialist'].map(cat => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat === 'all' ? null : cat)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                (cat === 'all' && !categoryFilter) || categoryFilter === cat
                  ? 'bg-gneva-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
              aria-pressed={(cat === 'all' && !categoryFilter) || categoryFilter === cat}
            >
              {cat.charAt(0).toUpperCase() + cat.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Agent List */}
      <div className="space-y-3" role="list" aria-label="Agent list">
        {filtered.map(agent => {
          const Icon = AGENT_ICONS[agent.name] || Bot
          const isExpanded = expandedAgent === agent.name
          const isEditing = editingAgent === agent.name
          const perf = performance[agent.name]

          return (
            <div
              key={agent.id}
              className={`bg-white border rounded-xl transition-shadow ${
                isExpanded ? 'shadow-lg border-gneva-300' : 'shadow-sm border-gray-200 hover:shadow-md'
              }`}
              role="listitem"
            >
              {/* Header row */}
              <button
                onClick={() => handleToggleExpand(agent.name)}
                className="w-full flex items-center gap-4 px-5 py-4 text-left"
                aria-expanded={isExpanded}
                aria-controls={`agent-detail-${agent.name}`}
              >
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                  agent.enabled ? 'bg-gneva-100 text-gneva-600' : 'bg-gray-100 text-gray-400'
                }`}>
                  <Icon size={20} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-900 truncate">{agent.display_name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${CATEGORY_COLORS[agent.category] || 'bg-gray-100 text-gray-600'}`}>
                      {agent.category}
                    </span>
                    {!agent.enabled && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-600">disabled</span>
                    )}
                    {agent.is_builtin && (
                      <span className="text-xs text-gray-400">built-in</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500 truncate">{agent.role}</p>
                </div>
                <div className="hidden sm:flex items-center gap-4 text-sm text-gray-400 flex-shrink-0">
                  <span>{agent.tools?.length || 0} tools</span>
                  {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                </div>
              </button>

              {/* Expanded Detail */}
              {isExpanded && (
                <div id={`agent-detail-${agent.name}`} className="border-t border-gray-100 px-5 py-4">
                  {!isEditing ? (
                    <div className="space-y-4">
                      {/* Description */}
                      {agent.description && (
                        <p className="text-gray-600">{agent.description}</p>
                      )}

                      {/* Config bars */}
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <div>
                          <span className="text-xs text-gray-500">Proactivity</span>
                          <div className="flex items-center gap-2 mt-1">
                            <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                              <div className="h-full bg-gneva-500 rounded-full" style={{ width: `${agent.proactivity_level * 20}%` }} />
                            </div>
                            <span className="text-sm font-medium text-gray-600">{agent.proactivity_level}/5</span>
                          </div>
                        </div>
                        <div>
                          <span className="text-xs text-gray-500">Formality</span>
                          <div className="flex items-center gap-2 mt-1">
                            <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                              <div className="h-full bg-purple-500 rounded-full" style={{ width: `${agent.formality_level * 20}%` }} />
                            </div>
                            <span className="text-sm font-medium text-gray-600">{agent.formality_level}/5</span>
                          </div>
                        </div>
                        <div>
                          <span className="text-xs text-gray-500">Detail Level</span>
                          <div className="flex items-center gap-2 mt-1">
                            <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                              <div className="h-full bg-amber-500 rounded-full" style={{ width: `${agent.detail_level * 20}%` }} />
                            </div>
                            <span className="text-sm font-medium text-gray-600">{agent.detail_level}/5</span>
                          </div>
                        </div>
                      </div>

                      {/* Performance */}
                      {perf && perf.meeting_count > 0 && (
                        <div>
                          <h4 className="text-sm font-semibold text-gray-700 mb-2">
                            Performance ({perf.meeting_count} meetings)
                          </h4>
                          <div className="flex gap-6 flex-wrap">
                            <ScoreBadge score={perf.avg_composite_score} label="Overall" />
                            <ScoreBadge score={perf.avg_accuracy} label="Accuracy" />
                            <ScoreBadge score={perf.avg_helpfulness} label="Helpful" />
                            <ScoreBadge score={perf.avg_timing} label="Timing" />
                            <ScoreBadge score={perf.avg_tone} label="Tone" />
                            <ScoreBadge score={perf.avg_restraint} label="Restraint" />
                            {perf.avg_participant_rating && (
                              <div className="text-center">
                                <div className="text-lg font-bold text-gneva-600 flex items-center gap-1">
                                  <Star size={14} /> {perf.avg_participant_rating.toFixed(1)}
                                </div>
                                <div className="text-xs text-gray-500">User Rating</div>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Model & tools */}
                      <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                        <span>Model: <code className="text-gray-700">{agent.model_default}</code></span>
                        <span>Talk time: {(agent.max_talk_time_pct * 100).toFixed(0)}%</span>
                      </div>

                      {/* Actions */}
                      <div className="flex gap-2 pt-2">
                        <button
                          onClick={() => startEdit(agent)}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                          aria-label={`Configure ${agent.display_name}`}
                        >
                          <Settings2 size={14} /> Configure
                        </button>
                        {!agent.is_builtin && (
                          <button
                            onClick={() => handleDelete(agent.name)}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-colors"
                            aria-label={`Delete ${agent.display_name}`}
                          >
                            <Trash2 size={14} /> Delete
                          </button>
                        )}
                      </div>
                    </div>
                  ) : (
                    /* Edit Form */
                    <div className="space-y-4">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <label className="block">
                          <span className="text-sm font-medium text-gray-700">Display Name</span>
                          <input
                            type="text"
                            value={editForm.display_name || ''}
                            onChange={e => setEditForm({ ...editForm, display_name: e.target.value })}
                            className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gneva-500 focus:border-gneva-500"
                          />
                        </label>
                        <label className="block">
                          <span className="text-sm font-medium text-gray-700">Max Talk Time</span>
                          <input
                            type="number"
                            min={0} max={100} step={5}
                            value={Math.round((editForm.max_talk_time_pct || 0) * 100)}
                            onChange={e => setEditForm({ ...editForm, max_talk_time_pct: Number(e.target.value) / 100 })}
                            className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gneva-500 focus:border-gneva-500"
                          />
                        </label>
                      </div>
                      <label className="block">
                        <span className="text-sm font-medium text-gray-700">Description</span>
                        <textarea
                          value={editForm.description || ''}
                          onChange={e => setEditForm({ ...editForm, description: e.target.value })}
                          rows={2}
                          className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gneva-500 focus:border-gneva-500"
                        />
                      </label>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <SliderField
                          label="Proactivity" value={editForm.proactivity_level || 3}
                          onChange={v => setEditForm({ ...editForm, proactivity_level: v })}
                        />
                        <SliderField
                          label="Formality" value={editForm.formality_level || 3}
                          onChange={v => setEditForm({ ...editForm, formality_level: v })}
                        />
                        <SliderField
                          label="Detail Level" value={editForm.detail_level || 3}
                          onChange={v => setEditForm({ ...editForm, detail_level: v })}
                        />
                      </div>
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={editForm.enabled ?? true}
                          onChange={e => setEditForm({ ...editForm, enabled: e.target.checked })}
                          className="w-4 h-4 rounded border-gray-300 text-gneva-600 focus:ring-gneva-500"
                        />
                        <span className="text-sm text-gray-700">Enabled</span>
                      </label>
                      <div className="flex gap-2 pt-2">
                        <button
                          onClick={() => handleSaveEdit(agent.name)}
                          disabled={saving}
                          className="px-4 py-2 bg-gneva-600 text-white rounded-lg hover:bg-gneva-700 disabled:opacity-50 transition-colors"
                        >
                          {saving ? 'Saving...' : 'Save Changes'}
                        </button>
                        <button
                          onClick={() => { setEditingAgent(null); setEditForm({}) }}
                          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {filtered.length === 0 && !loading && (
        <div className="text-center py-12 text-gray-500" role="status">
          {search || categoryFilter ? 'No agents match your filters.' : 'No agents configured yet.'}
        </div>
      )}

      {/* Create Agent Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true" aria-label="Create new agent">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h2 className="text-lg font-bold text-gray-900">Create Agent</h2>
              <button onClick={() => setShowCreate(false)} aria-label="Close dialog">
                <X size={20} className="text-gray-400 hover:text-gray-600" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <label className="block">
                <span className="text-sm font-medium text-gray-700">Internal Name <span className="text-red-500">*</span></span>
                <input
                  type="text"
                  placeholder="my_agent"
                  pattern="^[a-z][a-z0-9_]*$"
                  value={createForm.name}
                  onChange={e => setCreateForm({ ...createForm, name: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '') })}
                  className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gneva-500 focus:border-gneva-500"
                />
                <span className="text-xs text-gray-400">Lowercase, no spaces. e.g. "finance_bot"</span>
              </label>
              <label className="block">
                <span className="text-sm font-medium text-gray-700">Display Name <span className="text-red-500">*</span></span>
                <input
                  type="text"
                  placeholder="Finance Bot"
                  value={createForm.display_name}
                  onChange={e => setCreateForm({ ...createForm, display_name: e.target.value })}
                  className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gneva-500 focus:border-gneva-500"
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-gray-700">Role <span className="text-red-500">*</span></span>
                <input
                  type="text"
                  placeholder="Financial analysis and budget tracking"
                  value={createForm.role}
                  onChange={e => setCreateForm({ ...createForm, role: e.target.value })}
                  className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gneva-500 focus:border-gneva-500"
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-gray-700">Description</span>
                <textarea
                  placeholder="What does this agent do?"
                  value={createForm.description}
                  onChange={e => setCreateForm({ ...createForm, description: e.target.value })}
                  rows={2}
                  className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gneva-500 focus:border-gneva-500"
                />
              </label>
              <div className="grid grid-cols-3 gap-4">
                <SliderField
                  label="Proactivity" value={createForm.proactivity_level}
                  onChange={v => setCreateForm({ ...createForm, proactivity_level: v })}
                />
                <SliderField
                  label="Formality" value={createForm.formality_level}
                  onChange={v => setCreateForm({ ...createForm, formality_level: v })}
                />
                <SliderField
                  label="Detail" value={createForm.detail_level}
                  onChange={v => setCreateForm({ ...createForm, detail_level: v })}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 px-6 py-4 border-t bg-gray-50 rounded-b-2xl">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={saving || !createForm.name || !createForm.display_name || !createForm.role}
                className="px-4 py-2 bg-gneva-600 text-white rounded-lg hover:bg-gneva-700 disabled:opacity-50 transition-colors"
              >
                {saving ? 'Creating...' : 'Create Agent'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
