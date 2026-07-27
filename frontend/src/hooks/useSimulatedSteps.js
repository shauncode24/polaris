import { useEffect, useRef, useState } from 'react'

// Drives a checklist of real backend pipeline stages while an async call
// is in flight. It never claims the FINAL step is complete on its own —
// that only happens when the real response resolves and the caller stops
// rendering this component in favor of the success view. This keeps the
// UI honest: we're showing believable progress through known stages, not
// pretending to know real server-side timing.
export function useSimulatedSteps(steps, isRunning, intervalMs = 750) {
  const [activeIndex, setActiveIndex] = useState(0)
  const timerRef = useRef(null)

  useEffect(() => {
    clearInterval(timerRef.current)
    if (isRunning) {
      setActiveIndex(0)
      timerRef.current = setInterval(() => {
        setActiveIndex((i) => (i < steps.length - 1 ? i + 1 : i))
      }, intervalMs)
    }
    return () => clearInterval(timerRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isRunning, steps.length, intervalMs])

  return activeIndex
}