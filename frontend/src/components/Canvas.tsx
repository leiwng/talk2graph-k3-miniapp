import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'
import type { PatchOp } from '../api/types'

interface HoverInfo {
  id: string
  text: string
  x: number
  y: number
}

export function Canvas() {
  const svg = useStore((s) => s.svg)
  const dsl = useStore((s) => s.dsl)
  const solution = useStore((s) => s.solution)
  const seq = useStore((s) => s.seq)
  const busy = useStore((s) => s.busy)
  const selectedId = useStore((s) => s.selectedObjectId)
  const selectObject = useStore((s) => s.selectObject)
  const applyPatch = useStore((s) => s.applyPatch)

  const containerRef = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<HoverInfo | null>(null)

  // 注入交互：hover / 点击选中 / 拖动点
  useEffect(() => {
    const root = containerRef.current
    if (!root || !dsl) return
    const svgEl = root.querySelector<SVGSVGElement>('svg')
    if (!svgEl) return

    const objs = svgEl.querySelectorAll<SVGElement>('[data-id]')
    type H = {
      el: SVGElement
      enter: (e: MouseEvent) => void
      leave: () => void
      down: (e: MouseEvent) => void
    }
    const handlers: H[] = []

    // 拖动状态：单次注册到 document，避免离开元素丢失 mouseup
    let dragging: { id: string; startedAt: number } | null = null

    const onWindowMove = (e: MouseEvent) => {
      if (!dragging) return
      // 实时更新 hover 信息为 "正在拖动 X"
      const rect = root.getBoundingClientRect()
      setHover({
        id: dragging.id,
        text: `拖动 ${dragging.id} 到此处（松手提交）`,
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      })
    }
    const onWindowUp = async (e: MouseEvent) => {
      if (!dragging) return
      const moved = performance.now() - dragging.startedAt
      const id = dragging.id
      const draggingState = dragging
      dragging = null
      window.removeEventListener('mousemove', onWindowMove)
      window.removeEventListener('mouseup', onWindowUp)
      setHover(null)

      // 拖动太短认为是点击；不发 patch
      if (moved < 120) return
      const math = clientToMath(svgEl, e.clientX, e.clientY)
      if (!math || !dsl) return
      const idx = dsl.objects.findIndex((o) => o.id === id)
      if (idx < 0) return
      const ops: PatchOp[] = [
        {
          op: dsl.objects[idx].hint == null ? 'add' : 'replace',
          path: `/objects/${idx}/hint`,
          value: [math.x, math.y],
        } as any,
      ]
      await applyPatch(ops)
    }

    objs.forEach((el) => {
      const id = el.getAttribute('data-id')!
      if (id === selectedId) el.classList.add('t2g-selected')

      const onEnter = (e: MouseEvent) => {
        if (dragging) return
        const rect = root.getBoundingClientRect()
        const text = describe(id, dsl, solution)
        setHover({ id, text, x: e.clientX - rect.left, y: e.clientY - rect.top })
      }
      const onLeave = () => {
        if (!dragging) setHover(null)
      }
      const onDown = (e: MouseEvent) => {
        e.stopPropagation()
        // 仅 point 支持拖动
        const obj = dsl.objects.find((o) => o.id === id)
        if (obj && obj.kind === 'point') {
          dragging = { id, startedAt: performance.now() }
          window.addEventListener('mousemove', onWindowMove)
          window.addEventListener('mouseup', onWindowUp)
        }
        // 点击：选中（即使拖动也保留选中态）
        selectObject(selectedId === id ? null : id)
      }
      el.addEventListener('mouseenter', onEnter)
      el.addEventListener('mouseleave', onLeave)
      el.addEventListener('mousedown', onDown)
      handlers.push({ el, enter: onEnter, leave: onLeave, down: onDown })
    })

    return () => {
      handlers.forEach(({ el, enter, leave, down }) => {
        el.removeEventListener('mouseenter', enter)
        el.removeEventListener('mouseleave', leave)
        el.removeEventListener('mousedown', down)
        el.classList.remove('t2g-selected')
      })
      window.removeEventListener('mousemove', onWindowMove)
      window.removeEventListener('mouseup', onWindowUp)
    }
  }, [svg, selectedId, dsl, solution, selectObject, applyPatch])

  return (
    <section>
      <div className="section-header">画板</div>
      <div className="canvas-wrap" ref={containerRef}>
        {svg ? (
          <div
            dangerouslySetInnerHTML={{ __html: svg }}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          />
        ) : dsl ? (
          <div className="placeholder">
            {busy ? '渲染中…' : '点击撤销/重做后会自动刷新画板'}
          </div>
        ) : (
          <div className="placeholder">
            还没有图形。<br />
            在左侧输入"画一个等边三角形"试试。
          </div>
        )}
        {hover && (
          <div
            className="canvas-tooltip"
            style={{ left: hover.x + 12, top: hover.y + 12 }}
          >
            {hover.text}
          </div>
        )}
        {svg && <FeedbackOverlay />}
      </div>
      <div className="canvas-footer">
        <span>seq #{seq}</span>
        {solution && <span>残差：{solution.residual.toExponential(2)}</span>}
        {dsl && (
          <span>
            对象 {dsl.objects.length} · 约束 {dsl.constraints.length}
          </span>
        )}
        {dsl && dsl.objects.some((o) => o.kind === 'point') && (
          <span style={{ color: 'var(--muted)' }}>提示：可拖动点重新摆位</span>
        )}
      </div>
    </section>
  )
}

function clientToMath(svgEl: SVGSVGElement, clientX: number, clientY: number) {
  // 通过 SVGPoint matrixTransform 得到 SVG 内坐标
  const pt = svgEl.createSVGPoint()
  pt.x = clientX
  pt.y = clientY
  const ctm = svgEl.getScreenCTM()
  if (!ctm) return null
  const inv = ctm.inverse()
  const local = pt.matrixTransform(inv)

  const scale = Number(svgEl.dataset.t2gScale || '1')
  const offsetX = Number(svgEl.dataset.t2gOffsetX || '0')
  const offsetY = Number(svgEl.dataset.t2gOffsetY || '0')
  const minX = Number(svgEl.dataset.t2gBboxMinx || '0')
  const minY = Number(svgEl.dataset.t2gBboxMiny || '0')
  const cs = Number(svgEl.dataset.t2gCanvasSize || '480')

  const mx = minX + (local.x - offsetX) / scale
  const my = minY + (cs - offsetY - local.y) / scale
  return { x: mx, y: my }
}

function describe(
  id: string,
  dsl: ReturnType<typeof useStore.getState>['dsl'],
  sol: ReturnType<typeof useStore.getState>['solution'],
): string {
  if (!dsl) return id
  const obj = dsl.objects.find((o) => o.id === id)
  if (!obj) return id
  const label = dsl.labels?.[id] ?? id
  switch (obj.kind) {
    case 'point': {
      const c = sol?.coordinates?.[id]
      if (c) return `${label}(${c[0].toFixed(2)}, ${c[1].toFixed(2)})`
      return `点 ${label}`
    }
    case 'segment': {
      const a = sol?.coordinates?.[obj.a!]
      const b = sol?.coordinates?.[obj.b!]
      if (a && b) {
        const d = Math.hypot(a[0] - b[0], a[1] - b[1])
        return `|${obj.a}${obj.b}| = ${d.toFixed(2)}`
      }
      return `线段 ${obj.a}${obj.b}`
    }
    case 'circle': {
      const info = sol?.circles?.[id]
      if (info) return `圆 ${id}：r = ${info.radius.toFixed(2)}`
      return `圆 ${id}`
    }
    case 'polygon':
      return `多边形 [${(obj.vertices || []).join('')}]`
    default:
      return `${obj.kind} ${id}`
  }
}

function FeedbackOverlay() {
  const sendFeedback = useStore((s) => s.sendFeedback)
  const seq = useStore((s) => s.seq)
  const [sent, setSent] = useState<'good' | 'bad' | null>(null)
  const [showBadInput, setShowBadInput] = useState(false)
  const [comment, setComment] = useState('')

  // 切换图形（seq 变）时重置
  useEffect(() => {
    setSent(null)
    setShowBadInput(false)
    setComment('')
  }, [seq])

  const onGood = async () => {
    setSent('good')
    await sendFeedback('good')
  }
  const onBad = () => {
    setShowBadInput(true)
  }
  const submitBad = async () => {
    setSent('bad')
    await sendFeedback('bad', comment.trim() || undefined)
    setShowBadInput(false)
  }

  if (sent) {
    return (
      <div className="feedback-overlay sent">
        <span style={{ fontSize: 11 }}>已收到反馈，谢谢 🙏</span>
      </div>
    )
  }

  return (
    <div className="feedback-overlay">
      {!showBadInput ? (
        <>
          <button
            className="feedback-btn"
            onClick={onGood}
            title="这道题画对了"
          >
            👍 不错
          </button>
          <button
            className="feedback-btn"
            onClick={onBad}
            title="这道题画错了"
          >
            👎 不对
          </button>
        </>
      ) : (
        <div className="feedback-comment-box">
          <input
            type="text"
            placeholder="哪里不对？（可选）"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') submitBad()
              if (e.key === 'Escape') setShowBadInput(false)
            }}
            autoFocus
            style={{ width: 180 }}
          />
          <button onClick={submitBad} className="primary" style={{ fontSize: 11 }}>
            提交
          </button>
          <button
            onClick={() => setShowBadInput(false)}
            style={{ fontSize: 11 }}
          >
            取消
          </button>
        </div>
      )}
    </div>
  )
}
