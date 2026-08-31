import fs from 'node:fs'
import path from 'node:path'

const sourcePath = process.argv[2]
if (!sourcePath) throw new Error('Pass the pasted brief path as the first argument.')

const source = fs.readFileSync(sourcePath, 'utf8')
const lines = source.split(/\r?\n/)
const start = lines.findIndex((line) => /^# TOPIC 1\s+—\s+NUMBER/.test(line))
const end = lines.findIndex((line, index) => index > start && /^# 20\./.test(line))
if (start < 0 || end < 0) throw new Error('Could not locate the official syllabus section.')

const topics = []
let topic = null
let subtopic = null
let section = 'outcomes'

const clean = (value) => value
  .replace(/^\*\s+/, '')
  .replace(/\*\*/g, '')
  .replace(/`([^`]+)`/g, '$1')
  .trim()

for (const rawLine of lines.slice(start, end)) {
  const line = rawLine.trim()
  const topicMatch = line.match(/^# TOPIC (\d+)\s+—\s+(.+)$/)
  const subtopicMatch = line.match(/^## (\d+\.\d+(?:\.\d+)?)\s+(.+)$/)

  if (topicMatch) {
    topic = {
      number: topicMatch[1],
      title: clean(topicMatch[2]).toLowerCase().replace(/^./, (character) => character.toUpperCase()),
      subtopics: [],
    }
    topics.push(topic)
    subtopic = null
    continue
  }
  if (subtopicMatch) {
    subtopic = { code: subtopicMatch[1], title: clean(subtopicMatch[2]), outcomes: [], notes: [] }
    topic?.subtopics.push(subtopic)
    section = 'outcomes'
    continue
  }
  if (!subtopic) continue
  if (/^### Learning outcomes$/i.test(line)) {
    section = 'outcomes'
    continue
  }
  if (/^### Notes and examples$/i.test(line)) {
    section = 'notes'
    continue
  }
  if (!line || line === '---' || /^### /.test(line)) continue

  const value = clean(line)
  if (value) subtopic[section].push(value)
}

const header = '// Generated from the curriculum content supplied in the product brief.\n// Render curriculum wording from this source of truth.\n\n'
const output = `${header}export const syllabus = ${JSON.stringify(topics, null, 2)}\n\nexport const syllabusMeta = {\n  title: 'O Level Mathematics',\n  subtitle: 'Cambridge Mathematics (Syllabus D) 4024',\n  examinationYears: '2025–2027',\n  version: 'Version 2',\n  published: 'February 2024',\n}\n`

const outputPath = path.resolve('src/data/syllabus.js')
fs.mkdirSync(path.dirname(outputPath), { recursive: true })
fs.writeFileSync(outputPath, output, 'utf8')
console.log(`Wrote ${topics.length} topics and ${topics.reduce((sum, item) => sum + item.subtopics.length, 0)} subtopics to ${outputPath}`)
