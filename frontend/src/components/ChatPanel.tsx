import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'
import { ExampleHints } from './TopBar'
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

  return (
    <section>
      <div className="section-header">对话</div>
      <div className="chat-list" ref={listRef}>
        {messages.length === 0 && seq === 0 && (
          <>
            <div className="chat-msg assistant">
              你好，老师。说一句话我就给你画图。
            </div>
            <ExampleHints onClick={(t) => setText(t)} />
          </>
        )}
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
          placeholder="例如：画一个内切圆半径为 3 的等腰三角形"
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

function ChatMsgItem({ msg }: { msg: Message }) {
  if (msg.role === 'user') {
    return (
      <div className={`chat-msg user ${msg.pending ? 'pending' : ''}`}>
        {msg.content}
      </div>
    )
  }

  // 思考占位
  if (msg.content === '__thinking__') {
    return (
      <div className="chat-msg assistant thinking">
        话图正在思考中
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
