import { useStore } from '../store'
import type { Constraint, GeoObject, PatchOp } from '../api/types'

export function RightPanel() {
  const dsl = useStore((s) => s.dsl)
  const selected = useStore((s) => s.selectedObjectId)
  const select = useStore((s) => s.selectObject)
  const applyPatch = useStore((s) => s.applyPatch)
  const busy = useStore((s) => s.busy)

  if (!dsl) {
    return (
      <section className="right-panel">
        <div className="section-header">对象</div>
        <div style={{ padding: 12, color: 'var(--muted)', fontSize: 12 }}>
          （空）
        </div>
      </section>
    )
  }

  return (
    <section className="right-panel">
      <div className="section-header">对象 ({dsl.objects.length})</div>
      <div className="tree">
        {dsl.objects.map((o) => (
          <ObjectItem
            key={o.id}
            obj={o}
            selected={selected === o.id}
            onClick={() => select(selected === o.id ? null : o.id)}
          />
        ))}
      </div>

      <div className="section-header">约束 ({dsl.constraints.length})</div>
      <div className="tree" style={{ flex: 'none', maxHeight: '30%' }}>
        {dsl.constraints.map((c, i) => (
          <ConstraintItem
            key={i}
            c={c}
            disabled={busy}
            onChangeValue={async (newVal) => {
              const ops: PatchOp[] = [
                { op: 'replace', path: `/constraints/${i}/value`, value: newVal },
              ]
              await applyPatch(ops)
            }}
            onRemove={async () => {
              const ops: PatchOp[] = [{ op: 'remove', path: `/constraints/${i}` }]
              await applyPatch(ops)
            }}
          />
        ))}
      </div>

      <PropertyPanel />
    </section>
  )
}

function ObjectItem({
  obj,
  selected,
  onClick,
}: {
  obj: GeoObject
  selected: boolean
  onClick: () => void
}) {
  const meta = describeObject(obj)
  return (
    <div
      className={`tree-item ${selected ? 'selected' : ''}`}
      onClick={onClick}
    >
      <span>
        <strong>{obj.id}</strong>
      </span>
      <span className="meta">{meta}</span>
    </div>
  )
}

function describeObject(o: GeoObject): string {
  switch (o.kind) {
    case 'point':
      return '点'
    case 'segment':
      return `线段 ${o.a}${o.b}`
    case 'line':
      return `直线 ${o.a}${o.b}`
    case 'polygon':
      return `多边形 [${(o.vertices || []).join('')}]`
    case 'circle': {
      const d = o.definition
      if (!d) return '圆'
      switch (d.type) {
        case 'center_radius':
          return `圆 (${d.center}, r=${d.radius})`
        case 'center_through':
          return `圆 (${d.center}, 过 ${d.through})`
        case 'incircle':
          return `内切圆 / ${d.of}`
        case 'circumcircle':
          return `外接圆 / ${d.of}`
        default:
          return '圆'
      }
    }
    default:
      return o.kind
  }
}

function ConstraintItem({
  c,
  disabled,
  onChangeValue,
  onRemove,
}: {
  c: Constraint
  disabled: boolean
  onChangeValue: (v: number) => void
  onRemove: () => void
}) {
  return (
    <div className="tree-item" title={JSON.stringify(c)}>
      <span>{describeConstraint(c)}</span>
      <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
        {typeof c.value === 'number' && (
          <input
            type="number"
            value={c.value}
            step="0.5"
            style={{ width: 60, fontSize: 11, padding: '2px 4px' }}
            disabled={disabled}
            onChange={(e) => {
              const v = Number(e.target.value)
              if (!Number.isNaN(v)) onChangeValue(v)
            }}
            onClick={(e) => e.stopPropagation()}
          />
        )}
        <button
          onClick={(e) => {
            e.stopPropagation()
            onRemove()
          }}
          disabled={disabled}
          style={{ fontSize: 11, padding: '2px 6px' }}
          title="删除约束"
        >
          ×
        </button>
      </span>
    </div>
  )
}

function describeConstraint(c: Constraint): string {
  switch (c.type) {
    case 'length':
      return `|${c.segment}| =`
    case 'equal_length':
      return `等长 [${(c.segments || []).join(',')}]`
    case 'angle':
      return `∠${c.a}${c.b}${c.c} =`
    case 'parallel':
      return `${c.a} ∥ ${c.b}`
    case 'perpendicular':
      return `${c.a} ⊥ ${c.b}`
    case 'collinear':
      return `共线 [${(c.points || []).join('')}]`
    case 'tangent':
      return `${c.line} 切 ${c.circle}`
    case 'on_circle':
      return `${c.point} ∈ ${c.circle}`
    case 'isoceles':
      return `${c.polygon} 等腰 @${c.apex}`
    case 'equilateral':
      return `${c.polygon} 等边`
    case 'right_triangle':
      return `${c.polygon} 直角@${c.right_at}`
    case 'radius':
      return `r(${c.circle}) =`
    default:
      return c.type
  }
}

function PropertyPanel() {
  const dsl = useStore((s) => s.dsl)
  const solution = useStore((s) => s.solution)
  const selectedId = useStore((s) => s.selectedObjectId)
  const applyPatch = useStore((s) => s.applyPatch)
  const busy = useStore((s) => s.busy)

  if (!dsl || !selectedId) {
    return (
      <div className="properties">
        <h4>属性</h4>
        <div style={{ color: 'var(--muted)' }}>点击左侧对象查看属性</div>
      </div>
    )
  }

  const obj = dsl.objects.find((o) => o.id === selectedId)
  if (!obj) return null

  const coord = solution?.coordinates?.[obj.id]
  const circle = solution?.circles?.[obj.id]
  const label = dsl.labels?.[obj.id] ?? obj.id

  return (
    <div className="properties">
      <h4>{obj.kind} — {obj.id}</h4>
      <div className="prop-row">
        <label>标签</label>
        <input
          defaultValue={label}
          disabled={busy}
          onBlur={async (e) => {
            const v = e.target.value
            if (v === label) return
            await applyPatch([
              { op: 'replace', path: `/labels/${obj.id}`, value: v },
            ])
          }}
        />
      </div>
      {coord && (
        <>
          <div className="prop-row">
            <label>X</label>
            <span className="key">{coord[0].toFixed(3)}</span>
          </div>
          <div className="prop-row">
            <label>Y</label>
            <span className="key">{coord[1].toFixed(3)}</span>
          </div>
        </>
      )}
      {circle && (
        <>
          <div className="prop-row">
            <label>圆心</label>
            <span className="key">
              ({circle.center[0].toFixed(3)}, {circle.center[1].toFixed(3)})
            </span>
          </div>
          <div className="prop-row">
            <label>半径</label>
            <span className="key">{circle.radius.toFixed(3)}</span>
          </div>
        </>
      )}
    </div>
  )
}
