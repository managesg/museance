// Fixture calculator (fixtures/app1) button ids and the face printed on each keycap.
export const KEY_LABELS: Record<string, string> = {
  k7: '7',
  k8: '8',
  k1: '1',
  k0: '0',
  kadd: '+',
  kmul: '×',
  kdiv: '÷',
  kdot: '.',
  keq: '=',
  kc: 'C',
};

// Steps follow CONTRACTS.md: click:<selector>, type:<selector>:<text>, key:<name>, wait:<ms>.
export function stepLabel(step: string): string {
  const cut = step.indexOf(':');
  if (cut < 0) return step;
  const verb = step.slice(0, cut);
  const arg = step.slice(cut + 1);
  if (verb === 'click') {
    const id = /^#[\w-]+$/.test(arg) ? arg.slice(1) : '';
    return Object.hasOwn(KEY_LABELS, id) ? KEY_LABELS[id] : id || arg;
  }
  if (verb === 'type') return `"${arg.slice(arg.indexOf(':') + 1)}"`;
  if (verb === 'key') return arg;
  if (verb === 'wait') return `wait ${arg}ms`;
  return step;
}
