const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const Module = require('node:module');
const filename = path.resolve(__dirname, '../src/predictionCategoryChoices.ts');
const source = fs.readFileSync(filename, 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {target: ts.ScriptTarget.ES2021, module: ts.ModuleKind.CommonJS}}).outputText;
const moduleUnderTest = new Module(filename, module);
moduleUnderTest.filename = filename;
moduleUnderTest.paths = module.paths;
moduleUnderTest._compile(compiled, filename);
const {predictionCategoryChoices} = moduleUnderTest.exports;

test('identical-looking categories have distinct accessible labels while raw input values stay exact', () => {
  const input = Object.freeze([' Gauteng ', 'Gauteng', 'Mpumalanga']);
  const result = predictionCategoryChoices(input);
  assert.deepEqual(result.map(x => x.value), input);
  assert.equal(result[0].label, 'Gauteng (leading: SPACE; trailing: SPACE)');
  assert.equal(result[1].label, 'Gauteng (exact value)');
  assert.equal(result[2].label, 'Mpumalanga');
  assert.notEqual(result[0].label, result[1].label);
});

test('different leading and trailing category whitespace is visible, never silently normalized', () => {
  const result = predictionCategoryChoices(['North', ' North', 'North ', 'North  ', 'South']);
  assert.equal(new Set(result.map(x => x.label)).size, result.length);
  assert.deepEqual(result.map(x => x.value), ['North', ' North', 'North ', 'North  ', 'South']);
});

test('no whitespace collision preserves original category labels and order', () => {
  assert.deepEqual(predictionCategoryChoices(['Zulu', 'Gauteng', 'Mpumalanga']), [
    {value: 'Zulu', label: 'Zulu'}, {value: 'Gauteng', label: 'Gauteng'}, {value: 'Mpumalanga', label: 'Mpumalanga'}
  ]);
});

test('blank and whitespace-only option values retain distinct original strings', () => {
  const input = ['', ' ', '  ', 'Other'];
  const result = predictionCategoryChoices(input);
  assert.deepEqual(result.map(x => x.value), input);
  assert.equal(new Set(result.slice(0, 3).map(x => x.label)).size, 3);
  assert.equal(result[3].label, 'Other');
});

test('space, tab, and mixed whitespace never produce the same visible option label', () => {
  const original = ['Gauteng', ' Gauteng', '\tGauteng', ' \tGauteng', 'Gauteng ', 'Gauteng\t'];
  const choices = predictionCategoryChoices(original);
  assert.equal(new Set(choices.map(c => c.label)).size, original.length);
  assert.deepEqual(choices.map(c => c.value), original);
  assert.match(choices[1].label, /SPACE/);
  assert.match(choices[2].label, /TAB/);
});

test('whitespace-only variants retain a unique visible label', () => {
  const original = ['', ' ', '\t', '\u00a0', ' \t'];
  const choices = predictionCategoryChoices(original);
  assert.equal(new Set(choices.map(c => c.label)).size, original.length);
  assert.deepEqual(choices.map(c => c.value), original);
  assert.match(choices[0].label, /empty raw value/);
  assert.match(choices[3].label, /NO-BREAK SPACE/);
});

test('Predict React UI renders option labels but submits original values', () => {
  const app = fs.readFileSync(path.resolve(__dirname, '../src/App.tsx'), 'utf8');
  assert.match(app, /import \{predictionCategoryChoices\} from '\.\/predictionCategoryChoices'/);
  assert.match(app, /predictionCategoryChoices\(f\.options\?\?\[\]\)\.map\(/);
  assert.match(app, /<option key=\{c\.value\} value=\{c\.value\}>\{c\.label\}<\/option>/);
  assert.match(app, /\[f\.name,predictVals\[f\.name\]\?\?''\]/);
});
