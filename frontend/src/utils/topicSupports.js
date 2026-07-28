// frontend/src/utils/topicSupports.js
// Hand-seeded, same philosophy as the backend's TECH_CATEGORIES /
// CAPABILITY_MAP — a small, stable vocabulary mapping a DSA topic to the
// kind of interview/career signal it supports. Not derived, not scored —
// just a fixed lookup so Evidence Generated can say what a topic is FOR,
// not only how many problems were solved in it.

export const TOPIC_SUPPORTS = {
  'Arrays & Hashing': ['Problem Solving', 'Backend'],
  'Strings': ['Problem Solving'],
  'Sliding Window': ['Problem Solving'],
  'Stack': ['Problem Solving'],
  'Queue': ['Problem Solving', 'Systems'],
  'Linked List': ['Problem Solving'],
  'Trees': ['Problem Solving', 'Backend'],
  'Graphs': ['Backend', 'Distributed Systems'],
  'Heap': ['Backend', 'Systems'],
  'Trie': ['Problem Solving'],
  'Dynamic Programming': ['Backend', 'AI/ML'],
  'Greedy': ['Problem Solving'],
  'Backtracking': ['Problem Solving', 'AI/ML'],
  'Bit Manipulation': ['Systems'],
  'Binary Search': ['Problem Solving'],
  'Intervals': ['Problem Solving'],
  'Sorting': ['Problem Solving', 'Backend'],
  'Math': ['AI/ML'],
  'Recursion': ['Problem Solving', 'AI/ML'],
  'Design': ['Systems', 'Backend'],
}

export function supportsFor(topic) {
  return TOPIC_SUPPORTS[topic] || []
}