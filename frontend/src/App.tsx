import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  error?: boolean
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8311'

const examples = [
  'What is the work from home policy?',
  'How many laptops are currently in stock?',
  'What is the status of order ORD1001?',
  'Show me information about product P1001.',
]

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState<string>()
  const [loading, setLoading] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function sendMessage(text: string) {
    const message = text.trim()
    if (!message || loading) return

    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: 'user', content: message },
    ])
    setInput('')
    setLoading(true)

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id: sessionId }),
      })
      if (!response.ok) throw new Error(`Request failed (${response.status})`)

      const data = await response.json()
      setSessionId(data.session_id)
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: data.response,
        },
      ])
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content:
            error instanceof Error
              ? `I could not reach the enterprise assistant. ${error.message}`
              : 'I could not reach the enterprise assistant.',
          error: true,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    void sendMessage(input)
  }

  function clearConversation() {
    setMessages([])
    setSessionId(undefined)
    setInput('')
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            N
          </div>
          <div>
            <span className="eyebrow">Northstar Operations</span>
            <h1>Enterprise Assistant</h1>
          </div>
        </div>
        <div className="topbar-actions">
          <span className="status">
            <span className="status-dot" /> Agents online
          </span>
          <button
            className="clear-button"
            onClick={clearConversation}
            disabled={messages.length === 0}
          >
            Clear conversation
          </button>
        </div>
      </header>

      <main className="workspace">
        <aside className="capabilities">
          <p className="section-label">Connected capabilities</p>
          <div className="agent-card">
            <span className="agent-icon hr">HR</span>
            <div>
              <strong>People & Business</strong>
              <span>Policies · Company information</span>
            </div>
          </div>
          <div className="agent-card">
            <span className="agent-icon ops">PO</span>
            <div>
              <strong>Products & Orders</strong>
              <span>Catalog · Inventory · Fulfillment</span>
            </div>
          </div>
          <div className="architecture-note">
            <span>A2A orchestration</span>
            <p>Requests are securely routed to specialized enterprise agents.</p>
          </div>
        </aside>

        <section className="chat-panel">
          <div className="chat-scroll" aria-live="polite">
            {messages.length === 0 ? (
              <div className="empty-state">
                <div className="spark" aria-hidden="true">✦</div>
                <h2>How can I help your work today?</h2>
                <p>
                  Ask across workplace policy, company information, product
                  inventory, and order operations.
                </p>
                <div className="examples">
                  {examples.map((example) => (
                    <button key={example} onClick={() => void sendMessage(example)}>
                      {example}
                      <span aria-hidden="true">→</span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="messages">
                {messages.map((message) => (
                  <div className={`message-row ${message.role}`} key={message.id}>
                    <span className="avatar" aria-hidden="true">
                      {message.role === 'user' ? 'You' : 'AI'}
                    </span>
                    <div className={`message ${message.error ? 'error' : ''}`}>
                      {message.content}
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="message-row assistant">
                    <span className="avatar" aria-hidden="true">AI</span>
                    <div className="message typing" aria-label="Assistant is thinking">
                      <span />
                      <span />
                      <span />
                    </div>
                  </div>
                )}
                <div ref={endRef} />
              </div>
            )}
          </div>

          <form className="composer" onSubmit={submit}>
            <label htmlFor="message-input" className="sr-only">
              Ask the enterprise assistant
            </label>
            <textarea
              id="message-input"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  void sendMessage(input)
                }
              }}
              placeholder="Ask about a policy, product, inventory, or order..."
              rows={1}
              disabled={loading}
            />
            <button
              className="send-button"
              type="submit"
              disabled={!input.trim() || loading}
              aria-label="Send message"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="m4 4 16 8-16 8 3-8-3-8Zm3.7 7h7.5L6.4 6.6 7.7 11Zm-1.3 6.4 8.8-4.4H7.7l-1.3 4.4Z" />
              </svg>
            </button>
          </form>
          <p className="disclaimer">
            Responses are generated from approved enterprise data. Verify critical decisions.
          </p>
        </section>
      </main>
    </div>
  )
}

export default App
