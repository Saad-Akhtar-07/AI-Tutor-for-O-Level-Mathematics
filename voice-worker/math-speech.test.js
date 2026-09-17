import test from 'node:test'
import assert from 'node:assert/strict'
import { prepareSpeech, plainToLatex } from './math-speech.js'

const read = text => prepareSpeech(text).segments.join(' ')
for (const [input, expected] of [
  ['3/5', /three fifths/], ['x²', /x squared/], ['x³', /x cubed/],
  ['3-5', /3 minus 5/], ['-3', /negative 3/], ['5!', /5 factorial/],
  ['2×10^-3', /2 times 10.*negative 3/], ['x_2', /x.*2/],
  ['0.25', /zero point two five/], ['0.05', /zero point zero five/],
  ['P(A)', /probability of upper A/], ['P(A|B)', /probability of upper A given upper B/],
  ['P(A ∩ B)', /intersection/], ['P(A ∪ B)', /union/],
  ['x ≤ 3', /less than or equals/], ['x >= 3', /greater than or equals/],
  ['x != 3', /not equals/], ['25%', /25 percent/],
  ['(a+b)/c', /open bracket a plus b close bracket over c/],
  ['1/(x+2)', /1 over open bracket x plus 2 close bracket/],
  ['-3/5', /negative 3 over 5/], ['sqrt(9)', /Root 9/],
  ['x^(-2)', /to the power of open bracket negative 2/],
  ['P(A) = 0.25', /probability of upper A equals zero point two five/],
  [String.raw`$\frac{a+b}{c}$`, /a plus b over c/],
  [String.raw`$\sqrt{9}$`, /Root 9/],
]) test(`pronunciation: ${input}`, () => {
  assert.match(read(`Try ${input}. What next?`), expected)
  assert.equal(prepareSpeech(input).warning, null)
})
test('plain fractions preserve precedence and nested grouping', () => {
  assert.equal(plainToLatex('a+b/c'), 'a + \\frac{b}{c}')
  assert.equal(plainToLatex('(a+b)/c'), '\\frac{\\left(a + b\\right)}{c}')
  assert.match(read('Try (a+(b*c))/d.'), /over d/)
  assert.notEqual(read('1/x+2'), read('1/(x+2)'))
})
test('prose and ambiguous student wording remain prose', () => {
  assert.equal(read('Try one over x plus two.'), 'Try one over x plus two.')
  assert.match(read('Try -3/5.'), /^Try /)
  assert.equal(read('Use the step-by-step explanation.'), 'Use the step-by-step explanation.')
  assert.equal(read('This is O-level maths.'), 'This is O-level maths.')
})
test('malformed or unsupported maths is explicit, never guessed', () => {
  for (const input of [String.raw`$\frac{1}{$`, 'Try 1/(x+2.', String.raw`Try \unknown{x}.`, 'Try √x.']) {
    const result = prepareSpeech(input)
    assert.ok(result.warning, input)
    assert.match(result.segments.join(' '), /check the mathematical expression/)
  }
})
test('decimals are not split into separate audio segments', () => {
  assert.deepEqual(prepareSpeech('Try 0.25.').segments, ['Try zero point two five .'])
})
test('long prose is bounded for inference', () => {
  assert.ok(prepareSpeech('Try the next step carefully. '.repeat(100)).segments.every(text => text.length <= 240))
})
