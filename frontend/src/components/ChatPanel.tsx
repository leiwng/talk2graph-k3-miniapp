import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'
import { EXAMPLES } from './TopBar'
import type { Message } from '../api/types'

export function ChatPanel() {
  const messages = useStore((s) => s.messages)
  const sendChat = useStore((s) => s.sendChat)
  const busy = useStore((s) => s.busy)
  const seq = useStore((s) => s.seq)
  const errorBanner = useStore((s) => s.errorBanner)
  const dismissError = useStore((s) => s.dismissError)
  const [text, setText] = useState('')
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages.length, errorBanner])

  const submit = async () => {
    const v = text.trim()
    if (!v || busy) return
    setText('')
    await sendChat(v)
  }

  const sendExample = async (nl: string) => {
    if (busy) return
    setText('')
    await sendChat(nl)
  }

  const showWelcome = messages.length === 0 && seq === 0

  return (
    <section className="chat-panel">
      <div className="section-header">对话</div>
      <div className="chat-list" ref={listRef}>
        {showWelcome && <WelcomeCard onPick={sendExample} />}
        {messages.map((m) => (
          <ChatMsgItem key={m.id} msg={m} />
        ))}
        {errorBanner && (
          <div className="chat-msg error">
            ⚠ {errorBanner}
            <button
              onClick={dismissError}
              style={{ marginLeft: 8, padding: '2px 6px', fontSize: 11 }}
            >
              关闭
            </button>
          </div>
        )}
      </div>

      <div className="chat-input">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="试试：画一个等边三角形 ABC，边长为 4"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault()
              submit()
            }
          }}
          disabled={busy}
        />
        <div className="actions">
          <span className="hint">⌘/Ctrl + Enter 发送</span>
          <button className="primary" onClick={submit} disabled={busy || !text.trim()}>
            {busy ? '生成中…' : '发送'}
          </button>
        </div>
      </div>
    </section>
  )
}

function WelcomeCard({ onPick }: { onPick: (nl: string) => void }) {
  return (
    <>
      <div className="welcome-card">
        <h2 className="welcome-title">你好，老师 👋</h2>
        <p className="welcome-desc">
          说一句话，我就给你画几何图形。支持初中平面几何、坐标系、函数图像、几何变换。
        </p>
        <div className="welcome-features">
          <div className="feature-row">
            <span className="check">✓</span>
            <span>自然语言作图，无需手动拖拽</span>
          </div>
          <div className="feature-row">
            <span className="check">✓</span>
            <span>支持等长、角度、相切、共线、等腰等约束</span>
          </div>
          <div className="feature-row">
            <span className="check">✓</span>
            <span>可导出 SVG / PNG / PDF 用于课件</span>
          </div>
        </div>
      </div>
      <div className="example-grid">
        {EXAMPLES.map((ex) => (
          <button
            key={ex.nl}
            className="example-card"
            onClick={() => onPick(ex.nl)}
          >
            <span className="icon">{ex.icon}</span>
            <span className="text">
              <span className="title">{ex.title}</span>
              <span className="desc">{ex.desc}</span>
            </span>
          </button>
        ))}
      </div>
    </>
  )
}

function ChatMsgItem({ msg }: { msg: Message }) {
  if (msg.role === 'user') {
    return (
      <div className={`chat-msg user ${msg.pending ? 'pending' : ''}`}>
        {msg.content}
      </div>
    )
  }

  // 思考占位（V2-D SSE 流式）
  // 新格式：__stream__:<json>，含 stage + objects 列表
  // 旧格式：__thinking__ 或 __stage__:xxx（向后兼容）
  const stageText: Record<string, string> = {
    llm: '正在理解题意',
    fallback: '正在切换备选模型',
    patch: '正在修改图形',
    solve: '正在求解几何约束',
    repair: '图形不收敛，正在尝试修正',
    render: '正在渲染图形',
  }
  if (msg.content.startsWith('__stream__:')) {
    try {
      const state = JSON.parse(msg.content.slice('__stream__:'.length))
      const text = stageText[state.stage] || '话图正在思考中'
      return (
        <div className="chat-msg assistant thinking">
          <div className="thinking-stage">
            {text}
            <span className="dots">
              <span>.</span>
              <span>.</span>
              <span>.</span>
            </span>
          </div>
          {state.waiting && (
            <div className="thinking-waiting">
              AI 正在准备输出…
            </div>
          )}
          {state.objects?.length > 0 && (
            <div className="thinking-objects">
              {state.objects.map((o: { id: string; kind: string }, i: number) => (
                <div key={i} className="thinking-obj">
                  ✓ {describeObject(o.id, o.kind)}
                </div>
              ))}
            </div>
          )}
        </div>
      )
    } catch {
      // 解析失败回退到旧格式
    }
  }
  if (msg.content === '__thinking__' || msg.content.startsWith('__stage__:')) {
    const stage = msg.content.startsWith('__stage__:')
      ? msg.content.slice('__stage__:'.length) : ''
    const text = stageText[stage] || '话图正在思考中'
    return (
      <div className="chat-msg assistant thinking">
        {text}
        <span className="dots">
          <span>.</span>
          <span>.</span>
          <span>.</span>
        </span>
      </div>
    )
  }

  // 按 error_kind 分色
  if (msg.error_kind === 'refuse') {
    return (
      <div className="chat-msg refuse">
        <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
      </div>
    )
  }
  if (msg.error_kind === 'solve') {
    return (
      <div className="chat-msg solve-error">
        🔧 {msg.content}
      </div>
    )
  }
  if (msg.error_kind === 'patch') {
    return (
      <div className="chat-msg solve-error">
        ⚙ {msg.content}
      </div>
    )
  }
  if (msg.error_kind === 'network') {
    return (
      <div className="chat-msg error">
        ⚠ {msg.content}
      </div>
    )
  }

  // 正常 assistant：尝试解析 JSON 给出摘要
  let preview = msg.content
  try {
    const j = JSON.parse(msg.content)
    const objs = j.objects?.length ?? '?'
    const cons = j.constraints?.length ?? '?'
    preview = `✓ 图形已更新（${objs} 个对象，${cons} 条约束）`
  } catch {
    /* 文本消息原样 */
  }
  return (
    <div className="chat-msg assistant">
      {msg.fallback && (
        <div className="fallback-hint">
          （AI 第一次输出与现有图形有冲突，已自动重新理解为重画）
        </div>
      )}
      {preview}
    </div>
  )
}

// V2-D：把 (id, kind) 翻译成中文描述，给 thinking 气泡的"已识别对象"列表用
function describeObject(id: string, kind: string): string {
  switch (kind) {
    case 'point': return `点 ${id}`
    case 'segment': return `线段 ${id}`
    case 'line': return `直线 ${id}`
    case 'circle': return `圆 ${id}`
    case 'polygon': return `多边形 ${id}`
    case 'axis': return `坐标系 ${id}`
    case 'curve': return `曲线 ${id}`
    case 'arc': return `弧 ${id}`
    case 'sector': return `扇形 ${id}`
    case 'bow': return `弓形 ${id}`
    case 'annular_sector': return `圆环扇环 ${id}`
    case 'cube': return `正方体 ${id}`
    case 'cuboid': return `长方体 ${id}`
    case 'cylinder': return `圆柱 ${id}`
    case 'cone': return `圆锥 ${id}`
    case 'sphere': return `球 ${id}`
    case 'bar_chart': return `条形图 ${id}`
    case 'line_chart': return `折线图 ${id}`
    case 'pie_chart': return `扇形图 ${id}`
    case 'region': return `阴影区域 ${id}`
    case 'number_line': return `数轴 ${id}`
    case 'aux_line': return `辅助线 ${id}`
    case 'transformed_point': return `派生点 ${id}`
    case 'transformed_polygon': return `变换多边形 ${id}`
    default: return `${id} (${kind})`
  }
}
