// Stub DOM evaluation, following eval/run_fixture.js; never reads original HTML.
// Run through check_revival.py for the OS network and Node permission sandboxes.
'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
// HTMLParser supplies actual elements and scripts, excluding HTML comments.
const {elements, scripts} = JSON.parse(fs.readFileSync(0, 'utf8'));
const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const rows = Array.isArray(data) ? data : [...data.good, ...data.traps];
// Only seed actual HTML elements. Missing IDs must fail, not be fabricated.
const setup = `
  const elements = Object.create(null);
  for (const {id, text} of ${JSON.stringify(elements)}) {
    const listeners = Object.create(null);
    elements[id] = {
      id, innerText: text, value: text, onclick: null,
      get textContent() { return this.innerText; },
      set textContent(value) { this.innerText = String(value); },
      addEventListener(type, callback) { (listeners[type] ??= []).push(callback); },
      click() {
        const event = {type: 'click', target: this, currentTarget: this};
        if (this.onclick) this.onclick(event);
        for (const callback of listeners.click ?? []) callback.call(this, event);
      }
    };
  }
  const document = {
    getElementById(id) { return elements[id] ?? null; },
    querySelector(selector) {
      if (!selector.startsWith('#')) throw new Error('Stub DOM supports ID selectors only');
      return elements[selector.slice(1)] ?? null;
    }
  };
  const window = globalThis;
`;
const output = Object.create(null);
for (const row of rows) {
  const context = vm.createContext(Object.create(null), {codeGeneration: {strings: false, wasm: false}, microtaskMode: 'afterEvaluate'});
  try {
    vm.runInContext(setup, context, {timeout: 1000});
    for (const script of scripts) vm.runInContext(script, context, {timeout: 1000});
    for (const step of row.steps) {
      const [kind, selector, ...rest] = step.split(':');
      let action;
      if (kind === 'click') action = `document.querySelector(${JSON.stringify(selector)}).click()`;
      else if (kind === 'type') action = `document.querySelector(${JSON.stringify(selector)}).value = ${JSON.stringify(rest.join(':'))}`;
      else throw new Error('Unsupported stub DOM step: ' + step);
      vm.runInContext(action, context, {timeout: 1000});
    }
    const observed = vm.runInContext(`String(document.querySelector(${JSON.stringify(row.observe)}).innerText)`, context, {timeout: 1000});
    output[row.id] = {observed};
  } catch (error) {
    output[row.id] = {error: String(error.message)};
  }
}
console.log(JSON.stringify(output));
