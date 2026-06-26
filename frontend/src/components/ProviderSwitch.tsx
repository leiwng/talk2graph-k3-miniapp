import { useStore } from '../store'

export function ProviderSwitch() {
  const providerName = useStore((s) => s.providerName)
  const providers = useStore((s) => s.availableProviders)
  const setProvider = useStore((s) => s.setProvider)

  return (
    <select
      value={providerName}
      onChange={(e) => setProvider(e.target.value)}
      title="切换 LLM"
    >
      {providers.map((p) => (
        <option key={p.name} value={p.name} disabled={!p.enabled}>
          {labelOf(p.name, p.model)}
          {!p.enabled ? '（未配置）' : ''}
        </option>
      ))}
      {providers.length === 0 && (
        <option value={providerName}>{labelOf(providerName, '')}</option>
      )}
    </select>
  )
}

function labelOf(name: string, model: string): string {
  switch (name) {
    case 'zhipu':
      return model ? `智谱 ${model}` : '智谱'
    case 'volcengine':
      return model ? `火山方舟 ${shorten(model)}` : '火山方舟'
    case 'deepseek':
      return model ? `DeepSeek ${model}` : 'DeepSeek'
    case 'minimax':
      return model ? `MiniMax ${model}` : 'MiniMax'
    default:
      return model ? `${name} (${model})` : name
  }
}

function shorten(s: string): string {
  if (s.length <= 18) return s
  return s.slice(0, 8) + '…' + s.slice(-6)
}
