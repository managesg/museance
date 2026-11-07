// The court writes a failed run as output text; this turns it into words a viewer can read.

/** 'ERROR:observe <sel>: <Exc>' -> 'no <sel> on the page'; 'ERROR:step <i> <step>: <Exc>' -> 'step <i> failed'; else as given. */
export function prettyOutput(s: string): string {
  const observe = /^ERROR:observe (.+?): /.exec(s);
  if (observe) return `no ${observe[1]} on the page`;
  const step = /^ERROR:step (\d+) /.exec(s);
  return step ? `step ${step[1]} failed` : s;
}
