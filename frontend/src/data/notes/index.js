// These reviewed Probability bundles are imported explicitly so they are
// included reliably in local and production (Vercel) builds.
import notes81 from './8.1.json'
import notes82 from './8.2.json'
import notes83 from './8.3.json'

export const subtopicNotes = {
  '8.1': notes81,
  '8.2': notes82,
  '8.3': notes83,
}

export function getNotesForSubtopic(code) {
  return subtopicNotes[code] || null
}
