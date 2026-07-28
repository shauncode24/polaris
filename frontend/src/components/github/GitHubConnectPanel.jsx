import { useState } from 'react'
import { IconGithub } from '../icons/Icons'
import Button from '../common/Button'
import './GitHubConnectPanel.css'

function GitHubConnectPanel({ defaultUsername, onConnect, connecting, error }) {
  const [username, setUsername] = useState(defaultUsername || '')
  const [pat, setPat] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!username.trim()) return
    onConnect(username.trim(), pat.trim())
  }

  return (
    <div className="gh-connect">
      <span className="gh-connect__icon"><IconGithub size={26} /></span>
      <h2>Connect your GitHub</h2>
      <p>Turn your repositories into evidence-backed portfolio insights.</p>

      {error && <p className="gh-connect__error">{error}</p>}

      <form className="gh-connect__form" onSubmit={handleSubmit}>
        <label>
          GitHub username
          <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="octocat" />
        </label>
        <label>
          Personal access token
          <input
            type="password"
            value={pat}
            onChange={(e) => setPat(e.target.value)}
            placeholder="ghp_… (leave blank to reuse a saved token)"
          />
        </label>
        <Button type="submit" variant="primary" disabled={connecting}>
          {connecting ? 'Connecting…' : 'Connect & sync'}
        </Button>
      </form>
    </div>
  )
}

export default GitHubConnectPanel