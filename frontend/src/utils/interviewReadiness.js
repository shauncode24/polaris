// frontend/src/utils/interviewReadiness.js
// Deterministic readiness scoring — no LLM, no invented numbers. Each
// mastery level maps to a fixed point value (same spirit as the backend's
// MASTERY_THRESHOLDS), and a track's % is the average across its required
// topics. This is a real, recomputable formula over real synced data —
// never a guess dressed up as a percentage.

const MASTERY_SCORE = {
  'Not Practiced': 0,
  'Introduced': 30,
  'Some Practice': 60,
  'Consistent Practice': 85,
  'Extensive Practice': 100,
}

export const READINESS_TRACKS = [
  {
    key: 'backend',
    label: 'Backend / SDE-1 Interviews',
    topics: ['Arrays & Hashing', 'Strings', 'Sliding Window', 'Binary Search', 'Stack', 'Linked List', 'Trees', 'Graphs', 'Dynamic Programming', 'Sorting'],
  },
  {
    key: 'product',
    label: 'Product Company (SDE-2)',
    topics: ['Heap', 'Trie', 'Dynamic Programming', 'Greedy', 'Backtracking', 'Bit Manipulation', 'Intervals', 'Design', 'Graphs'],
  },
  {
    key: 'ai',
    label: 'AI / ML Engineer Interviews',
    topics: ['Arrays & Hashing', 'Dynamic Programming', 'Graphs', 'Math', 'Recursion', 'Design'],
  },
]

export function computeReadinessTracks(topicMastery) {
  const byTopic = {}
  for (const t of topicMastery || []) byTopic[t.topic] = t.mastery

  return READINESS_TRACKS.map((track) => {
    const scores = track.topics.map((topic) => MASTERY_SCORE[byTopic[topic] || 'Not Practiced'])
    const percentage = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0
    const weakTopics = track.topics.filter((topic) => MASTERY_SCORE[byTopic[topic] || 'Not Practiced'] < 60)
    return { key: track.key, label: track.label, percentage, weakTopics }
  })
}