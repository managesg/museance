"""Chat brain for 'Seance · The Bailiff', the court officer judges talk to inside ASI:One.

The human is the Judge. The Bailiff has no model: every reply is a fixed template filled
with what the court measured. respond() is the only entry point; state is a plain dict.

Stages: lobby -> verdict -> (cross_prompt <-> cross_result | ruling_prompt) -> closed.
Hearing the argument keeps stage 'verdict' (same choices). cross_result and case_error
exist because their numbered choices differ from every other stage.
"""
import json
import re

CASES = {'1': 'todo', '2': 'app1'}
OTHER = {'1': '2', '2': '1'}
EXAMPLES = {'todo': 'add milk', 'app1': '7 / 8 ='}
MAX_WORDS = 20

LOBBY = ['1) The case of Todo', '2) The case of the Calculator', '3) How this court works']
VERDICT = ['1) Hear them argue', '2) Test it yourself', '3) Deliver your ruling']
CROSSED = ['1) Try another', '2) Back to the verdict', '3) Deliver your ruling']
RULING = ['1) Faithful', '2) Forgery', '3) Needs repair']
CLOSED = ['1) New case', '2) See the record', '3) Leave court']
OOPS = ['1) Try again', '2) Other case', '3) How this court works']
CHOICES = {'lobby': LOBBY, 'verdict': VERDICT, 'cross_result': CROSSED,
           'ruling_prompt': RULING, 'closed': CLOSED, 'case_error': OOPS}

GREETING = ['🔨 All rise! Your Honor, a dead app awaits your judgment.']
HOW = ['🐧 McClusky, Esq., a penguin medium, brought a dead app back to life.',
       '🦉 Dr. Hoot, an owl skeptic, argues it is a fake.',
       '🔍 A court with rules and no AI tests the original and the revival side by side.',
       '⚖️ Then you rule, Your Honor. The Bailiff has no opinion.']
ASK_RULING = ['⚖️ How do you rule, Your Honor?']
UNKNOWN = ['Your Honor, please choose 1, 2, or 3.']
ADJOURN = ['🔨 Court adjourned. Thank you, Your Honor.', 'Type "all rise" to reopen court.']
TRY_IT = '🔍 The court will try it on the original and the revival.'
SAME = '🔨 Same on both apps, Your Honor. The Bailiff has no opinion.'
DIFFERENT = '🔨 They differ, Your Honor. The Bailiff has no model. The Bailiff noticed anyway.'
SPEAKERS = {'hoot': '🦉 Hoot:', 'mcclusky': '🐧 McClusky:', 'bailiff': '🔨 Bailiff:'}
RULED = {1: 'Faithful', 2: 'Forgery', 3: 'Needs repair'}
REACTIONS = {  # (ruling, evidence agrees)
    (1, True): '🐧 McClusky bows deeply. 🦉 Hoot sulks in the rafters.',
    (2, True): '🦉 Hoot gloats. 🐧 McClusky faints onto the evidence table.',
    (3, True): '🦉 Hoot gloats. 🐧 McClusky bows and sends the revival back to the workshop.',
    (1, False): '🐧 McClusky bows, a little too quickly. 🦉 Hoot sulks.',
    (2, False): '🐧 McClusky faints. 🦉 Hoot sulks. Even he found nothing.',
    (3, False): '🐧 McClusky faints. 🦉 Hoot sulks. There is nothing to repair.',
}

NUMBERS = {'1': 1, 'one': 1, 'first': 1, '1st': 1, '2': 2, 'two': 2, 'second': 2, '2nd': 2,
           '3': 3, 'three': 3, 'third': 3, '3rd': 3}
NEGATIONS = {'no', 'not', 'isnt', 'never', 'dont', 'cant', 'cannot', 'wasnt', 'doesnt', 'didnt', 'wont',
             'wouldnt', 'shouldnt', 'arent', 'aint', 'nope'}
FILLER = {'the', 'a', 'number', 'option', 'choice', 'case', 'please', 'i', 'pick', 'choose', 'take', 'go',
          'with', 'lets', 'let', 'us', 'of', 'ok', 'okay', 'to', 'me', 'now', 'just', 'want', 'like'}
BACK = {'back', 'cancel', 'go back'}
HOW_WORDS = {'how', 'help', 'work', 'works', 'explain'}
KEYWORDS = {
    'lobby': {1: {'todo'}, 2: {'calculator', 'calc'}, 3: HOW_WORDS},
    'verdict': {1: {'argue', 'argument', 'hear', 'debate'}, 2: {'test', 'try', 'yourself'},
                3: {'rule', 'ruling', 'deliver', 'decide', 'verdict'}},
    'cross_result': {1: {'another', 'again', 'try', 'more'}, 2: {'back', 'verdict', 'return'},
                     3: {'rule', 'ruling', 'deliver', 'decide'}},
    'ruling_prompt': {1: {'faithful', 'genuine', 'authentic'}, 2: {'forgery', 'forged', 'fake', 'fraud'},
                      3: {'repair', 'fix', 'broken'}},
    'closed': {1: {'new', 'another', 'next'}, 2: {'record', 'see', 'show'},
               3: {'leave', 'exit', 'quit', 'bye', 'goodbye', 'adjourn', 'done'}},
    'case_error': {1: {'again', 'retry'}, 2: {'other', 'another', 'different'}, 3: HOW_WORDS},
}
_UNSAFE = str.maketrans('', '', '[]{}`')


def respond(state, text, *, run_case, run_cross, run_argue=None):
    """One chat turn. Returns (reply_text, new_state); state is None for a new judge.
    run_argue(app) -> [{who, line}]: the parties argue live; without it (or if it fails) the argument on file."""
    raw, norm = _clean(text)
    stage = (state or {}).get('stage')
    if stage == 'cross_prompt' and _menu(norm, 'cross_result') and not (
            CASES[state['case']] == 'app1' and norm.isdigit()):  # Todo has no "3" to test; the Calculator does
        stage = 'cross_result'  # "back", "rule", or a menu number: the judge is moving on
    elif stage == 'cross_prompt' or (stage == 'cross_result' and raw and not _menu(norm, 'cross_result')):
        return _cross(state, raw, norm, run_cross)  # after a test, anything but a menu choice is the next test
    if stage not in CHOICES:  # a new judge, or a state this version does not know
        stage, state = 'lobby', None
    pick = _pick(norm, KEYWORDS[stage])
    if pick is None:
        if state is None:
            return _say(GREETING + LOBBY), {'stage': 'lobby'}
        return _say(UNKNOWN + CHOICES[stage]), state
    if stage in ('lobby', 'case_error'):
        if pick == 3:
            return _say(HOW + LOBBY), {'stage': 'lobby'}
        if stage == 'lobby':
            return _open(str(pick), run_case)
        return _open(state['case'] if pick == 1 else OTHER[state['case']], run_case)
    s = state['summary']
    if stage == 'verdict':
        if pick == 1:
            return _say(_argue(_heard(s, state['case'], run_argue))), state
        if pick == 2:
            return _say(_cross_prompt(state)), {**state, 'stage': 'cross_prompt'}
        return _say(ASK_RULING + RULING), {**state, 'stage': 'ruling_prompt'}
    if stage == 'cross_result':
        if pick == 1:
            return _say(_cross_prompt(state)), {**state, 'stage': 'cross_prompt'}
        if pick == 2:
            return _say(_back(s)), {**state, 'stage': 'verdict'}
        return _say(ASK_RULING + RULING), {**state, 'stage': 'ruling_prompt'}
    if stage == 'ruling_prompt':
        return _say(_rule(s, pick)), {**state, 'stage': 'closed'}
    if pick == 1:  # closed
        return _say(GREETING + LOBBY), {'stage': 'lobby'}
    if pick == 2:
        return _say(_record(s)), state
    return _say(ADJOURN), None


def _clean(text):
    """The text without leading @mentions, plus a lowercase, punctuation-free copy for matching."""
    words = str(text or '').split()
    while words and words[0].startswith('@'):
        words.pop(0)
    raw = ' '.join(words)
    return raw, ' '.join(re.sub(r'[^\w\s]', '', raw.lower()).split())


def _pick(norm, keywords):
    """1, 2 or 3 when every clue in the judge's words (digits, keywords, number words) names the same choice."""
    words = set(norm.split())
    if words & NEGATIONS:
        return None
    digits = {NUMBERS[w] for w in words if w.isdigit() and w in NUMBERS}
    keys = {n for n, k in keywords.items() if words & k}
    named = {NUMBERS[w] for w in words if w in NUMBERS and not w.isdigit() and w != 'one'}
    named = named or ({1} if 'one' in words else set())  # 'one' is also a pronoun: "the second one"
    if words - set(NUMBERS) - FILLER:  # "the other one", "wait a second": number words only count among filler
        named = set()
    picks = digits | keys | named
    return picks.pop() if len(picks) == 1 else None


def _menu(norm, stage):
    """The words are only a menu choice (a number, a keyword, filler), not a test like "1 / 0 =" or "add eggs"."""
    words = set(norm.split())
    return bool(words) and words <= FILLER | set(NUMBERS) | set().union(*KEYWORDS[stage].values())


def _heard(s, case, run_argue):
    """The summary with the argument heard live from the parties, else as it is (argument on file)."""
    try:
        said = [{'who': str(a['who']), 'line': str(a['line'])} for a in run_argue(CASES[case])] if run_argue else []
    except Exception:  # a party did not answer: the argument on file still stands
        said = []
    return {**s, 'argument': said} if said else s


def _open(case, run_case):
    try:
        s = run_case(CASES[case])
    except Exception as e:  # by contract the pipeline explains its failures in plain words
        return _oops(case, _reason(e))
    try:
        s = json.loads(json.dumps(s))  # state must survive the agent's storage
        lines = _verdict(s)
        _argue(s)
        _record(s)  # fail now, not mid-case, if the case file has gaps
    except Exception:
        return _oops(case, 'The case file is incomplete.')
    return _say(lines), {'stage': 'verdict', 'case': case, 'summary': s}


def _oops(case, reason):
    lines = [f'🔨 The court could not open that case. {reason}', 'Your Honor, what now?', *OOPS]
    return _say(lines), {'stage': 'case_error', 'case': case}


def _reason(e):
    first_line = (str(e).strip().splitlines() or [''])[0]
    return ' '.join(first_line.split()[:12]) or 'The witnesses did not show up.'


def _verdict(s):
    n = len(s['differences'])
    held = (f"All {s['claims']} claims held" if s['locked'] == s['claims']
            else f"{s['locked']} of {s['claims']} claims held")
    busted = f", {s['struck']} busted" if s['struck'] else ''
    found = f"found {_count(n, 'difference')}" if n else 'found no differences'
    evidence = ([_exhibit('❌', d) for d in s['differences']] + [_exhibit('✅', e) for e in s['examples'][:1]]
                + [f'🔨 Struck from the record: {x}' for x in s['struck_examples']])
    return [f"⚖️ The case of {s['title']}: is the revival the same app as the dead original?",
            f"🐧 McClusky swore {s['claims']} claims. 🦉 Hoot attacked with {s['attacks']}.",
            f'🔍 {held}{busted}. The court {found} between the apps.',
            *evidence[:2], 'Your Honor, what now?', *VERDICT]


def _exhibit(mark, r):
    return f"{mark} {r['did']} → Original: {r['original']} · Revival: {r['revival']}"


def _count(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def _argue(s):
    said = [f"{SPEAKERS[a['who']]} {a['line']}" for a in s['argument'] if a.get('who') in SPEAKERS][:4]
    return (said or ['🔨 Bailiff: Both sides rest. The Bailiff has no opinion.']) + ['Your Honor, what now?', *VERDICT]


def _back(s):
    return [f"⚖️ Back to the case of {s['title']}.", 'Your Honor, what now?', *VERDICT]


def _cross_prompt(state, first=TRY_IT):
    example = EXAMPLES[CASES[state['case']]]
    return [first, 'Type "back" to return to the verdict.', f'Your Honor, type something to try, like "{example}".']


def _cross(state, raw, norm, run_cross):
    if norm in BACK:
        return _say(_back(state['summary'])), {**state, 'stage': 'verdict'}
    if not raw:
        return _say(_cross_prompt(state)), state
    try:
        r = run_cross(CASES[state['case']], raw)
        r = {k: str(r[k]) for k in ('did', 'original', 'revival')}
    except ValueError as e:  # the court cannot map this action: say why, let the judge retry
        return _say(_cross_prompt(state, f'🔍 {e}')), state
    except Exception:  # court down or a malformed answer: same retry, plain words
        return _say(_cross_prompt(state, '🔍 The court could not run that test just now.')), state
    same = r['original'].strip() == r['revival'].strip()
    s = state['summary']
    if not same and all(d['did'] != r['did'] for d in s['differences']):
        s = {**s, 'differences': s['differences'] + [r]}  # what the judge finds is evidence too
    lines = [f"🔍 {r['did']}", f"Original: {r['original']} · Revival: {r['revival']} {'✅' if same else '❌'}",
             SAME if same else DIFFERENT, *CROSSED]
    return _say(lines), {**state, 'stage': 'cross_result', 'summary': s}


def _rule(s, pick):
    n = len(s['differences'])
    agrees = (pick == 1) == (n == 0)  # faithful iff no differences; forgery and repair both fit any
    if agrees:
        said = '✅ The evidence agrees with Your Honor.'
    elif n:
        said = f"❌ Objection, Your Honor! The evidence says {_count(n, 'difference')} between the apps."
    else:
        said = f"❌ Objection, Your Honor! The evidence says 0 differences in {s['attacks']} attacks."
    return [f'⚖️ Your Honor rules: {RULED[pick]}.', said, REACTIONS[pick, agrees], '🔨 Case closed.', *CLOSED]


def _record(s):
    start, end = s['credibility'][0], s['credibility'][-1]
    moved = (f'rose from {start} to {end}' if end > start
             else f'fell from {start} to {end}' if end < start else f'stayed at {end}')
    n = len(s['differences'])
    found = f"{_count(n, 'difference')} found." if n else 'No differences found.'
    sealed = ('🔨 Every step is in a tamper-proof record. Nobody can rewrite it.' if s['ledger']['intact']
              else '🔨 Warning: this record failed its tamper check.')
    return [f"📜 The record, Your Honor: {s['locked']} claims locked, {s['struck']} struck.",
            f"🔍 Hoot attacked {s['attacks']} times. The court took {s['seconds']} seconds. {found}",
            f"⚖️ Fidelity score: {s['fidelity']} out of 100.",
            f"🐧 McClusky's credibility {moved}.",
            sealed, *CLOSED]


def _say(lines):
    """Final check on every reply: no brackets, and no line over MAX_WORDS (long lines are split, not cut)."""
    out = []
    for line in lines:
        words = line.translate(_UNSAFE).split()
        out += [' '.join(words[i:i + MAX_WORDS]) for i in range(0, len(words), MAX_WORDS)]
    picks = [line for line in out if re.match(r'\d\) ', line)]  # ASI:One renders Markdown: single newlines collapse
    return '\n\n'.join([line for line in out if line not in picks] + (['\n'.join(picks)] if picks else []))
