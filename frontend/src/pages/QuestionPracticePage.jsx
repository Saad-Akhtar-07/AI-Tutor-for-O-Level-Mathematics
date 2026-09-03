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
import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import InlineContent from '../components/notes/InlineContent.jsx'
import SyllabusSidebar from '../components/SyllabusSidebar.jsx'
import { getQuestionBank } from '../api/content.js'
import {
  attachmentContentUrl,
  getStudentResponses,
  removeSolutionImage,
  saveStudentResponse,
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
  const schemeId = `${part.id}-scheme`

  return <section className={`question-part ${isActive ? 'is-active' : ''}`} onFocusCapture={onActivate}>
    <div className="question-part-heading"><span>{part.label}</span><strong>{part.marks} {part.marks === 1 ? 'mark' : 'marks'}</strong></div>
    <div className="question-part-prompt">{part.prompt.map((block, index) => <QuestionBlock block={block} key={index} />)}</div>
    <AnswerComposer part={part} value={answer} attachments={attachments} saveState={saveState} saveMessage={saveMessage} onChange={onAnswerChange} onSave={onSave} onUpload={onUpload} onRemoveAttachment={onRemoveAttachment} />
    <div className="question-help-row">
      <div className="tutor-actions">
        <button type="button" className="hint-button" onClick={() => onTutorRequest('hint', part, answer)}><Lightbulb size={17} /> Give me a hint</button>
        <button type="button" className="check-ai-button" onClick={() => onTutorRequest('check', part, answer)}><Sparkles size={17} /> Check with AI</button>
      </div>
      <button type="button" className={`mark-scheme-toggle ${showScheme ? 'is-open' : ''}`} aria-expanded={showScheme} aria-controls={schemeId} onClick={() => setShowScheme((visible) => !visible)}>{showScheme ? <EyeOff size={17} /> : <Eye size={17} />}{showScheme ? 'Hide mark scheme' : 'Mark scheme'}</button>
    </div>
    {showScheme && <div className="mark-scheme-panel" id={schemeId}><div className="scheme-answer"><span>Answer</span><p><InlineContent content={part.mark_scheme.answer} /></p></div>{part.mark_scheme.marking_points.length > 0 && <div className="scheme-points"><span>How marks are awarded</span><ol>{part.mark_scheme.marking_points.map((point, index) => <li key={`${point.code}-${index}`}><strong>{point.code}</strong><p><InlineContent content={point.text} /></p></li>)}</ol></div>}</div>}
  </section>
}

function partText(part) {
  return part.prompt.filter((block) => block.type === 'paragraph').map((block) => block.content).join(' ').toLowerCase()
}

function buildTutorReply(type, question, part, answer = '', message = '') {
  const context = `${question.title} ${partText(part)}`.toLowerCase()

  if (type === 'check' && !answer.trim()) return 'Add your first step in the answer box, then ask me to check it. Even a fraction or short equation is enough to begin.'
  if (type === 'check') {
    if (context.includes('mean') || context.includes('frequency')) return 'Good—you have started the method. Check that you used every relevant frequency, and for a grouped mean make sure each frequency is multiplied by its class midpoint before dividing by the total frequency.'
    if (context.includes('venn')) return 'Good—you have started the method. Check the intersections first, then confirm that all regions—including the area outside the circles—add to the stated total.'
    if (context.includes('without replacement') || context.includes('chooses two') || context.includes('chosen')) return 'Good—you have started the method. Check that every number comes from the question and that the denominator changes after a selection when there is no replacement.'
    return 'Good—you have started the method. Check that your favourable outcomes are over the correct total, then simplify only after the probability setup is complete.'
  }
  if (type === 'concept') {
    if (context.includes('venn')) return 'In a Venn diagram, start with the deepest overlap and work outwards. The total of every region, including outside the circles, must equal the universal set.'
    if (context.includes('modal') || context.includes('mode')) return 'The modal class is the interval with the greatest frequency. You do not need to calculate an exact value inside that interval.'
    if (context.includes('median')) return 'The median lies at the middle position in the ordered data. Use cumulative frequency to find which interval contains that position.'
    if (context.includes('mean') || context.includes('frequency')) return 'For grouped data, use each class midpoint as the representative value, multiply it by its frequency, then divide the total by the total frequency.'
    if (context.includes('probability')) return 'For probability, divide favourable outcomes by all equally likely outcomes. Multiply probabilities along one path; add probabilities for separate valid paths.'
    return 'Start by naming the mathematical idea being tested, then connect the information given in the question to the rule or formula you need.'
  }
  if (type === 'hint') {
    if (context.includes('without replacement') || context.includes('chooses two') || context.includes('chosen')) return 'Write the probability for the first selection, then update both the favourable count and the total before writing the second probability. Multiply along the path.'
    if (context.includes('venn')) return 'Look for an intersection whose value can be found directly. Fill the overlaps before the regions belonging to only one set.'
    if (context.includes('mean')) return 'Add a midpoint row to the table first. Your next calculation should use frequency × midpoint for every class.'
    if (context.includes('more than') || context.includes('less than')) return 'Identify which frequency or outcome count satisfies the inequality, then place it over the total number of outcomes.'
    if (context.includes('probability')) return 'Name the event you want, count its favourable outcomes, and compare that count with the total number of equally likely outcomes.'
    return 'Underline what the question gives you and what it asks you to find. Write one useful rule, formula, or relationship before substituting values.'
  }
  if (message.toLowerCase().includes('answer')) return 'I can help you reach the answer, but I will start with the method. Tell me which step feels uncertain, or use the mark-scheme button when you are ready to reveal it.'
  return 'Let’s take one small step. Write the probability expression or calculation you think should come first, and I’ll help you check the setup.'
}

function AiTutorPanel({ topic, question, activePart, activeAnswer, request, onRequest }) {
  const [messages, setMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const messageEndRef = useRef(null)
  const isEmpty = Boolean(question.isPlaceholder)

  useEffect(() => {
    setMessages([])
    setChatInput('')
  }, [question.id])

  useEffect(() => {
    if (!request) return
    const reply = buildTutorReply(request.type, question, request.part, request.answer)
    const labels = { hint: 'Hint', concept: 'Concept', check: 'Approach check' }
    setMessages((current) => [...current, { id: `${request.id}-reply`, role: 'assistant', text: reply, label: labels[request.type] || 'Tutor' }])
  }, [question, request])

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [messages])

  const sendMessage = (event) => {
    event.preventDefault()
    const message = chatInput.trim()
    if (!message) return
    const stamp = Date.now()
    setMessages((current) => [
      ...current,
      { id: `${stamp}-student`, role: 'student', text: message },
      { id: `${stamp}-assistant`, role: 'assistant', text: buildTutorReply('message', question, activePart, activeAnswer, message), label: 'Tutor' },
    ])
    setChatInput('')
  }

  return <aside className="ai-tutor-panel" aria-label="AI tutor">
    <header className="ai-tutor-header">
      <div className="ai-tutor-avatar"><Bot size={21} /></div>
      <div><div className="ai-tutor-title"><h2>AI Tutor</h2><span>Demo mode</span></div><p><i /> Ready to help</p></div>
    </header>
    <div className="ai-tutor-context"><span>Current focus</span><strong>{isEmpty ? `${topic.number} ${topic.title}` : `Question ${question.number} ${activePart.label}`}</strong><p>{isEmpty ? 'Questions are being prepared' : `${activePart.marks} ${activePart.marks === 1 ? 'mark' : 'marks'} · Guidance without giving the answer away`}</p></div>
    <div className="ai-tutor-conversation" aria-live="polite">
      {messages.length === 0 ? <div className="tutor-welcome">
        <div><Sparkles size={22} /></div>
        <h3>{isEmpty ? `Your ${topic.title} tutor is ready.` : 'Try it—I’m here if you get stuck.'}</h3>
        <p>{isEmpty ? 'When a reviewed question is loaded, I will follow its active part and help without taking over the solution.' : 'I can give a small hint, explain the idea, or check your setup while you keep control of the solution.'}</p>
      </div> : <div className="tutor-messages">{messages.map((message) => <div className={`tutor-message ${message.role}`} key={message.id}>{message.label && <span>{message.label}</span>}<p>{message.text}</p></div>)}<div ref={messageEndRef} /></div>}
    </div>
    <div className="tutor-quick-actions" aria-label="Tutor shortcuts">
      <button type="button" disabled={isEmpty} onClick={() => onRequest('hint', activePart, activeAnswer)}><Lightbulb size={15} /> Hint</button>
      <button type="button" disabled={isEmpty} onClick={() => onRequest('concept', activePart, activeAnswer)}><BookOpenCheck size={15} /> Explain concept</button>
      <button type="button" disabled={isEmpty} onClick={() => onRequest('check', activePart, activeAnswer)}><CheckCircle2 size={15} /> Check approach</button>
    </div>
    <form className="tutor-chat-form" onSubmit={sendMessage}>
      <label className="sr-only" htmlFor="tutor-message">Ask the AI tutor</label>
      <input id="tutor-message" value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder={isEmpty ? 'Available with a question' : 'Ask about this step…'} disabled={isEmpty} />
      <button type="submit" aria-label="Send message" disabled={isEmpty || !chatInput.trim()}><Send size={18} /></button>
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
      mark_scheme: { answer: '', marking_points: [] },
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
  const [tutorRequest, setTutorRequest] = useState(null)
  const answersRef = useRef({})
  const saveTimersRef = useRef(new Map())
  const saveVersionsRef = useRef(new Map())
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
    setTutorRequest(null)
    saveTimersRef.current.forEach((timer) => clearTimeout(timer))
    saveTimersRef.current.clear()
    if (!topic) return undefined
    let cancelled = false
    getStudentResponses(topic.number)
      .then((responses) => {
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
    setTutorRequest(null)
  }

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

  const askTutor = async (type, part, answer) => {
    if (!hasQuestions) return
    setActivePartId(part.id)
    if (type === 'check') {
      clearTimeout(saveTimersRef.current.get(part.id))
      saveTimersRef.current.delete(part.id)
      try {
        await persistAnswer(part.id, answer, 'ready_for_review')
      } catch {
        return
      }
    }
    setTutorRequest({ id: Date.now(), type, part, answer })
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
      <div className="practice-workspace">
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
        <AiTutorPanel topic={topic} question={question} activePart={activePart} activeAnswer={answers[activePart.id] || ''} request={tutorRequest} onRequest={askTutor} />
      </div>
    </div>
  </main>
}
