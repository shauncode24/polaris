// frontend/src/components/interview/ChatInput.jsx
import { useState } from 'react'
import './ChatInput.css'

function ChatInput({ onSubmit, disabled, placeholder = 'Write your message...' }) {
  const [value, setValue] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!value.trim() || disabled) return
    onSubmit(value)
    setValue('')
  }

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
      />
      <button type="submit" className="chat-input__send" disabled={disabled || !value.trim()}>
        Send →
      </button>
    </form>
  )
}

export default ChatInput