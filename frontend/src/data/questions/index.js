import probabilityQuestionBank from './probability.json'

const questionBanksByTopic = {
  '8': probabilityQuestionBank,
}

export function getQuestionBank(topicNumber) {
  return questionBanksByTopic[String(topicNumber)] || null
}

export function getQuestionCount(topicNumber) {
  return getQuestionBank(topicNumber)?.questions?.length || 0
}

export function hasQuestionBank(topicNumber) {
  return getQuestionCount(topicNumber) > 0
}
