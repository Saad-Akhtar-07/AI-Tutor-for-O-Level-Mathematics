// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import QuestionPracticePage from '../pages/QuestionPracticePage.jsx'
import TopicPage from '../pages/TopicPage.jsx'

vi.mock('../api/content.js', () => ({
  getQuestionBank: vi.fn().mockResolvedValue({
    total_marks: 1,
    questions: [{
      id: 'question-one', number: 9, title: 'A daily commute', total_marks: 1,
      syllabus_codes: ['8.3'], prompt: [],
      parts: [{ id: 'part-one', label: '(a)', marks: 1, prompt: [] }],
    }],
  }),
  getQuestionCount: vi.fn().mockResolvedValue(1),
  getQuestionPartSolution: vi.fn(),
}))
vi.mock('../api/submissions.js', async importOriginal => ({
  ...await importOriginal(),
  getStudentResponses: vi.fn().mockResolvedValue([]),
  getTutorReviews: vi.fn().mockResolvedValue([]),
  getTutorChatTurns: vi.fn().mockResolvedValue([{
    id: 'turn-one', client_message_id: 'message-one', question_part_id: 'part-one',
    status: 'completed', teaching_move: 'small_hint', created_at: '2026-09-17T10:00:00Z',
    learner_message: 'Can you give me hints?', tutor_message: 'Think about the two possible outcomes.',
  }]),
}))

let resizeWorkspace
function renderWorkspace(path = '/topic/8/practice') {
  return render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/topic/:topicNumber/practice" element={<QuestionPracticePage />} />
    <Route path="/topic/:topicNumber" element={<TopicPage />} />
  </Routes></MemoryRouter>)
}

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('ResizeObserver', class {
    constructor(callback) { resizeWorkspace = callback }
    observe() { resizeWorkspace() }
    disconnect() {}
  })
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  Element.prototype.scrollIntoView = vi.fn()
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function () {
    const width = document.querySelector('.is-sidebar-collapsed') ? 1200 : 900
    return { width, right: width, left: 0, top: 0, bottom: 700, height: 700 }
  })
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

test('the sidebar edge toggle preserves chat drafts and its compact size across practice and lessons', async () => {
  await act(async () => { renderWorkspace() })
  await screen.findByText('Think about the two possible outcomes.')
  const composer = screen.getByRole('textbox', { name: 'Ask the AI tutor about this question' })
  fireEvent.change(composer, { target: { value: 'What should I consider next?' } })
  expect(composer.value).toBe('What should I consider next?')
  expect(screen.queryByRole('button', { name: 'Widen AI tutor' })).toBeNull()
  const toggle = screen.getByRole('button', { name: 'Collapse syllabus sidebar' })
  expect(toggle.closest('.reader-sidebar')).toBeTruthy()
  fireEvent.click(toggle)
  act(() => resizeWorkspace())
  expect(composer.value).toBe('What should I consider next?')
  expect(document.getElementById('main-content').classList.contains('is-sidebar-collapsed')).toBe(true)
  expect(screen.getByRole('link', { name: '8.1 Introduction to probability' })).toBeTruthy()
  expect(localStorage.getItem('practice-sidebar-collapsed-v1')).toBe('true')
  fireEvent.click(screen.getByRole('button', { name: 'Expand syllabus sidebar' }))
  act(() => resizeWorkspace())
  expect(document.getElementById('main-content').classList.contains('is-sidebar-collapsed')).toBe(false)
  fireEvent.click(screen.getByRole('button', { name: 'Collapse syllabus sidebar' }))
  expect(composer.value).toBe('What should I consider next?')
  expect(screen.getByText('Think about the two possible outcomes.')).toBeTruthy()
  cleanup()
  await act(async () => { renderWorkspace('/topic/8') })
  expect(screen.getByRole('heading', { name: 'Probability' })).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Expand syllabus sidebar' }).getAttribute('aria-expanded')).toBe('false')
  fireEvent.click(screen.getByRole('button', { name: 'Expand syllabus sidebar' }))
  expect(document.getElementById('main-content').classList.contains('is-sidebar-collapsed')).toBe(false)
})

test('voice settings stay out of the conversation and can be dismissed with Escape', async () => {
  await act(async () => { renderWorkspace() })
  await screen.findByText('Think about the two possible outcomes.')
  expect(screen.queryByRole('combobox', { name: 'Tutor voice' })).toBeNull()
  const settings = screen.getByRole('button', { name: 'Voice settings' })
  fireEvent.click(settings)
  expect(screen.getByRole('combobox', { name: 'Tutor voice' }).value).toBe('device')
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('combobox', { name: 'Tutor voice' })).toBeNull()
  expect(settings.getAttribute('aria-expanded')).toBe('false')
  expect(document.activeElement).toBe(settings)
})
