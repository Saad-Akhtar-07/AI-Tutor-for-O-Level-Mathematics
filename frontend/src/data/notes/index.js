// Load any locally generated subtopic bundles. The JSON content is intentionally
// not committed because source-material redistribution rights can vary.
const noteModules = import.meta.glob('./*.json', { eager: true, import: 'default' })

export const subtopicNotes = Object.values(noteModules).reduce((notes, data) => {
  if (data?.subtopic_code) notes[data.subtopic_code] = data
  return notes
}, {})

export function getNotesForSubtopic(code) {
  return subtopicNotes[code] || null
}
