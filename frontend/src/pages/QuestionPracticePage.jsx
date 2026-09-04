import {
  BookOpenCheck,
  Bot,
  Camera,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleDashed,
  Eye,
  EyeOff,
  Lightbulb,
  LoaderCircle,
  Save,
  Send,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import InlineContent from '../components/notes/InlineContent.jsx'
import SyllabusSidebar from '../components/SyllabusSidebar.jsx'
import { getQuestionBank, getQuestionPartSolution } from '../api/content.js'
import {
  attachmentContentUrl,
  getStudentResponses,
  getTutorChatTurns,
  getTutorReviews,
  removeSolutionImage,
  requestTutorReview,
  saveStudentResponse,
  sendTutorChatMessage,
  uploadSolutionImage,
} from '../api/submissions.js'
import { syllabus } from '../data/syllabus.js'
import NotFound from './NotFound.jsx'

const mathsTools = [
  { id: 'power', label: 'x²', name: 'Add a power' },
  { id: 'root', label: '√', name: 'Add a square root' },
  { id: 'fraction', label: 'a/b', name: 'Add a fraction' },
  { id: 'multiply', label: '×', name: 'Add a multiplication sign' },
  { id: 'divide', label: '÷', name: 'Add a division sign' },
  { id: 'probability', label: 'P( )', name: 'Add probability notation' },
]

const TUTOR_WIDTH_STORAGE_KEY = 'ai-tutor-panel-width-v1'
const DEFAULT_TUTOR_WIDTH = 380
const MIN_TUTOR_WIDTH = 310
const MAX_TUTOR_WIDTH = 650
const MIN_QUESTION_WIDTH = 420
const RESIZER_WIDTH = 22

function storedTutorWidth() {
  try {
    const value = Number(localStorage.getItem(TUTOR_WIDTH_STORAGE_KEY))
    return Number.isFinite(value) && value > 0 ? value : DEFAULT_TUTOR_WIDTH
  } catch {
    return DEFAULT_TUTOR_WIDTH
  }
}

function tutorWidthBounds(workspace) {
  const availableWidth = workspace?.getBoundingClientRect().width || 1080
  return {
    minimum: MIN_TUTOR_WIDTH,
    maximum: Math.max(
      MIN_TUTOR_WIDTH,
      Math.min(MAX_TUTOR_WIDTH, availableWidth - MIN_QUESTION_WIDTH - RESIZER_WIDTH),
    ),
  }
}

function clampTutorWidth(workspace, requestedWidth) {
  const { minimum, maximum } = tutorWidthBounds(workspace)
  return Math.round(Math.min(maximum, Math.max(minimum, requestedWidth)))
}

function QuestionTable({ rows }) {
  return <div className="question-table-wrap"><table className="question-table"><tbody>{rows.map((row, ri) => <tr key={ri}>{row.map((cell, ci) => <td key={ci} className={ci === 0 ? 'question-table-label' : ''}><InlineContent content={cell || '\u00a0'} /></td>)}</tr>)}</tbody></table></div>
}

function CardsDiagram({ sets }) {
  return <div className="cards-diagram" aria-label="Card sets">{sets.map((set) => <div className="card-set" key={set.label}><strong>{set.label}</strong><div>{set.values.map((value, index) => <span key={`${value}-${index}`}>{value}</span>)}</div></div>)}</div>
}

function BagsDiagram({ bags }) {
  return <div className="bags-diagram" aria-label="Contents of the bags">{bags.map((bag) => <div className="bag-card" key={bag.label}><div className="bag-shape" aria-hidden="true">{Array.from({ length: bag.black }, (_, i) => <span className="ball black" key={`b-${i}`} />)}{Array.from({ length: bag.white }, (_, i) => <span className="ball white" key={`w-${i}`} />)}</div><strong>{bag.label}</strong><small>{bag.black} black, {bag.white} white</small></div>)}</div>
}

const regionClass = { m_only: 'venn-m-only', p_only: 'venn-p-only', d_only: 'venn-p-only', c_only: 'venn-c-only', g_only: 'venn-c-only', m_p: 'venn-mp', m_d: 'venn-mp', m_c: 'venn-mc', m_g: 'venn-mc', p_c: 'venn-pc', d_g: 'venn-pc', m_p_c: 'venn-all', m_d_g: 'venn-all', outside: 'venn-outside' }

function VennDiagram({ labels, regions }) {
  return <div className="venn-frame" role="img" aria-label={`Venn diagram for sets ${labels.join(', ')}`}><div className="venn-circle venn-left" /><div className="venn-circle venn-right" /><div className="venn-circle venn-bottom" /><span className="venn-label venn-label-left">{labels[0]}</span><span className="venn-label venn-label-right">{labels[1]}</span><span className="venn-label venn-label-bottom">{labels[2]}</span>{Object.entries(regions).map(([key, value]) => value !== null && <span className={`venn-value ${regionClass[key]}`} key={key}>{value}</span>)}</div>
}

function CoordinateGrid({ x_label: xLabel, y_label: yLabel, x_min: xMin, x_max: xMax, y_min: yMin, y_max: yMax }) {
  return <div className="coordinate-figure" role="img" aria-label={`Blank graph from ${xMin} to ${xMax} and ${yMin} to ${yMax}`}><span className="axis-label axis-y">{yLabel}</span><div className="coordinate-grid"><span>{yMax}</span><span>{yMin}</span></div><div className="axis-ticks"><span>{xMin}</span><span>{xMax}</span></div><span className="axis-label axis-x">{xLabel}</span></div>
}

function QuestionBlock({ block }) {
  if (block.type === 'paragraph') return <p className="question-paragraph"><InlineContent content={block.content} /></p>
  if (block.type === 'table') return <QuestionTable rows={block.rows} />
  if (block.type === 'cards') return <CardsDiagram sets={block.sets} />
  if (block.type === 'bags') return <BagsDiagram bags={block.bags} />
  if (block.type === 'venn') return <VennDiagram labels={block.labels} regions={block.regions} />
  if (block.type === 'coordinate_grid') return <CoordinateGrid {...block} />
  return null
}

function AnswerComposer({ part, value, attachments, saveState, saveMessage, onChange, onSave, onUpload, onRemoveAttachment }) {
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  const insertMaths = (tool) => {
    const textarea = textareaRef.current
    const start = textarea?.selectionStart ?? value.length
    const end = textarea?.selectionEnd ?? value.length
    const selected = value.slice(start, end)
    let insertion = ''
    let cursorOffset = 0

    if (tool.id === 'power') {
      insertion = selected ? `${selected}^2` : '^2'
      cursorOffset = insertion.length
    } else if (tool.id === 'root') {
      insertion = `sqrt(${selected})`
      cursorOffset = selected ? insertion.length : 5
    } else if (tool.id === 'fraction') {
      insertion = selected ? `(${selected})/()` : '()/()'
      cursorOffset = selected ? insertion.length - 1 : 1
    } else if (tool.id === 'probability') {
      insertion = `P(${selected})`
      cursorOffset = selected ? insertion.length : 2
    } else {
      insertion = tool.id === 'multiply' ? ' × ' : ' ÷ '
      cursorOffset = insertion.length
    }

    const nextValue = `${value.slice(0, start)}${insertion}${value.slice(end)}`
    onChange(nextValue)
    requestAnimationFrame(() => {
      textarea?.focus()
      textarea?.setSelectionRange(start + cursorOffset, start + cursorOffset)
    })
  }

  return <div className="answer-composer">
    <div className="answer-composer-heading">
      <label htmlFor={`${part.id}-answer`}>Your working and answer</label>
      <span>{value.trim() ? 'Draft added' : 'Show your method'}</span>
    </div>
    <div className="answer-entry">
      <textarea ref={textareaRef} id={`${part.id}-answer`} rows="4" maxLength="20000" spellCheck="false" value={value} onChange={(event) => onChange(event.target.value)} placeholder="Write each step here…" />
      {part.answer_suffix && <span className="answer-suffix">{part.answer_suffix}</span>}
    </div>
    <div className="maths-toolbar" aria-label="Maths input tools">
      <span>Maths tools</span>
      <div>{mathsTools.map((tool) => <button type="button" key={tool.id} title={tool.name} aria-label={tool.name} onClick={() => insertMaths(tool)}>{tool.label}</button>)}</div>
      <small>Keyboard: / for fractions · ^ for powers</small>
    </div>
    <div className="solution-input-footer">
      <div className="solution-input-actions">
        <input
          ref={fileInputRef}
          className="sr-only"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          onChange={(event) => {
            const files = Array.from(event.target.files || [])
            if (files.length) onUpload(files)
            event.target.value = ''
          }}
        />
        <button type="button" className="attach-solution-button" onClick={() => fileInputRef.current?.click()} disabled={saveState === 'uploading'}>
          {saveState === 'uploading' ? <LoaderCircle className="spin" size={16} /> : <Camera size={16} />}
          Add solution photo
        </button>
        <button type="button" className="save-solution-button" onClick={onSave} disabled={saveState === 'saving' || saveState === 'uploading'}>
          {saveState === 'saving' ? <LoaderCircle className="spin" size={16} /> : <Save size={16} />}
          Save work
        </button>
      </div>
      <span className={`solution-save-status ${saveState === 'error' ? 'is-error' : ''}`} role={saveState === 'error' ? 'alert' : 'status'}>
        {saveMessage || (saveState === 'saved' ? 'Saved securely' : saveState === 'saving' ? 'Saving…' : 'Text auto-saves after you pause')}
      </span>
    </div>
    {attachments.length > 0 && <div className="solution-attachments" aria-label="Attached solution images">
      {attachments.map((attachment) => <figure key={attachment.id}>
        <img src={attachmentContentUrl(attachment.content_url)} alt={`Attached working: ${attachment.original_filename}`} />
        <figcaption><span title={attachment.original_filename}>{attachment.original_filename}</span><button type="button" aria-label={`Remove ${attachment.original_filename}`} onClick={() => onRemoveAttachment(attachment.id)}><Trash2 size={14} /></button></figcaption>
      </figure>)}
    </div>}
  </div>
}

function QuestionPart({ part, answer, attachments, saveState, saveMessage, isActive, onAnswerChange, onSave, onUpload, onRemoveAttachment, onActivate, onTutorRequest }) {
  const [showScheme, setShowScheme] = useState(false)
  const [scheme, setScheme] = useState(null)
  const [schemeState, setSchemeState] = useState('idle')
  const schemeId = `${part.id}-scheme`

  const toggleScheme = async () => {
    if (showScheme) {
      setShowScheme(false)
      return
    }
    setShowScheme(true)
    if (scheme) return
    setSchemeState('loading')
    try {
      setScheme(await getQuestionPartSolution(part.id))
      setSchemeState('loaded')
    } catch {
      setSchemeState('error')
    }
  }

  return <section className={`question-part ${isActive ? 'is-active' : ''}`} onFocusCapture={onActivate}>
    <div className="question-part-heading"><span>{part.label}</span><strong>{part.marks} {part.marks === 1 ? 'mark' : 'marks'}</strong></div>
    <div className="question-part-prompt">{part.prompt.map((block, index) => <QuestionBlock block={block} key={index} />)}</div>
    <AnswerComposer part={part} value={answer} attachments={attachments} saveState={saveState} saveMessage={saveMessage} onChange={onAnswerChange} onSave={onSave} onUpload={onUpload} onRemoveAttachment={onRemoveAttachment} />
    <div className="question-help-row">
      <div className="tutor-actions">
        <button type="button" className="hint-button" onClick={() => onTutorRequest('hint', part, answer)}><Lightbulb size={17} /> Give me a hint</button>
        <button type="button" className="check-ai-button" onClick={() => onTutorRequest('check', part, answer)}><Sparkles size={17} /> Check with AI</button>
      </div>
      <button type="button" className={`mark-scheme-toggle ${showScheme ? 'is-open' : ''}`} aria-expanded={showScheme} aria-controls={schemeId} onClick={toggleScheme}>{showScheme ? <EyeOff size={17} /> : <Eye size={17} />}{showScheme ? 'Hide mark scheme' : 'Mark scheme'}</button>
    </div>
    {showScheme && <div className="mark-scheme-panel" id={schemeId}>
      {schemeState === 'loading' && <p>Loading mark scheme…</p>}
      {schemeState === 'error' && <p role="alert">The mark scheme could not be loaded.</p>}
      {scheme && <><div className="scheme-answer"><span>Answer</span><p><InlineContent content={scheme.answer} /></p></div>{scheme.marking_points.length > 0 && <div className="scheme-points"><span>How marks are awarded</span><ol>{scheme.marking_points.map((point, index) => <li key={`${point.code}-${index}`}><strong>{point.code}</strong><p><InlineContent content={point.text} /></p></li>)}</ol></div>}</>}
    </div>}
  </section>
}

const teachingMoveLabels = {
  ask_question: 'Socratic question',
  small_hint: 'Small hint',
  explain_concept: 'Concept explanation',
  check_understanding: 'Check your thinking',
  encourage: 'Tutor',
  redirect: 'Back to the question',
}

function AiTutorPanel({ topic, question, activePart, reviews, reviewState, chatTurns, chatState, onRequest, onSendMessage, onRetryMessage }) {
  const [chatInput, setChatInput] = useState('')
  const messageEndRef = useRef(null)
  const isEmpty = Boolean(question.isPlaceholder)
  const partReviews = reviews.filter((review) => review.question_part_id === activePart.id)
  const partTurns = chatTurns.filter((turn) => turn.question_part_id === activePart.id)
  const isReviewing = reviewState === 'reviewing'
  const isChatting = chatState === 'sending'
  const isBusy = isReviewing || isChatting
  const timeline = [
    ...partReviews.map((review) => ({ kind: 'review', createdAt: review.created_at, value: review })),
    ...partTurns.map((turn) => ({ kind: 'chat', createdAt: turn.created_at, value: turn })),
  ].sort((left, right) => new Date(left.createdAt) - new Date(right.createdAt))

  useEffect(() => {
    setChatInput('')
  }, [activePart.id])

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [partReviews.length, partTurns.length, isBusy])

  const submitMessage = (event) => {
    event.preventDefault()
    const message = chatInput.trim()
    if (!message || isBusy || isEmpty) return
    setChatInput('')
    onSendMessage(activePart, message)
  }

  const handleComposerKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  return <aside className="ai-tutor-panel" id="ai-tutor-panel" aria-label="AI tutor">
    <header className="ai-tutor-header">
      <div className="ai-tutor-avatar"><Bot size={21} /></div>
      <div><div className="ai-tutor-title"><h2>AI Tutor</h2><span>Socratic tutor</span></div><p><i /> {isReviewing ? 'Reviewing your work' : isChatting ? 'Thinking with you' : 'Ready to help'}</p></div>
    </header>
    <div className="ai-tutor-context"><span>Current focus</span><strong>{isEmpty ? `${topic.number} ${topic.title}` : `Question ${question.number} ${activePart.label}`}</strong><p>{isEmpty ? 'Questions are being prepared' : `${activePart.marks} ${activePart.marks === 1 ? 'mark' : 'marks'} · Guidance without giving the answer away`}</p></div>
    <div className="ai-tutor-conversation" aria-live="polite" aria-busy={isBusy}>
      {timeline.length === 0 && !isBusy ? <div className="tutor-welcome">
        <div><Sparkles size={22} /></div>
        <h3>{isEmpty ? `Your ${topic.title} tutor is ready.` : 'Try it—I’m here if you get stuck.'}</h3>
        <p>{isEmpty ? 'When a reviewed question is loaded, I will follow its active part and help without taking over the solution.' : 'Ask about a step, request a hint, or share what is confusing. I will help you reason it out one step at a time.'}</p>
      </div> : <div className="tutor-messages">
        {timeline.map((item) => item.kind === 'review' ? <div className="tutor-message assistant" key={`review-${item.value.id}`}>
          <span>{item.value.status === 'completed' ? `Attempt ${item.value.attempt_number} · ${item.value.marks_awarded}/${item.value.marks_maximum} marks` : `Attempt ${item.value.attempt_number}`}</span>
          <p>{item.value.feedback || item.value.error_message || 'This review did not complete.'}</p>
        </div> : <div className="tutor-chat-turn" key={`chat-${item.value.client_message_id}`}>
          <div className="tutor-message student"><span>You</span><p>{item.value.learner_message}</p></div>
          {item.value.status === 'completed' && <div className="tutor-message assistant"><span>{teachingMoveLabels[item.value.teaching_move] || 'Tutor'}</span><p>{item.value.tutor_message}</p></div>}
          {item.value.status === 'processing' && <div className="tutor-message assistant"><span>Thinking</span><p className="tutor-thinking"><LoaderCircle className="spin" size={15} /> Working out the best next question…</p></div>}
          {item.value.status === 'failed' && <div className="tutor-message assistant is-error" role="alert"><span>Message saved</span><p>{item.value.error_message || 'I could not answer just now.'}</p><button type="button" className="tutor-retry-button" disabled={isBusy} onClick={() => onRetryMessage(activePart, item.value)}>Retry</button></div>}
        </div>)}
        {isReviewing && <div className="tutor-message assistant"><span>Reviewing</span><p className="tutor-thinking"><LoaderCircle className="spin" size={16} /> Reading your method and preparing the next hint…</p></div>}
        <div ref={messageEndRef} />
      </div>}
    </div>
    <div className="tutor-quick-actions" aria-label="Tutor shortcuts">
      <button type="button" disabled={isEmpty || isBusy} onClick={() => onRequest('hint', activePart)}><Lightbulb size={15} /> Give a hint</button>
      <button type="button" disabled={isEmpty || isBusy} onClick={() => onRequest('check', activePart)}><CheckCircle2 size={15} /> Check my work</button>
    </div>
    <form className="tutor-chat-form" onSubmit={submitMessage}>
      <label className="sr-only" htmlFor={`tutor-message-${activePart.id}`}>Ask the AI tutor about this question</label>
      <textarea
        id={`tutor-message-${activePart.id}`}
        rows="2"
        maxLength="1000"
        value={chatInput}
        onChange={(event) => setChatInput(event.target.value)}
        onKeyDown={handleComposerKeyDown}
        placeholder={isEmpty ? 'Available with a question' : 'Ask about this step…'}
        disabled={isEmpty || isBusy}
      />
      <button type="submit" aria-label="Send message" title="Send message" disabled={isEmpty || isBusy || !chatInput.trim()}><Send size={18} /></button>
      <small>Enter to send · Shift+Enter for a new line</small>
    </form>
  </aside>
}

function createEmptyQuestion(topic) {
  return {
    id: `topic-${topic.number || 'unknown'}-empty`,
    isPlaceholder: true,
    number: '—',
    title: `${topic.title || 'Topic'} practice`,
    syllabus_codes: [],
    total_marks: 0,
    prompt: [],
    parts: [{
      id: `topic-${topic.number || 'unknown'}-empty-part`,
      label: '',
      marks: 0,
      prompt: [],
    }],
  }
}

function EmptyQuestionCard({ topic, loading = false, error = '' }) {
  const title = loading
    ? 'Loading practice questions…'
    : error
      ? 'The content API is unavailable.'
      : `The workspace is ready for ${topic.title}.`
  const description = loading
    ? 'Fetching the reviewed question bank from PostgreSQL.'
    : error
      ? 'Start the backend API and confirm PostgreSQL is running, then refresh this page.'
      : 'Reviewed questions for this topic are being prepared. Once available, you will be able to write answers, ask for hints and check your work here.'
  return <article className="exam-question empty-question-card">
    <header className="exam-question-header">
      <div className="question-number empty"><CircleDashed size={22} /></div>
      <div><p>QUESTION WORKSPACE</p><h2>{topic.title} practice</h2></div>
      <strong>Awaiting questions</strong>
    </header>
    <div className="empty-question-body">
      <div className="empty-question-icon"><BookOpenCheck size={25} /></div>
      <p className="empty-question-kicker">{loading ? 'Connecting to content library' : error ? 'Connection needed' : 'Practice set coming next'}</p>
      <h3>{title}</h3>
      <p>{description}</p>
      <div className="empty-question-preview" aria-hidden="true">
        <span />
        <span />
        <span />
        <div />
      </div>
    </div>
  </article>
}

export default function QuestionPracticePage() {
  const { topicNumber } = useParams()
  const topic = syllabus.find((item) => item.number === topicNumber)
  const [questionBank, setQuestionBank] = useState(null)
  const [isLoading, setIsLoading] = useState(Boolean(topic))
  const [loadError, setLoadError] = useState('')
  const questions = questionBank?.questions || []
  const hasQuestions = questions.length > 0
  const emptyQuestion = createEmptyQuestion(topic || {})
  const [questionIndex, setQuestionIndex] = useState(0)
  const [answers, setAnswers] = useState({})
  const [attachments, setAttachments] = useState({})
  const [saveStates, setSaveStates] = useState({})
  const [saveMessages, setSaveMessages] = useState({})
  const [responseLoadError, setResponseLoadError] = useState('')
  const [activePartId, setActivePartId] = useState('')
  const [reviews, setReviews] = useState([])
  const [reviewStates, setReviewStates] = useState({})
  const [chatTurns, setChatTurns] = useState([])
  const [chatStates, setChatStates] = useState({})
  const [tutorPanelWidth, setTutorPanelWidth] = useState(storedTutorWidth)
  const [tutorPanelMaxWidth, setTutorPanelMaxWidth] = useState(MAX_TUTOR_WIDTH)
  const [isResizingTutor, setIsResizingTutor] = useState(false)
  const answersRef = useRef({})
  const saveTimersRef = useRef(new Map())
  const saveVersionsRef = useRef(new Map())
  const workspaceRef = useRef(null)
  const tutorPanelWidthRef = useRef(tutorPanelWidth)
  const preferredTutorPanelWidthRef = useRef(tutorPanelWidth)
  const resizeFrameRef = useRef(null)
  const pendingPointerXRef = useRef(null)
  const isResizingTutorRef = useRef(false)
  const question = hasQuestions ? (questions[questionIndex] || questions[0]) : emptyQuestion
  const activePart = question.parts.find((part) => part.id === activePartId) || question.parts[0]

  useEffect(() => {
    let cancelled = false
    if (!topic) return undefined
    setIsLoading(true)
    setLoadError('')
    setQuestionBank(null)
    getQuestionBank(topic.number)
      .then((bank) => {
        if (!cancelled) setQuestionBank(bank)
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error.message)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => { cancelled = true }
  }, [topic])

  useEffect(() => {
    setQuestionIndex(0)
    setAnswers({})
    answersRef.current = {}
    setAttachments({})
    setSaveStates({})
    setSaveMessages({})
    setResponseLoadError('')
    setActivePartId('')
    setReviews([])
    setReviewStates({})
    setChatTurns([])
    setChatStates({})
    saveTimersRef.current.forEach((timer) => clearTimeout(timer))
    saveTimersRef.current.clear()
    if (!topic) return undefined
    let cancelled = false
    Promise.all([getStudentResponses(topic.number), getTutorReviews(topic.number), getTutorChatTurns(topic.number)])
      .then(([responses, restoredReviews, restoredChatTurns]) => {
        if (cancelled) return
        const restoredAnswers = {}
        const restoredAttachments = {}
        const restoredStates = {}
        responses.forEach((response) => {
          restoredAnswers[response.question_part_id] = response.typed_work
          restoredAttachments[response.question_part_id] = response.attachments
          restoredStates[response.question_part_id] = 'saved'
        })
        answersRef.current = restoredAnswers
        setAnswers(restoredAnswers)
        setAttachments(restoredAttachments)
        setSaveStates(restoredStates)
        setReviews(restoredReviews)
        setChatTurns(restoredChatTurns)
      })
      .catch((error) => {
        if (!cancelled) setResponseLoadError(error.message)
      })
    return () => {
      cancelled = true
      saveTimersRef.current.forEach((timer) => clearTimeout(timer))
      saveTimersRef.current.clear()
    }
  }, [topicNumber])

  useLayoutEffect(() => {
    const keepWidthInBounds = () => {
      const workspace = workspaceRef.current
      if (!workspace || window.matchMedia('(max-width: 1279px)').matches) return
      const bounds = tutorWidthBounds(workspace)
      const nextWidth = clampTutorWidth(workspace, preferredTutorPanelWidthRef.current)
      setTutorPanelMaxWidth(bounds.maximum)
      tutorPanelWidthRef.current = nextWidth
      setTutorPanelWidth(nextWidth)
      workspace.style.setProperty('--tutor-panel-width', `${nextWidth}px`)
    }
    keepWidthInBounds()
    window.addEventListener('resize', keepWidthInBounds)
    return () => {
      window.removeEventListener('resize', keepWidthInBounds)
      if (resizeFrameRef.current !== null) cancelAnimationFrame(resizeFrameRef.current)
      document.documentElement.classList.remove('is-resizing-tutor')
    }
  }, [])

  useEffect(() => {
    if (!topic) return
    document.title = hasQuestions
      ? `${topic.title} practice - Question ${question.number} - Mathematics 4024`
      : `${topic.title} practice - Mathematics 4024`
    window.scrollTo(0, 0)
  }, [hasQuestions, question.number, topic])

  if (!topic) return <NotFound />

  const moveTo = (index) => {
    if (!hasQuestions) return
    const nextIndex = Math.max(0, Math.min(questions.length - 1, index))
    const nextQuestion = questions[nextIndex]
    setQuestionIndex(nextIndex)
    setActivePartId(nextQuestion.parts[0].id)
  }

  const applyTutorWidth = (requestedWidth, persist = false) => {
    const workspace = workspaceRef.current
    if (!workspace) return tutorPanelWidthRef.current
    const nextWidth = clampTutorWidth(workspace, requestedWidth)
    tutorPanelWidthRef.current = nextWidth
    workspace.style.setProperty('--tutor-panel-width', `${nextWidth}px`)
    if (persist) {
      preferredTutorPanelWidthRef.current = nextWidth
      setTutorPanelWidth(nextWidth)
      try { localStorage.setItem(TUTOR_WIDTH_STORAGE_KEY, String(nextWidth)) }
      catch { /* The width remains active for this page. */ }
    }
    return nextWidth
  }

  const updateTutorWidthFromPointer = (clientX) => {
    pendingPointerXRef.current = clientX
    if (resizeFrameRef.current !== null) return
    resizeFrameRef.current = requestAnimationFrame(() => {
      resizeFrameRef.current = null
      const workspace = workspaceRef.current
      if (!workspace || pendingPointerXRef.current === null) return
      const rightEdge = workspace.getBoundingClientRect().right
      applyTutorWidth(rightEdge - pendingPointerXRef.current)
    })
  }

  const startTutorResize = (event) => {
    if (event.button !== 0) return
    event.preventDefault()
    isResizingTutorRef.current = true
    setIsResizingTutor(true)
    setTutorPanelMaxWidth(tutorWidthBounds(workspaceRef.current).maximum)
    document.documentElement.classList.add('is-resizing-tutor')
    event.currentTarget.setPointerCapture(event.pointerId)
    updateTutorWidthFromPointer(event.clientX)
  }

  const moveTutorResize = (event) => {
    if (!isResizingTutorRef.current) return
    event.preventDefault()
    updateTutorWidthFromPointer(event.clientX)
  }

  const finishTutorResize = (event) => {
    if (!isResizingTutorRef.current) return
    if (resizeFrameRef.current !== null) {
      cancelAnimationFrame(resizeFrameRef.current)
      resizeFrameRef.current = null
    }
    if (event.type !== 'pointercancel') {
      const workspace = workspaceRef.current
      const rightEdge = workspace?.getBoundingClientRect().right || event.clientX
      applyTutorWidth(rightEdge - event.clientX)
    }
    isResizingTutorRef.current = false
    setIsResizingTutor(false)
    preferredTutorPanelWidthRef.current = tutorPanelWidthRef.current
    setTutorPanelWidth(tutorPanelWidthRef.current)
    try { localStorage.setItem(TUTOR_WIDTH_STORAGE_KEY, String(tutorPanelWidthRef.current)) }
    catch { /* The width remains active for this page. */ }
    document.documentElement.classList.remove('is-resizing-tutor')
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  const resizeTutorWithKeyboard = (event) => {
    const largeStep = event.shiftKey ? 64 : 24
    let nextWidth = tutorPanelWidthRef.current
    if (event.key === 'ArrowLeft') nextWidth += largeStep
    else if (event.key === 'ArrowRight') nextWidth -= largeStep
    else if (event.key === 'Home') nextWidth = MIN_TUTOR_WIDTH
    else if (event.key === 'End') nextWidth = tutorWidthBounds(workspaceRef.current).maximum
    else return
    event.preventDefault()
    applyTutorWidth(nextWidth, true)
  }

  const resetTutorWidth = () => applyTutorWidth(DEFAULT_TUTOR_WIDTH, true)

  const persistAnswer = async (partId, value, status = 'draft') => {
    const version = (saveVersionsRef.current.get(partId) || 0) + 1
    saveVersionsRef.current.set(partId, version)
    setSaveStates((current) => ({ ...current, [partId]: 'saving' }))
    setSaveMessages((current) => ({ ...current, [partId]: '' }))
    try {
      const response = await saveStudentResponse(partId, value, status)
      setAttachments((current) => ({ ...current, [partId]: response.attachments }))
      if (saveVersionsRef.current.get(partId) === version) {
        setSaveStates((current) => ({ ...current, [partId]: 'saved' }))
        setSaveMessages((current) => ({
          ...current,
          [partId]: status === 'ready_for_review' ? 'Saved and ready for tutor review' : 'Saved securely',
        }))
      }
      return response
    } catch (error) {
      if (saveVersionsRef.current.get(partId) === version) {
        setSaveStates((current) => ({ ...current, [partId]: 'error' }))
        setSaveMessages((current) => ({ ...current, [partId]: error.message }))
      }
      throw error
    }
  }

  const changeAnswer = (partId, value) => {
    answersRef.current = { ...answersRef.current, [partId]: value }
    setAnswers(answersRef.current)
    setSaveStates((current) => ({ ...current, [partId]: 'saving' }))
    setSaveMessages((current) => ({ ...current, [partId]: '' }))
    clearTimeout(saveTimersRef.current.get(partId))
    const timer = setTimeout(() => {
      saveTimersRef.current.delete(partId)
      persistAnswer(partId, value).catch(() => {})
    }, 800)
    saveTimersRef.current.set(partId, timer)
  }

  const saveNow = (part) => {
    clearTimeout(saveTimersRef.current.get(part.id))
    saveTimersRef.current.delete(part.id)
    persistAnswer(part.id, answersRef.current[part.id] || '').catch(() => {})
  }

  const uploadImages = async (part, files) => {
    const currentAttachments = attachments[part.id] || []
    if (currentAttachments.length + files.length > 4) {
      setSaveStates((current) => ({ ...current, [part.id]: 'error' }))
      setSaveMessages((current) => ({ ...current, [part.id]: 'You can attach up to 4 images to one answer.' }))
      return
    }
    clearTimeout(saveTimersRef.current.get(part.id))
    saveTimersRef.current.delete(part.id)
    try {
      await persistAnswer(part.id, answersRef.current[part.id] || '')
      setSaveStates((current) => ({ ...current, [part.id]: 'uploading' }))
      setSaveMessages((current) => ({ ...current, [part.id]: 'Uploading solution image…' }))
      let response
      for (const file of files) response = await uploadSolutionImage(part.id, file)
      setAttachments((current) => ({ ...current, [part.id]: response.attachments }))
      setSaveStates((current) => ({ ...current, [part.id]: 'saved' }))
      setSaveMessages((current) => ({ ...current, [part.id]: `${response.attachments.length} solution image${response.attachments.length === 1 ? '' : 's'} saved` }))
    } catch (error) {
      setSaveStates((current) => ({ ...current, [part.id]: 'error' }))
      setSaveMessages((current) => ({ ...current, [part.id]: error.message }))
    }
  }

  const deleteImage = async (part, attachmentId) => {
    setSaveStates((current) => ({ ...current, [part.id]: 'saving' }))
    setSaveMessages((current) => ({ ...current, [part.id]: 'Removing image…' }))
    try {
      await removeSolutionImage(attachmentId)
      setAttachments((current) => ({
        ...current,
        [part.id]: (current[part.id] || []).filter((item) => item.id !== attachmentId),
      }))
      setSaveStates((current) => ({ ...current, [part.id]: 'saved' }))
      setSaveMessages((current) => ({ ...current, [part.id]: 'Image removed' }))
    } catch (error) {
      setSaveStates((current) => ({ ...current, [part.id]: 'error' }))
      setSaveMessages((current) => ({ ...current, [part.id]: error.message }))
    }
  }

  const askTutor = async (type, part) => {
    if (!hasQuestions) return
    setActivePartId(part.id)
    clearTimeout(saveTimersRef.current.get(part.id))
    saveTimersRef.current.delete(part.id)
    setReviewStates((current) => ({ ...current, [part.id]: 'reviewing' }))
    try {
      const saved = await persistAnswer(
        part.id,
        answersRef.current[part.id] || '',
        'ready_for_review',
      )
      const review = await requestTutorReview(part.id, saved.revision, type)
      setReviews((current) => {
        const withoutDuplicate = current.filter((item) => item.id !== review.id)
        return [...withoutDuplicate, review].sort((a, b) => a.attempt_number - b.attempt_number)
      })
      setReviewStates((current) => ({ ...current, [part.id]: 'complete' }))
    } catch (error) {
      setReviewStates((current) => ({ ...current, [part.id]: 'error' }))
      setSaveStates((current) => ({ ...current, [part.id]: 'error' }))
      setSaveMessages((current) => ({ ...current, [part.id]: error.message }))
      getTutorReviews(topic.number).then(setReviews).catch(() => {})
    }
  }

  const sendTutorMessage = async (part, message, clientMessageId = crypto.randomUUID()) => {
    if (!hasQuestions) return
    setActivePartId(part.id)
    if (saveTimersRef.current.has(part.id)) {
      clearTimeout(saveTimersRef.current.get(part.id))
      saveTimersRef.current.delete(part.id)
      try {
        await persistAnswer(part.id, answersRef.current[part.id] || '')
      } catch {
        // The learner can still ask for help if saving their separate work area fails.
      }
    }
    setChatStates((current) => ({ ...current, [part.id]: 'sending' }))
    setChatTurns((current) => {
      const existing = current.find((turn) => turn.client_message_id === clientMessageId)
      const optimistic = {
        ...(existing || {}),
        id: existing?.id || clientMessageId,
        client_message_id: clientMessageId,
        question_part_id: part.id,
        learner_message: message,
        tutor_message: null,
        status: 'processing',
        error_message: null,
        created_at: existing?.created_at || new Date().toISOString(),
      }
      return [...current.filter((turn) => turn.client_message_id !== clientMessageId), optimistic]
    })
    try {
      const turn = await sendTutorChatMessage(part.id, message, clientMessageId)
      setChatTurns((current) => [
        ...current.filter((item) => item.client_message_id !== clientMessageId),
        turn,
      ])
      setChatStates((current) => ({ ...current, [part.id]: 'complete' }))
    } catch (error) {
      setChatStates((current) => ({ ...current, [part.id]: 'error' }))
      setChatTurns((current) => current.map((turn) => (
        turn.client_message_id === clientMessageId
          ? { ...turn, status: 'failed', error_message: error.message }
          : turn
      )))
      getTutorChatTurns(topic.number).then((restored) => {
        setChatTurns((current) => {
          const transient = current.filter((turn) => (
            !restored.some((item) => item.client_message_id === turn.client_message_id)
            && ['processing', 'failed'].includes(turn.status)
          ))
          return [...restored, ...transient]
        })
      }).catch(() => {})
    }
  }

  const summary = hasQuestions
    ? `${questions.length} reviewed questions · ${questionBank.total_marks} marks · Your tutor stays with the active part`
    : isLoading
      ? 'Loading reviewed questions from the content library'
      : loadError
        ? 'Could not reach the content library'
        : 'Question workspace ready · Reviewed questions have not been added yet'

  return <main className="reader-shell" id="main-content" tabIndex="-1">
    <SyllabusSidebar topic={topic} activeCode="practice" />
    <div className="reader-main practice-reader-main">
      <nav className="breadcrumbs" aria-label="Breadcrumb"><ol><li><Link to="/">Syllabus</Link></li><li><ChevronRight size={14} /></li><li><Link to={`/topic/${topic.number}`}>{topic.number} {topic.title}</Link></li><li><ChevronRight size={14} /></li><li><span aria-current="page">Practice questions</span></li></ol></nav>
      <header className="practice-heading"><div><p>TOPIC {topic.number} - {topic.title.toUpperCase()}</p><h1>Practice with your AI tutor</h1><span>{summary}</span></div><BookOpenCheck size={38} /></header>
      <nav className={`question-picker ${hasQuestions ? '' : 'is-empty'}`} aria-label="Choose a question">
        <span>Question</span>
        <div>{hasQuestions ? questions.map((item, index) => <button type="button" key={item.id} className={index === questionIndex ? 'active' : ''} aria-current={index === questionIndex ? 'step' : undefined} onClick={() => moveTo(index)}>{item.number}</button>) : <span className="question-picker-empty"><CircleDashed size={16} /> {isLoading ? 'Loading questions…' : loadError ? 'Content API unavailable' : 'No reviewed questions available'}</span>}</div>
      </nav>
      {responseLoadError && <div className="response-load-warning" role="alert">Saved work could not be restored: {responseLoadError}</div>}
      <div
        ref={workspaceRef}
        className={`practice-workspace ${isResizingTutor ? 'is-resizing' : ''}`}
        style={{ '--tutor-panel-width': `${tutorPanelWidth}px` }}
      >
        <div className="practice-question-column">
          {hasQuestions ? <>
            <article className="exam-question" key={question.id}>
              <header className="exam-question-header"><div className="question-number">{String(question.number).padStart(2, '0')}</div><div><p>{question.syllabus_codes.map((code) => `Syllabus ${code}`).join(' - ')}</p><h2>{question.title}</h2></div><strong>{question.total_marks} marks</strong></header>
              <div className="question-stimulus">{question.prompt.map((block, index) => <QuestionBlock block={block} key={index} />)}</div>
              <div className="question-parts">{question.parts.map((part) => <QuestionPart part={part} answer={answers[part.id] || ''} attachments={attachments[part.id] || []} saveState={saveStates[part.id] || 'idle'} saveMessage={saveMessages[part.id] || ''} isActive={part.id === activePart.id} onAnswerChange={(value) => changeAnswer(part.id, value)} onSave={() => saveNow(part)} onUpload={(files) => uploadImages(part, files)} onRemoveAttachment={(attachmentId) => deleteImage(part, attachmentId)} onActivate={() => setActivePartId(part.id)} onTutorRequest={askTutor} key={part.id} />)}</div>
            </article>
            <nav className="practice-pagination" aria-label="Question navigation"><button type="button" onClick={() => moveTo(questionIndex - 1)} disabled={questionIndex === 0}><ChevronLeft size={18} /> Previous question</button><span>{questionIndex + 1} of {questions.length}</span><button type="button" onClick={() => moveTo(questionIndex + 1)} disabled={questionIndex === questions.length - 1}>Next question <ChevronRight size={18} /></button></nav>
          </> : <EmptyQuestionCard topic={topic} loading={isLoading} error={loadError} />}
        </div>
        <div
          className="tutor-panel-resizer"
          role="separator"
          aria-label="Resize question and AI tutor panels"
          aria-controls="ai-tutor-panel"
          aria-orientation="vertical"
          aria-valuemin={MIN_TUTOR_WIDTH}
          aria-valuemax={tutorPanelMaxWidth}
          aria-valuenow={tutorPanelWidth}
          aria-valuetext={`AI tutor width ${tutorPanelWidth} pixels`}
          tabIndex="0"
          title="Drag to resize · Double-click to reset"
          onPointerDown={startTutorResize}
          onPointerMove={moveTutorResize}
          onPointerUp={finishTutorResize}
          onPointerCancel={finishTutorResize}
          onKeyDown={resizeTutorWithKeyboard}
          onDoubleClick={resetTutorWidth}
        ><span aria-hidden="true" /></div>
        <AiTutorPanel topic={topic} question={question} activePart={activePart} reviews={reviews} reviewState={reviewStates[activePart.id] || 'idle'} chatTurns={chatTurns} chatState={chatStates[activePart.id] || 'idle'} onRequest={askTutor} onSendMessage={sendTutorMessage} onRetryMessage={(part, turn) => sendTutorMessage(part, turn.learner_message, turn.client_message_id)} />
      </div>
    </div>
  </main>
}
