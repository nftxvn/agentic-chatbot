#!/usr/bin/env node
// Read-only structural checks. Browser scenarios separately check runtime behavior.
const fs = require('node:fs');
const path = require('node:path');
const cp = require('node:child_process');
const { isDeepStrictEqual } = require('node:util');
const parser = require('@babel/parser');

const root = path.resolve(__dirname, '../..');
const defaultBaseline = '129834bddfde6cd9253b270553d9ac7e0283db05';
const git = (...args) => cp.execFileSync('git', args, { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
const parse = source => parser.parse(source, { sourceType: 'module', plugins: ['jsx'] });
const ignored = new Set(['start', 'end', 'loc', 'extra', 'leadingComments', 'innerComments', 'trailingComments', 'comments', 'tokens']);
function clean(value) {
  if (Array.isArray(value)) return value.map(clean);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(Object.entries(value).filter(([key]) => !ignored.has(key)).map(([key, item]) => [key, clean(item)]));
}
function requireEqual(actual, expected, message) {
  if (!isDeepStrictEqual(actual, expected)) throw new Error(message);
}
function find(node, predicate) {
  if (!node || typeof node !== 'object') return null;
  if (predicate(node)) return node;
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) {
      for (const child of value) { const hit = find(child, predicate); if (hit) return hit; }
    } else if (value && typeof value === 'object') {
      const hit = find(value, predicate); if (hit) return hit;
    }
  }
  return null;
}
function jsx(source) {
  const result = [];
  function walk(value) {
    if (!value || typeof value !== 'object') return;
    if (Array.isArray(value)) return value.forEach(walk);
    if (value.type === 'JSXElement' || value.type === 'JSXFragment') { result.push(clean(value)); return; }
    Object.values(value).forEach(walk);
  }
  walk(parse(source));
  return result;
}
function normalizeBadge(value) {
  if (Array.isArray(value)) return value.map(normalizeBadge);
  if (!value || typeof value !== 'object') return value;
  if (value.type === 'JSXElement' && value.openingElement.name.name === 'TicketStatusBadge') {
    if (value.openingElement.attributes.length !== 1 || !value.openingElement.selfClosing)
      throw new Error('Unexpected badge props or children');
    const status = value.openingElement.attributes.find(item => item.name.name === 'status').value.expression;
    return { type: 'JSXExpressionContainer', expression: { type: 'CallExpression', callee: { type: 'Identifier', name: 'getStatusBadge' }, arguments: [status] } };
  }
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, normalizeBadge(item)]));
}
function badgeEquivalent(before, after) {
  const main = values => values.sort((a, b) => JSON.stringify(b).length - JSON.stringify(a).length)[0];
  requireEqual(normalizeBadge(main(jsx(after))), main(jsx(before)), 'Live chat markup changed beyond badge extraction');
  const oldHelper = find(parse(before), node => node.type === 'VariableDeclarator' && node.id.name === 'getStatusBadge');
  const oldSwitch = find(oldHelper, node => node.type === 'SwitchStatement');
  const badge = parse(fs.readFileSync(path.join(root, 'admin-frontend/src/components/Tickets/TicketStatusBadge.jsx'), 'utf8'));
  const map = find(badge, node => node.type === 'VariableDeclarator' && node.id.name === 'STATUS_PRESENTATION').init;
  const fallback = find(badge, node => node.type === 'VariableDeclarator' && node.id.name === 'presentation').init.right;
  const span = find(badge, node => node.type === 'JSXElement');
  requireEqual(span.openingElement.name.name, 'span', 'Badge root changed');
  requireEqual(span.openingElement.attributes.length, 1, 'Badge attributes changed');
  const children = span.children.filter(item => item.type !== 'JSXText' || item.value.trim());
  requireEqual(children.map(item => clean(item)), [{type:'JSXExpressionContainer',expression:{type:'MemberExpression',object:{type:'Identifier',name:'presentation'},computed:false,property:{type:'Identifier',name:'label'}}}], 'Badge children changed');
  const template = span.openingElement.attributes.find(item => item.name.name === 'className').value.expression;
  const base = template.quasis.map(item => item.value.cooked).join('');
  requireEqual(template.expressions.map(clean), [{type:'MemberExpression',object:{type:'Identifier',name:'presentation'},computed:false,property:{type:'Identifier',name:'classes'}}], 'Badge class expression changed');
  const tokens = value => value.trim().split(/\s+/).sort();
  const states = ['open', 'in_progress', 'resolved', 'pending'];
  for (const status of states) {
    const oldCase = oldSwitch.cases.find(item => item.test?.value === status) || oldSwitch.cases.find(item => item.test === null);
    const oldSpan = find(oldCase, node => node.type === 'JSXElement');
    const oldClass = oldSpan.openingElement.attributes.find(item => item.name.name === 'className').value.value;
    const oldLabel = oldSpan.children.filter(item => item.type === 'JSXText').map(item => item.value).join('').trim() || status;
    const entry = map.properties.find(item => item.key.name === status)?.value || fallback;
    const values = Object.fromEntries(entry.properties.map(item => [item.key.name, item.value.type === 'StringLiteral' ? item.value.value : status]));
    requireEqual(tokens(base + values.classes), tokens(oldClass), `Badge classes changed: ${status}`);
    requireEqual(values.label, oldLabel, `Badge label changed: ${status}`);
  }
  return states;
}
function expandedWorkflow(source, componentName, hookName, readHook) {
  const component = find(parse(source), node => node.type === 'FunctionDeclaration' && node.id.name === componentName);
  if (!component) throw new Error(`Missing component ${componentName}`);
  return component.body.body.flatMap(statement => {
    const declaration = statement.type === 'VariableDeclaration' && statement.declarations.length === 1 ? statement.declarations[0] : null;
    if (declaration?.init?.type !== 'CallExpression' || declaration.init.callee.name !== hookName) return [clean(statement)];
    const hook = find(parse(readHook()), node => node.type === 'FunctionDeclaration' && node.id.name === hookName);
    if (!hook || hook.body.body.at(-1).type !== 'ReturnStatement') throw new Error(`Invalid hook ${hookName}`);
    const returned = hook.body.body.at(-1).argument;
    if (returned.type !== 'ObjectExpression') throw new Error(`Expected controller object from ${hookName}`);
    const available = new Set(returned.properties.map(item => item.key.name));
    for (const property of declaration.id.properties) {
      if (!available.has(property.key.name) || property.key.name !== property.value.name)
        throw new Error(`Missing/renamed controller binding: ${hookName}.${property.key.name}`);
    }
    const body = hook.body.body.slice(0, -1);
    if (body[0]?.type === 'ExpressionStatement' && body[0].expression.type === 'StringLiteral') body.shift();
    return body.map(clean);
  });
}
function main() {
  const args = process.argv.slice(2);
  let baseline = defaultBaseline, reportPath;
  for (let index = 0; index < args.length; index++) {
    if (args[index] === '--baseline' && args[index + 1]) baseline = args[++index];
    else if (args[index] === '--report' && args[index + 1]) reportPath = args[++index];
    else throw new Error('Usage: npm run verify:ui -- [--baseline COMMIT] [--report FILE]');
  }
  baseline = git('rev-parse', '--verify', '--end-of-options', `${baseline}^{commit}`).trim();
  const before = file => git('show', `${baseline}:${file}`);
  const current = file => fs.readFileSync(path.join(root, file), 'utf8');
  const files = git('ls-tree', '-r', '-z', '--name-only', baseline, 'admin-frontend/src', 'admin-frontend/public', 'admin-frontend/index.html').split('\0').filter(Boolean);
  const result = { baseline, jsxIdentical: [], badgeStatesVerified: [], stylesAssetsIdentical: [], workflowsIdentical: [] };
  for (const file of files) {
    if (file.endsWith('.jsx')) {
      const oldSource = before(file), newSource = current(file);
      if (isDeepStrictEqual(jsx(oldSource), jsx(newSource))) result.jsxIdentical.push(file);
      else if (file === 'admin-frontend/src/pages/LiveChatPage.jsx') result.badgeStatesVerified = badgeEquivalent(oldSource, newSource);
      else throw new Error(`JSX changed: ${file}`);
    } else if (/\.(css|svg|png|jpe?g|webp|woff2?|ttf)$/.test(file) || file === 'admin-frontend/index.html') {
      const oldBytes = cp.execFileSync('git', ['show', `${baseline}:${file}`], { cwd: root });
      if (!oldBytes.equals(fs.readFileSync(path.join(root, file)))) throw new Error(`Style/asset changed: ${file}`);
      result.stylesAssetsIdentical.push(file);
    }
  }
  for (const [component, hook] of [['DirectorySettings', 'useDirectorySettings'], ['FastPathSettings', 'useFastPathSettings']]) {
    const file = `admin-frontend/src/components/Settings/${component}.jsx`;
    const hookFile = `admin-frontend/src/hooks/settings/${hook}.js`;
    if (!find(parse(current(file)), node => node.type === 'CallExpression' && node.callee.name === hook))
      throw new Error(`Missing extracted controller ${hook} in ${component}`);
    const oldBody = expandedWorkflow(before(file), component, hook, () => before(hookFile));
    const newBody = expandedWorkflow(current(file), component, hook, () => current(hookFile));
    requireEqual(newBody, oldBody, `Workflow/hook order, state, effect, validation or payload changed: ${component}`);
    result.workflowsIdentical.push(component);
  }
  result.status = 'passed';
  if (reportPath) {
    fs.mkdirSync(path.dirname(path.resolve(reportPath)), { recursive: true });
    fs.writeFileSync(reportPath, JSON.stringify(result, null, 2) + '\n');
  }
  console.log(JSON.stringify({ status: result.status, baseline, jsxIdentical: result.jsxIdentical.length, badgeStates: result.badgeStatesVerified, stylesAssetsIdentical: result.stylesAssetsIdentical.length, workflowsIdentical: result.workflowsIdentical }));
}
try { main(); } catch (error) { console.error(`UI verification failed: ${error.message}`); process.exitCode = 1; }
