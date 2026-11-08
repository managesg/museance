"""Chat flow for 'Seance · The Bailiff', the court officer judges talk to inside ASI:One.

The human is the Judge. respond() is the only entry point; state is a plain JSON dict. respond is pure: the docket,
the court and the Bailiff's ears arrive as arguments. The court has no model: every verdict and every number comes
from run_case and run_cross (the deterministic court). The ears may: understand() (brain.py, ASI-1) maps free text
to one court action. Digits and menu words never reach it, and when it is unsure or down the keyword parser decides.
Nothing app-specific lives here: the cases, their titles and their test examples are the docket's rows.

Stages: lobby -> verdict -> (cross_prompt <-> cross_result | ruling_prompt) -> closed.
Hearing the argument keeps stage 'verdict' (same choices). cross_result and case_error
exist because their numbered choices differ from every other stage.
"""
import json
import re
from collections import Counter

MAX_WORDS, SHOWN, HISTORY = 20, 3, 6  # words per line, numbered choices per reply, chat lines the ears remember

VERDICT = ['1) Hear them argue', '2) Test it yourself', '3) Deliver your ruling']
CROSSED = ['1) Try another', '2) Back to the verdict', '3) Deliver your ruling']
RULING = ['1) Faithful', '2) Forgery', '3) Needs repair']
CLOSED = ['1) New case', '2) See the record', '3) Leave court']
OOPS = ['1) Try again', '2) Other case', '3) How this court works']
HOW_ITEM = 'How this court works'  # the lobby's last choice while the docket has fewer than SHOWN cases
CHOICES = {'verdict': VERDICT, 'cross_prompt': CROSSED, 'cross_result': CROSSED, 'ruling_prompt': RULING,
           'closed': CLOSED, 'case_error': OOPS}  # the test prompt shows no numbers; the last menu still counts
STAGES = {'lobby', *CHOICES}
CROSS = ('cross_prompt', 'cross_result')
ACTS = {'verdict': ('argue', 'test', 'rule'), 'cross_prompt': ('test', 'back', 'rule'),
        'cross_result': ('test', 'back', 'rule'), 'ruling_prompt': ('rule',) * 3,
        'closed': ('open_case', 'record', 'leave')}  # choice n -> the same action the ears can ask for
RULINGS = ('faithful', 'forgery', 'repair')  # in RULING's order
ACTIONS = {'open_case', 'test', 'rule', 'ask', 'argue', 'record', 'back', 'how', 'leave', 'greet'}

GREETING = ['🔨 All rise! Your Honor, a dead app awaits your judgment.']
HOW = ['🐧 McClusky, Esq., a penguin medium, brought a dead app back to life.',
       '🦉 Dr. Hoot, an owl skeptic, argues it is a fake.',
       '🔍 A court with rules and no AI tests the original and the revival side by side.',
       '👂 Talk to me in plain words. ASI-1 helps me listen, never rule.',
       '⚖️ Then you rule, Your Honor. The Bailiff has no opinion.']
ASK_RULING = ['⚖️ How do you rule, Your Honor?']
UNKNOWN = ['Your Honor, please choose 1, 2, or 3.']
SAFE = 'I can only speak to the record, Your Honor.'
FIRST = '🔨 Pick a case first, Your Honor.'
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
HOW_WORDS = {'how', 'help', 'work', 'works', 'explain'}
KEYWORDS = {  # the lobby's come from the docket
    'verdict': {1: {'argue', 'argument', 'hear', 'debate'}, 2: {'test', 'try', 'yourself'},
                3: {'rule', 'ruling', 'deliver', 'decide', 'verdict'}},
    'cross_result': {1: {'another', 'again', 'try', 'more'}, 2: {'back', 'verdict', 'return', 'cancel'},
                     3: {'rule', 'ruling', 'deliver', 'decide'}},
    'ruling_prompt': {1: {'faithful', 'genuine', 'authentic'}, 2: {'forgery', 'forged', 'fake', 'fraud'},
                      3: {'repair', 'fix', 'broken'}},
    'closed': {1: {'new', 'another', 'next'}, 2: {'record', 'see', 'show'},
               3: {'leave', 'exit', 'quit', 'bye', 'goodbye', 'adjourn', 'done'}},
    'case_error': {1: {'again', 'retry'}, 2: {'other', 'another', 'different'}, 3: HOW_WORDS},
}
KEYWORDS['cross_prompt'] = KEYWORDS['cross_result']
_UNSAFE = str.maketrans('', '', '[]{}`')


def respond(state, text, *, cases, run_case, run_cross, run_argue=None, understand=None, parses=None):
    """One chat turn -> (reply_text, new_state); state is None for a new judge and again once court adjourns.
    cases: the docket, [{app, title, about, example}] in order. run_case(app, fresh) -> the case summary (fresh:
    the judge asked for a new run). run_cross(app, text) -> {did, original, revival}; ValueError = plain words.
    run_argue(app) -> [{who, line}]: the parties argue live; without it (or if it fails) the argument on file.
    understand(stage, text, menu, facts, cases, history) -> one action, brain.understand's dict.
    parses(app, text) -> True when that app's test language takes the text as typed."""
    raw, _ = _clean(text)
    reply, new = _Court(cases, run_case, run_cross, run_argue, understand, parses).turn(state, raw)
    if new is not None and raw:
        said = [['judge', raw], ['bailiff', ' '.join(reply.split()[:40])]]
        new = {**new, 'history': (list((state or {}).get('history') or []) + said)[-HISTORY:]}
    return reply, new


class _Court:
    """One turn: the docket and the callbacks respond() was given."""

    def __init__(self, cases, run_case, run_cross, run_argue, understand, parses):
        self.cases = [c for c in cases or [] if isinstance(c, dict) and c.get('app')]
        self.run_case, self.run_cross, self.run_argue = run_case, run_cross, run_argue
        self.understand, self.parses = understand, parses or (lambda app, text: False)

    def turn(self, state, raw):
        norm = _clean(raw)[1]
        stage = (state or {}).get('stage')
        if stage not in STAGES:  # a new judge, or a state this version does not know
            stage, state = 'lobby', None
        app = (state or {}).get('app')
        if stage == 'cross_prompt' and not raw:
            return _say(self.prompt(state)), state
        menu = self.menu_only(norm, stage)
        if stage in CROSS and (stage == 'cross_prompt' or not menu) and self.parses(app, raw):
            return self.test(state, raw)  # the test language as typed: straight to the court, no model
        if stage == 'verdict' and ({'run', 'again'} <= set(norm.split()) or 'rerun' in norm.split()):
            return self.open(app, fresh=True)  # the verdict offers it when the run was reused
        if menu:  # digits and menu words: the keywords decide, the ears are never asked
            a = self.pick(stage, state, _pick(norm, self.keywords(stage)))
        else:
            a = self.hear(stage, state, raw) if raw else None
            if a is None:  # unsure, down or no ears: in a test anything else is the next test, else keywords
                a = ({'action': 'test', 'steps': raw} if stage in CROSS and raw
                     else self.pick(stage, state, _pick(norm, self.keywords(stage))))
        if a is None:
            if state is None:
                return _say(self.greeting()), {'stage': 'lobby'}
            return _say(UNKNOWN + self.choices(stage)), state
        return self.do(state, stage, a)

    def hear(self, stage, state, raw):
        """The ears' action for free text; None when they are unsure, down or broken."""
        if not self.understand:
            return None
        st = state or {}
        try:
            a = self.understand(stage, raw, [] if stage == 'cross_prompt' else self.choices(stage), st.get('summary'),
                                self.cases, st.get('history') or [])
        except Exception:  # the ears must never break the court
            return None
        act = a.get('action') if isinstance(a, dict) else None
        if act == 'choose':
            return self.pick(stage, state, a.get('choice'))
        if act not in ACTIONS:  # 'unclear', or nothing this court does
            return None
        if act == 'open_case' and a.get('app') not in {c['app'] for c in self.cases}:
            a = {**a, 'app': None}  # never a case off the docket: show the docket
        if act == 'test' and not a.get('steps') and stage in CROSS:
            a = {**a, 'steps': raw}  # the court words it, or says why it can't
        return a

    def pick(self, stage, state, n):
        """Choice n of this stage's menu as an action; None when the menu has no such choice."""
        if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= SHOWN:
            return None
        if stage == 'lobby':
            shown = self.cases[:SHOWN]
            return ({'action': 'open_case', 'app': shown[n - 1]['app']} if n <= len(shown)
                    else {'action': 'how'} if n == len(shown) + 1 else None)
        if stage == 'case_error':
            return [{'action': 'open_case', 'app': state['app']},
                    {'action': 'open_case', 'app': self.after(state['app'])}, {'action': 'how'}][n - 1]
        return {'action': ACTS[stage][n - 1], 'ruling': RULINGS[n - 1] if stage == 'ruling_prompt' else None}

    def do(self, state, stage, a):
        act, s = a['action'], (state or {}).get('summary')
        if act == 'open_case':
            if a.get('app'):  # the case already open again: the judge wants a new run
                return self.open(a['app'], fresh=a['app'] == (state or {}).get('app'))
            return _say(self.greeting()), {'stage': 'lobby'}
        if act == 'leave':
            return _say(ADJOURN), None
        if act == 'ask':  # the ears' words, every number checked against the case file by brain.py
            said = str(a['answer']).split('\n') if a.get('answer') else _from_record(s)
            menu = self.next(state)
            return _say([x for x in said if x not in menu] + menu), state or {'stage': 'lobby'}  # no echoed prompt
        if not s:  # no case open
            if act == 'how':
                return _say(HOW + self.choices('lobby')), {'stage': 'lobby'}
            return _say(self.greeting() if act == 'greet' else [FIRST, *self.choices('lobby')]), {'stage': 'lobby'}
        if act in ('how', 'greet'):
            return _say((HOW if act == 'how' else []) + self.next(state)), state
        if act == 'back':
            return _say(_back(s)), {**state, 'stage': 'verdict'}
        if act == 'argue':
            return _say(_argue(_heard(s, state['app'], self.run_argue))), {**state, 'stage': 'verdict'}
        if act == 'record':
            return _say(_record(s) + (CLOSED if stage == 'closed' else self.next(state))), state
        if act == 'test':
            if a.get('steps'):
                return self.test(state, a['steps'])
            return _say(self.prompt(state)), {**state, 'stage': 'cross_prompt'}
        n = RULINGS.index(a['ruling']) + 1 if a.get('ruling') in RULINGS else 0  # rule
        if n:  # the evidence check in _rule is the court's, not the ears'
            return _say(_rule(s, n)), {**state, 'stage': 'closed'}
        return _say(ASK_RULING + RULING), {**state, 'stage': 'ruling_prompt'}

    # --- the docket -----------------------------------------------------------------------------------------
    def row(self, app):
        return next((c for c in self.cases if c['app'] == app), {})

    def after(self, app):
        """'Other case': the next case on the docket."""
        apps = [c['app'] for c in self.cases] or [app]
        return apps[(apps.index(app) + 1) % len(apps)] if app in apps else apps[0]

    def choices(self, stage):
        if stage != 'lobby':
            return CHOICES[stage]
        shown = [f"{n}) The case of {c.get('title') or c['app']}" for n, c in enumerate(self.cases[:SHOWN], 1)]
        return shown + ([f'{len(shown) + 1}) {HOW_ITEM}'] if len(shown) < SHOWN else [])

    def greeting(self):
        return GREETING + [f"📜 {c['about']}" for c in self.cases[:SHOWN] if c.get('about')] + self.choices('lobby')

    def keywords(self, stage):
        """Choice -> its words. In the lobby: each case's title words and id, minus words two choices share."""
        if stage != 'lobby':
            return KEYWORDS[stage]
        picks = {n: _words(f"{c.get('title') or ''} {c['app']}") for n, c in enumerate(self.cases[:SHOWN], 1)}
        if len(picks) < SHOWN:
            picks[len(picks) + 1] = HOW_WORDS
        seen = Counter(w for ws in picks.values() for w in ws)
        return {n: {w for w in ws if seen[w] == 1} - FILLER - set(NUMBERS) for n, ws in picks.items()}

    def menu_only(self, norm, stage):
        """The words are only a menu choice (numbers, keywords, the menu's own words, filler), not a test like
        "1 / 0 =" or "add eggs" and not a sentence for the ears."""
        words = set(norm.split())
        shown = _words(' '.join(re.sub(r'^\d\) ', '', line) for line in self.choices(stage)))
        return bool(words) and words <= FILLER | set(NUMBERS) | shown | set().union(*self.keywords(stage).values())

    def next(self, state):
        """The judge's next step, as the stage shows it."""
        stage = (state or {}).get('stage', 'lobby')
        if stage == 'cross_prompt':
            return self.prompt(state)
        if stage == 'ruling_prompt':
            return ASK_RULING + RULING
        return ['Your Honor, what now?', *self.choices(stage)]

    # --- the court ------------------------------------------------------------------------------------------
    def open(self, app, fresh=False):
        try:
            s = self.run_case(app, fresh)
        except Exception as e:  # by contract the pipeline explains its failures in plain words
            return self.oops(app, _reason(e))
        try:  # state must survive the agent's storage
            s = json.loads(json.dumps({**s, 'title': self.row(app).get('title') or s.get('title') or app}))
            lines = _verdict(s)
            _argue(s)
            _record(s)  # fail now, not mid-case, if the case file has gaps
        except Exception:
            return self.oops(app, 'The case file is incomplete.')
        return _say(lines), {'stage': 'verdict', 'app': app, 'summary': s}

    def oops(self, app, reason):
        lines = [f'🔨 The court could not open that case. {reason}', 'Your Honor, what now?', *OOPS]
        return _say(lines), {'stage': 'case_error', 'app': app}

    def prompt(self, state, first=TRY_IT):
        example = self.row(state['app']).get('example')
        return [first, 'Type "back" to return to the verdict.',
                f'Your Honor, type something to try, like "{example}".' if example else
                'Your Honor, type something to try.']

    def test(self, state, steps):
        try:
            r = self.run_cross(state['app'], steps)
            r = {k: str(r[k]) for k in ('did', 'original', 'revival')}
        except ValueError as e:  # the court cannot map this action: say why, let the judge retry
            return _say(self.prompt(state, f'🔍 {e}')), {**state, 'stage': 'cross_prompt'}
        except Exception:  # court down or a malformed answer: same retry, plain words
            return _say(self.prompt(state, '🔍 The court could not run that test just now.')), {
                **state, 'stage': 'cross_prompt'}
        same = r['original'].strip() == r['revival'].strip()
        s = state['summary']
        if not same and all(d['did'] != r['did'] for d in s['differences']):
            s = {**s, 'differences': s['differences'] + [r]}  # what the judge finds is evidence too
        lines = [f"🔍 Tried on both apps: {r['did']}",
                 f"Original: {_seen(r['original'])} · Revival: {_seen(r['revival'])} {'✅' if same else '❌'}",
                 SAME if same else DIFFERENT, *CROSSED]
        return _say(lines), {**state, 'stage': 'cross_result', 'summary': s}


def _clean(text):
    """The text without leading @mentions, plus a lowercase, punctuation-free copy for matching."""
    words = str(text or '').split()
    while words and words[0].startswith('@'):
        words.pop(0)
    raw = ' '.join(words)
    return raw, ' '.join(re.sub(r'[^\w\s]', '', raw.lower()).split())


def _words(text):
    return set(_clean(text)[1].split())


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


def _heard(s, app, run_argue):
    """The summary with the argument heard live from the parties, else as it is (argument on file)."""
    try:
        said = [{'who': str(a['who']), 'line': str(a['line'])} for a in run_argue(app)] if run_argue else []
    except Exception:  # a party did not answer: the argument on file still stands
        said = []
    return {**s, 'argument': said} if said else s


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
    ago = s.get('ran_minutes_ago')  # the Bailiff reused a recent run: say so, honestly
    again = [] if ago is None else [f"🕰️ The court ran this case {'moments' if ago < 1 else _count(ago, 'minute')} "
                                    'ago. Say "run it again" for a fresh trial.']
    return [f"⚖️ The case of {s['title']}: is the revival the same app as the dead original?", *again,
            f"🐧 McClusky swore {s['claims']} claims. 🦉 Hoot attacked with {s['attacks']}.",
            f'🔍 {held}{busted}. The court {found} between the apps.',
            *evidence[:2], 'Your Honor, what now?', *VERDICT]


def _from_record(s):
    """No usable answer from the ears: the record's own lines, so a question never meets a dead end."""
    if not s:
        return [SAFE]
    return ['From the record, Your Honor:',
            f"🔍 {s['locked']} of {s['claims']} claims held. {_count(len(s['differences']), 'difference')} between the apps.",
            *[f'🔨 Struck: {x}' for x in s['struck_examples'][:1]], *[_exhibit('❌', d) for d in s['differences'][:1]]]


def _exhibit(mark, r):
    return f"{mark} {r['did']} → Original: {_seen(r['original'])} · Revival: {_seen(r['revival'])}"


def _seen(shown):
    """What a build showed; an empty page or list reads as nothing, not as a blank."""
    return str(shown).strip() or 'nothing'


def _count(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def _argue(s):
    said = [f"{SPEAKERS[a['who']]} {a['line']}" for a in s['argument'] if a.get('who') in SPEAKERS][:4]
    return (said or ['🔨 Bailiff: Both sides rest. The Bailiff has no opinion.']) + ['Your Honor, what now?', *VERDICT]


def _back(s):
    return [f"⚖️ Back to the case of {s['title']}.", 'Your Honor, what now?', *VERDICT]


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
    """The record, without a menu: the caller adds the stage's."""
    start, end = s['credibility'][0], s['credibility'][-1]
    moved = (f'rose from {start} to {end}' if end > start
             else f'fell from {start} to {end}' if end < start else f'stayed at {end}')
    n = len(s['differences'])
    found = f"{_count(n, 'difference')} found." if n else 'No differences found.'
    sealed = ('🔨 Every step is in a tamper-proof record. Nobody can rewrite it.' if s['ledger']['intact']
              else '🔨 Warning: this record failed its tamper check.')
    return [f"📜 The record, Your Honor: {s['locked']} claims held up, {s['struck']} proved false.",
            f"🔍 Hoot attacked {s['attacks']} times. The court took {s['seconds']} seconds. {found}",
            f"⚖️ Match score: {s['fidelity']} out of 100, how often the copy acted like the original.",
            f"🐧 McClusky's credibility {moved}.", sealed]


def _say(lines):
    """Final check on every reply: no brackets, and no line over MAX_WORDS (long lines are split, not cut)."""
    out = []
    for line in lines:
        words = line.translate(_UNSAFE).split()
        while len(words) > MAX_WORDS:  # break after a sentence or clause end when one is near, so "0 of 36" stays whole
            cut = next((i for i in range(MAX_WORDS, MAX_WORDS // 2, -1) if words[i - 1][-1] in '.,;:!?—'), MAX_WORDS)
            out.append(' '.join(words[:cut]))
            words = words[cut:]
        out += [' '.join(words)] if words else []
    picks = [line for line in out if re.match(r'\d\) ', line)]  # ASI:One renders Markdown: single newlines collapse
    return '\n\n'.join([line for line in out if line not in picks] + (['\n'.join(picks)] if picks else []))
