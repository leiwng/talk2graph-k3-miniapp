import { useStore } from '../store'

export function ProviderSwitch() {
  const debugUI = useStore((s) => s.debugUI)
  const providerName = useStore((s) => s.providerName)
  const providers = useStore((s) => s.availableProviders)
  const setProvider = useStore((s) => s.setProvider)

  if (!debugUI) return null

  const usable = providers.filter((p) => p.enabled)

  return (
    <div className="provider-switch">
      <select
        value={providerName}
        onChange={(e) => setProvider(e.target.value)}
        title="切换 LLM 模型"
      >
        {usable.map((p) => (
          <option key={p.name} value={p.name}>
            {p.model || p.name}
          </option>
        ))}
        {usable.length === 0 && (
          <option value={providerName}>{providerName}</option>
        )}
      </select>
    </div>
  )
}
