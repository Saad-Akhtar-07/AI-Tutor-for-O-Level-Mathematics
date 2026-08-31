import { BookOpenCheck, ChevronLeft, ChevronRight, Eye, EyeOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import InlineContent from '../components/notes/InlineContent.jsx'
import SyllabusSidebar from '../components/SyllabusSidebar.jsx'
import probabilityData from '../data/questions/probability.json'
import { syllabus } from '../data/syllabus.js'

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

function QuestionPart({ part }) {
  const [showScheme, setShowScheme] = useState(false)
  const schemeId = `${part.id}-scheme`
  return <section className="question-part"><div className="question-part-heading"><span>{part.label}</span><strong>{part.marks} {part.marks === 1 ? 'mark' : 'marks'}</strong></div><div className="question-part-prompt">{part.prompt.map((block, index) => <QuestionBlock block={block} key={index} />)}</div><label className="answer-label" htmlFor={`${part.id}-answer`}>Your working and answer</label><div className="answer-row"><textarea id={`${part.id}-answer`} rows="3" spellCheck="false" />{part.answer_suffix && <span>{part.answer_suffix}</span>}</div><button type="button" className={`mark-scheme-toggle ${showScheme ? 'is-open' : ''}`} aria-expanded={showScheme} aria-controls={schemeId} onClick={() => setShowScheme((visible) => !visible)}>{showScheme ? <EyeOff size={17} /> : <Eye size={17} />}{showScheme ? 'Hide mark scheme' : 'Show mark scheme'}</button>{showScheme && <div className="mark-scheme-panel" id={schemeId}><div className="scheme-answer"><span>Answer</span><p><InlineContent content={part.mark_scheme.answer} /></p></div>{part.mark_scheme.marking_points.length > 0 && <div className="scheme-points"><span>How marks are awarded</span><ol>{part.mark_scheme.marking_points.map((point, index) => <li key={`${point.code}-${index}`}><strong>{point.code}</strong><p><InlineContent content={point.text} /></p></li>)}</ol></div>}</div>}</section>
}

export default function ProbabilityPracticePage() {
  const topic = syllabus.find((item) => item.number === '8')
  const [questionIndex, setQuestionIndex] = useState(0)
  const question = probabilityData.questions[questionIndex]
  useEffect(() => { document.title = `Probability practice - Question ${question.number} - Mathematics 4024`; window.scrollTo(0, 0) }, [question.number])
  const moveTo = (index) => setQuestionIndex(Math.max(0, Math.min(probabilityData.questions.length - 1, index)))
  return <main className="reader-shell" id="main-content" tabIndex="-1"><SyllabusSidebar topic={topic} activeCode="practice" /><div className="reader-main practice-reader-main"><nav className="breadcrumbs" aria-label="Breadcrumb"><ol><li><Link to="/">Syllabus</Link></li><li><ChevronRight size={14} /></li><li><Link to="/topic/8">8 Probability</Link></li><li><ChevronRight size={14} /></li><li><span aria-current="page">Practice questions</span></li></ol></nav><header className="practice-heading"><div><p>TOPIC 8 - PROBABILITY</p><h1>Practice questions</h1><span>20 reviewed questions - 115 marks - examiner marking points included</span></div><BookOpenCheck size={38} /></header><nav className="question-picker" aria-label="Choose a question"><span>Question</span><div>{probabilityData.questions.map((item, index) => <button type="button" key={item.id} className={index === questionIndex ? 'active' : ''} aria-current={index === questionIndex ? 'step' : undefined} onClick={() => moveTo(index)}>{item.number}</button>)}</div></nav><article className="exam-question" key={question.id}><header className="exam-question-header"><div className="question-number">{String(question.number).padStart(2, '0')}</div><div><p>{question.syllabus_codes.map((code) => `Syllabus ${code}`).join(' - ')}</p><h2>{question.title}</h2></div><strong>{question.total_marks} marks</strong></header><div className="question-stimulus">{question.prompt.map((block, index) => <QuestionBlock block={block} key={index} />)}</div><div className="question-parts">{question.parts.map((part) => <QuestionPart part={part} key={part.id} />)}</div></article><nav className="practice-pagination" aria-label="Question navigation"><button type="button" onClick={() => moveTo(questionIndex - 1)} disabled={questionIndex === 0}><ChevronLeft size={18} /> Previous question</button><span>{questionIndex + 1} of {probabilityData.questions.length}</span><button type="button" onClick={() => moveTo(questionIndex + 1)} disabled={questionIndex === probabilityData.questions.length - 1}>Next question <ChevronRight size={18} /></button></nav></div></main>
}
