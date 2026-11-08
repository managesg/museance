"""Courtroom flow tests: an injected docket, the two summaries the court measured today, and a fake brain."""
import json
import re

import pytest

from agents.mesh.courtroom import CLOSED, CROSSED, HOW, RULING, SAFE, VERDICT, respond

TODO = {
    'app': 'todo', 'title': 'Todo',
    'claims': 16, 'locked': 15, 'struck': 1, 'unsworn': 0, 'fabricated': 0,
    'attacks': 20, 'seconds': 31, 'fidelity': 100, 'differences': [],
    'examples': [{'did': 'Typed "Buy milk", pressed Enter', 'original': '1 item: Buy milk',
                  'revival': '1 item: Buy milk'}],
    'struck_examples': ['"An empty task can be created" was a forum rumor. The original refuses.'],
    'credibility': [1000, 930],
    'argument': [
        {'who': 'hoot', 'line': 'Hoo. Sixteen claims, one rumor. I sealed my attacks before reading any.'},
        {'who': 'mcclusky', 'line': 'Fifteen held, Your Honor. The spirits were nearly flawless.'},
        {'who': 'bailiff', 'line': 'Fifteen locked, one struck. The Bailiff has no opinion.'}],
    'ledger': {'entries': 65, 'intact': True},
}
CALC = {
    'app': 'app1',
    'claims': 11, 'locked': 11, 'struck': 0, 'unsworn': 0, 'fabricated': 0,
    'attacks': 16, 'seconds': 12, 'fidelity': 93,
    'differences': [{'did': 'Pressed 7 ÷ 8 =', 'original': '0.87', 'revival': '0.88'},
                    {'did': 'Pressed 1 ÷ 0 =', 'original': 'Error', 'revival': 'Infinity'}],
    'examples': [{'did': 'Pressed 7 × 8 =', 'original': '56', 'revival': '56'}],
    'struck_examples': [],
    'credibility': [1000, 1244],
    'argument': [
        {'who': 'hoot', 'line': 'Hoo. Seven divided by eight. The original truncates. This forgery rounds.'},
        {'who': 'mcclusky', 'line': 'Objection! Every claim I swore was true. The revival betrayed me.'},
        {'who': 'bailiff', 'line': 'Eleven locked. Two differences found. The Bailiff has no model.'}],
    'ledger': {'entries': 65, 'intact': True},
}
SUMMARIES = {s['app']: s for s in (TODO, CALC)}
DOCKET = [  # docket.cases() rows; the docket's titles win over a summary's
    {'app': 'todo', 'title': 'Todo', 'about': 'A to-do list from 2016, its repository archived.', 'example': 'add milk'},
    {'app': 'app1', 'title': 'the Calculator', 'about': 'A pocket calculator written today for lane testing.',
     'example': '7 / 8 ='}]
LOBBY = ['1) The case of Todo', '2) The case of the Calculator', '3) How this court works']
ABOUTS = ['📜 A to-do list from 2016, its repository archived.', '📜 A pocket calculator written today for lane testing.']
GREETING = '🔨 All rise! Your Honor, a dead app awaits your judgment.'
PLEASE = 'Your Honor, please choose 1, 2, or 3.'
KEYS = ('action', 'choice', 'app', 'steps', 'ruling', 'topic', 'answer')  # brain.KEYS


def fake_run_case(app_id, fresh=False):
    return SUMMARIES[app_id]


def fake_run_cross(app_id, action):
    """Stand-in for the real court: Todo adds an item; the Calculator replays a press measured today."""
    if app_id == 'todo':
        m = re.fullmatch(r'add (.+)', action.strip(), re.I)
        if not m:
            raise ValueError('In this replay the court can only add items to the list.')
        item = m.group(1)
        return {'did': f'Typed "{item}", pressed Enter', 'original': f'1 item: {item}', 'revival': f'1 item: {item}'}
    did = 'Pressed ' + ' '.join(re.findall(r'\d+|[+\-×÷=]', action.replace('/', '÷').replace('*', '×')))
    for row in SUMMARIES[app_id]['differences'] + SUMMARIES[app_id]['examples']:
        if row['did'] == did:
            return row
    raise ValueError('The court has no recording of those presses today.')


def fake_parses(app_id, text):
    """Stand-in for the court's parser: Todo takes "add <item>", the Calculator its keys."""
    return bool(re.fullmatch(r'add .+' if app_id == 'todo' else r'[\d\s+*/×÷=.]+', text.strip(), re.I))


class Brain:
    """A fake brain.understand: an action per exact judge text, 'unclear' otherwise; every call is kept."""

    def __init__(self, said=None, fail=False):
        self.said, self.fail, self.calls = said or {}, fail, []

    def __call__(self, stage, text, menu, facts, cases, history):
        self.calls.append({'stage': stage, 'text': text, 'menu': menu, 'facts': facts, 'cases': cases,
                           'history': history})
        if self.fail:
            raise TimeoutError('ASI-1 is slow today')
        return {**dict.fromkeys(KEYS), 'action': 'unclear', **self.said.get(text, {})}


def nonblank(reply):
    return [line for line in reply.split('\n') if line]


def check(reply):
    """Product rules every reply obeys."""
    lines = nonblank(reply)
    assert sum(bool(re.match(r'\d+\)', line)) for line in lines) <= 3, reply
    assert all(len(line.split()) <= 20 for line in lines), reply
    assert not set('[]{}') & set(reply), reply
    assert 'seance' not in reply.lower(), reply
    assert 'Your Honor' in reply, reply
    last = lines[-1]  # the next step is always obvious
    assert re.match(r'\d\) ', last) or last.startswith(('Your Honor, type something to try', 'Type "all rise"')), reply


def bare(state):
    """The state without the ears' chat history."""
    return {k: v for k, v in state.items() if k != 'history'} if state else state


def turn(state, text, run_case=fake_run_case, run_cross=fake_run_cross, cases=DOCKET, **kw):
    reply, state = respond(state, text, cases=cases, run_case=run_case, run_cross=run_cross, parses=fake_parses,
                           **kw)
    check(reply)
    json.dumps(state)
    return reply, state


def play(*texts, state=None, **fakes):
    replies = []
    for text in texts:
        reply, state = turn(state, text, **fakes)
        replies.append(reply)
    return replies, state


def body(reply):
    """The lines above the numbered choices."""
    return [line for line in nonblank(reply) if not re.match(r'\d\) ', line)]


# --- the flow, keyword parser only --------------------------------------------------------------------------------
def test_todo_is_an_honest_win():
    (lobby, how, verdict, argue, prompt, crossed, ask, ruled, record, bye), state = play(
        '@thebailiff hello', '3', '1', '1', '2', 'add milk', '3', '1', '2', '3')
    assert nonblank(lobby) == [GREETING, *ABOUTS, *LOBBY]
    assert body(how) == HOW and how.endswith('\n'.join(LOBBY))
    assert nonblank(verdict)[:5] == [
        '⚖️ The case of Todo: is the revival the same app as the dead original?',
        '🐧 McClusky swore 16 claims. 🦉 Hoot attacked with 20.',
        '🔍 15 of 16 claims held, 1 busted. The court found no differences between the apps.',
        '✅ Typed "Buy milk", pressed Enter → Original: 1 item: Buy milk · Revival: 1 item: Buy milk',
        '🔨 Struck from the record: "An empty task can be created" was a forum rumor. The original refuses.']
    assert verdict.endswith('Your Honor, what now?\n\n' + '\n'.join(VERDICT))
    assert body(argue) == [
        '🦉 Hoot: Hoo. Sixteen claims, one rumor. I sealed my attacks before reading any.',
        '🐧 McClusky: Fifteen held, Your Honor. The spirits were nearly flawless.',
        '🔨 Bailiff: Fifteen locked, one struck. The Bailiff has no opinion.',
        'Your Honor, what now?']
    assert prompt.endswith('Your Honor, type something to try, like "add milk".')
    assert '🔍 Tried on both apps: Typed "milk", pressed Enter\n\nOriginal: 1 item: milk · Revival: 1 item: milk ✅' in crossed
    assert ask == '⚖️ How do you rule, Your Honor?\n\n1) Faithful\n2) Forgery\n3) Needs repair'
    assert ruled.startswith('⚖️ Your Honor rules: Faithful.\n\n✅ The evidence agrees with Your Honor.')
    assert '🔨 Case closed.' in ruled
    assert len(body(record)) <= 5 and record.endswith('\n'.join(CLOSED))
    for fact in ('15 claims held up, 1 proved false', 'No differences found', 'Match score: 100 out of 100',
                 'fell from 1000 to 930', 'Every step is in a tamper-proof record. Nobody can rewrite it.'):
        assert fact in record
    assert bye.startswith('🔨 Court adjourned. Thank you, Your Honor.') and state is None


def test_calculator_is_an_exposed_forgery():
    (_, verdict, argue, prompt, crossed, _, ruled, record, _), state = play(
        '@agent1qw47abcdef hi', '2', '1', '2', '7 / 8 =', '3', '2', '2', '3')
    assert nonblank(verdict)[:5] == [
        '⚖️ The case of the Calculator: is the revival the same app as the dead original?',
        '🐧 McClusky swore 11 claims. 🦉 Hoot attacked with 16.',
        '🔍 All 11 claims held. The court found 2 differences between the apps.',
        '❌ Pressed 7 ÷ 8 = → Original: 0.87 · Revival: 0.88',
        '❌ Pressed 1 ÷ 0 = → Original: Error · Revival: Infinity']
    assert '🦉 Hoot: Hoo. Seven divided by eight. The original truncates. This forgery rounds.' in argue
    assert prompt.endswith('Your Honor, type something to try, like "7 / 8 =".')
    assert '🔍 Tried on both apps: Pressed 7 ÷ 8 =\n\nOriginal: 0.87 · Revival: 0.88 ❌' in crossed
    assert ruled.startswith('⚖️ Your Honor rules: Forgery.\n\n✅ The evidence agrees with Your Honor.')
    for fact in ('11 claims held up, 0 proved false', '2 differences found', 'Match score: 93 out of 100',
                 'rose from 1000 to 1244'):
        assert fact in record
    assert state is None


@pytest.mark.parametrize('case, ruling, objection', [
    ('1', '1', None),
    ('1', 'forgery', '0 differences in 20 attacks'),
    ('1', 'needs repair', '0 differences in 20 attacks'),
    ('2', 'faithful', '2 differences between the apps'),
    ('2', '2', None),
    ('2', 'third', None),
])
def test_ruling_follows_the_evidence(case, ruling, objection):
    (*_, ruled), state = play(case, 'rule', ruling)
    if objection:
        assert f'❌ Objection, Your Honor! The evidence says {objection}.' in ruled
    else:
        assert '✅ The evidence agrees with Your Honor.' in ruled
    assert state['stage'] == 'closed'


@pytest.mark.parametrize('text, title', [
    ('one', 'Todo'), ('First!', 'Todo'), ('the to-do one', 'Todo'),
    ('Two.', 'the Calculator'), ('the second one', 'the Calculator'), ('calculator please', 'the Calculator')])
def test_lobby_understands_words(text, title):
    reply, state = turn({'stage': 'lobby'}, text)
    assert reply.startswith(f'⚖️ The case of {title}: ') and state['stage'] == 'verdict'


def test_mentions_are_stripped():
    assert turn(None, '@agent1qw47xyz 1')[0].startswith('⚖️ The case of Todo: ')
    assert turn({'stage': 'lobby'}, '@thebailiff 2')[0].startswith('⚖️ The case of the Calculator: ')
    _, state = play('2', '2')
    assert '🔍 Tried on both apps: Pressed 7 ÷ 8 =' in turn(state, '@thebailiff 7 / 8 =')[0]


def test_unknown_input_repeats_the_choices():
    greeting, lobby = turn(None, 'what is going on')
    assert nonblank(greeting) == [GREETING, *ABOUTS, *LOBBY]
    reply, same = turn(lobby, 'banana')
    assert nonblank(reply) == [PLEASE] + LOBBY and bare(same) == bare(lobby)
    _, verdict = turn(lobby, '1')
    for text in ('maybe later', '1 or 2', '@thebailiff', 'no'):
        reply, same = turn(verdict, text)
        assert nonblank(reply) == [PLEASE] + VERDICT and bare(same) == bare(verdict)
    _, ask = turn(verdict, '3')
    reply, same = turn(ask, 'not faithful')
    assert reply.startswith(PLEASE) and bare(same) == bare(ask)


def test_case_error_offers_a_way_out():
    asked = []

    def broken(app_id, fresh=False):
        asked.append((app_id, fresh))
        raise Exception('The original app would not start.')
    reply, state = turn(None, '1', run_case=broken)
    assert nonblank(reply) == ['🔨 The court could not open that case. The original app would not start.',
                               'Your Honor, what now?', '1) Try again', '2) Other case', '3) How this court works']
    assert bare(state) == {'stage': 'case_error', 'app': 'todo'}
    turn(state, 'try again', run_case=broken)
    assert asked == [('todo', False), ('todo', True)]  # trying again is a fresh run
    assert turn(state, 'try again')[0].startswith('⚖️ The case of Todo: ')
    assert turn(state, '2')[0].startswith('⚖️ The case of the Calculator: ')  # the next case on the docket
    reply, lobby = turn(state, '3')
    assert reply.endswith('\n'.join(LOBBY)) and bare(lobby) == {'stage': 'lobby'}
    reply, state = turn(None, '2', run_case=lambda app_id, fresh: {'title': 'Half a case'})
    assert 'The case file is incomplete.' in reply and state['stage'] == 'case_error'


def test_cross_errors_keep_the_judge_testing():
    def picky(app_id, action):
        raise ValueError('That calculator has no square root key.')
    _, state = play('2', '2')
    reply, after = turn(state, 'sqrt 2', run_cross=picky)
    assert reply.startswith('🔍 That calculator has no square root key.')
    assert reply.endswith('like "7 / 8 =".') and after['stage'] == 'cross_prompt'
    reply, after = turn(state, '7 / 8 =', run_cross=lambda app_id, action: 1 / 0)
    assert reply.startswith('🔍 The court could not run that test just now.') and after['stage'] == 'cross_prompt'


@pytest.mark.parametrize('word', ['back', 'Cancel!', '@thebailiff go back'])
def test_back_leaves_the_test(word):
    _, state = play('1', '2')
    reply, after = turn(state, word)
    assert reply.endswith('\n'.join(VERDICT)) and after['stage'] == 'verdict'


def test_after_a_test_the_judge_moves_on():
    _, state = play('1', '2', 'add milk')
    assert state['stage'] == 'cross_result'
    assert turn(state, 'try another')[1]['stage'] == 'cross_prompt'
    assert turn(state, 'back to the verdict')[1]['stage'] == 'verdict'
    assert turn(state, '3')[1]['stage'] == 'ruling_prompt'


def test_a_difference_the_judge_finds_is_evidence():
    def odd(app_id, action):
        return {'did': 'Typed "eggs", pressed Enter', 'original': '1 item: eggs', 'revival': '0 items'}
    (_, _, crossed), state = play('1', '2', 'add eggs', run_cross=odd)
    assert 'Original: 1 item: eggs · Revival: 0 items ❌' in crossed
    (_, ruled, record), _ = play('3', '1', '2', state=state)
    assert '❌ Objection, Your Honor! The evidence says 1 difference between the apps.' in ruled
    assert '1 difference found' in record


def test_new_case_returns_to_the_lobby():
    (*_, lobby), state = play('1', '3', '1', 'new case')
    assert nonblank(lobby) == [GREETING, *ABOUTS, *LOBBY] and bare(state) == {'stage': 'lobby'}


def test_outside_text_still_obeys_the_rules():
    wordy = dict(TODO, argument=[{'who': 'hoot', 'line': ' '.join(['hoo'] * 45)}],
                 examples=[{'did': 'Typed [x]', 'original': '[]', 'revival': '{}'}])
    (verdict, argue), _ = play('1', '1', run_case=lambda app_id, fresh: wordy,
                               cases=[dict(DOCKET[0], title='{Todo}')])
    assert verdict.startswith('⚖️ The case of Todo: ')
    assert argue.count('hoo') == 45  # split across lines, not cut


def test_long_lines_break_at_a_clause_and_blanks_read_as_nothing():
    said = [{'who': 'hoot', 'line': 'McClusky, your oath died at 89% with 198 credibility while the original showed '
                                    'nothing — even 0 of 36 differences will not save it.'}]
    _, state = play('1')
    reply, _ = respond(state, '1', cases=DOCKET, run_case=fake_run_case, run_cross=fake_run_cross,
                       run_argue=lambda app: said)
    assert body(reply)[:2] == ['🦉 Hoot: McClusky, your oath died at 89% with 198 credibility while the original '
                               'showed nothing —', 'even 0 of 36 differences will not save it.']
    _, prompt = play('1', '2')
    blank = turn(prompt, 'add nothing', run_cross=lambda app, steps: {'did': 'add', 'original': '', 'revival': ' '})[0]
    assert 'Original: nothing · Revival: nothing ✅' in blank


def test_lines_are_paragraphs_and_choices_a_list():
    """ASI:One renders Markdown: one blank line between thoughts, the three choices together."""
    reply, _ = turn(None, 'hello')
    assert reply == '\n\n'.join([GREETING, *ABOUTS]) + '\n\n' + '\n'.join(LOBBY)


def test_they_argue_live_when_the_parties_answer():
    _, state = play('1')
    live = [{'who': 'hoot', 'line': 'Hoo. One perjury.'}, {'who': 'mcclusky', 'line': 'Fifteen held!'},
            {'who': 'hoot', 'line': 'Still one.'}]
    heard = []
    reply, same = respond(state, '1', cases=DOCKET, run_case=fake_run_case, run_cross=fake_run_cross,
                          run_argue=lambda app: heard.append(app) or live)
    assert body(reply)[:3] == ['🦉 Hoot: Hoo. One perjury.', '🐧 McClusky: Fifteen held!', '🦉 Hoot: Still one.']
    assert bare(same) == bare(state) and heard == ['todo']

    def down(app):
        raise TimeoutError('Dr. Hoot did not answer')
    reply, _ = respond(state, '1', cases=DOCKET, run_case=fake_run_case, run_cross=fake_run_cross, run_argue=down)
    assert body(reply)[0].startswith('🦉 Hoot:')  # the argument on file


def test_free_text_ruling_needs_one_clear_choice():
    _, state = play('1', '3')
    reply, after = turn(state, "Wait a second, it's faithful")  # keyword faithful wins only when nothing contradicts
    assert 'Faithful' in reply and after['stage'] == 'closed'


@pytest.mark.parametrize('text', ["it doesn't look faithful", '1 forgery', 'hmm, tough one', 'that one'])
def test_contradictions_ask_again(text):
    _, state = play('1', '3')
    reply, same = turn(state, text)
    assert body(reply) == [PLEASE] and bare(same) == bare(state)


@pytest.mark.parametrize('text', ['the other one', 'which one should I pick?'])
def test_the_lobby_never_guesses_a_case(text):
    reply, state = turn(None, text)
    assert bare(state) == {'stage': 'lobby'} and 'The case of' not in body(reply)[0]


def test_a_calculator_test_after_a_test_is_a_test():
    _, state = play('2', '2', '7 / 8 =')
    assert state['stage'] == 'cross_result'
    reply, after = turn(state, '1 / 0 =')  # not choice 1: the judge is testing again
    assert body(reply)[0].startswith('🔍') and after['stage'] in ('cross_result', 'cross_prompt')


@pytest.mark.parametrize('text, stage', [('3', 'ruling_prompt'), ('rule', 'ruling_prompt'), ('2', 'verdict')])
def test_menu_words_leave_the_todo_test_prompt(text, stage):
    _, state = play('1', '2')
    assert state['stage'] == 'cross_prompt'
    assert turn(state, text)[1]['stage'] == stage


def test_a_digit_is_a_calculator_test():
    _, state = play('2', '2')
    reply, after = turn(state, '3')  # the Calculator's parser takes 3; Todo's does not (above)
    assert body(reply)[0].startswith('🔍') and after['stage'] in ('cross_prompt', 'cross_result')


# --- the docket ---------------------------------------------------------------------------------------------------
def test_the_lobby_is_the_docket():
    one = [{'app': 'x9', 'title': 'the Dial', 'about': '', 'example': ''}]
    reply, state = turn(None, 'hello', cases=one)
    assert nonblank(reply)[-2:] == ['1) The case of the Dial', '2) How this court works']
    assert turn(state, 'dial', cases=one, run_case=lambda app, fresh: dict(TODO, app=app))[0].startswith(
        '⚖️ The case of the Dial: ')
    four = DOCKET + [{'app': f'z{i}', 'title': f'the Z{i} App', 'about': 'Z.', 'example': 'z'} for i in (1, 2)]
    reply, _ = turn(None, 'hello', cases=four)
    assert nonblank(reply)[-3:] == [*LOBBY[:2], '3) The case of the Z1 App']  # never more than 3 choices
    reply, _ = turn({'stage': 'lobby'}, 'z1', cases=four, run_case=lambda app, fresh: dict(TODO, app=app))
    assert reply.startswith('⚖️ The case of the Z1 App: ')
    reply, state = turn(None, 'hello', cases=[])
    assert nonblank(reply)[-1] == '1) How this court works'


def test_shared_title_words_name_no_case():
    apps = [{'app': 'a', 'title': 'the Todo App', 'about': '', 'example': ''},
            {'app': 'b', 'title': 'the Notes App', 'about': '', 'example': ''}]
    assert turn({'stage': 'lobby'}, 'the app', cases=apps)[0].startswith(PLEASE)
    assert turn({'stage': 'lobby'}, 'notes app', cases=apps, run_case=lambda app, fresh: dict(TODO, app=app))[
        0].startswith('⚖️ The case of the Notes App: ')


def test_the_test_prompt_shows_the_dockets_example():
    plain = [dict(DOCKET[0], example='')]
    _, state = play('1', '2', cases=plain)
    assert nonblank(turn(state, '', cases=plain)[0])[-1] == 'Your Honor, type something to try.'


# --- the ears: one test per brain action ------------------------------------------------------------------------
def test_digits_and_menu_words_never_reach_the_ears():
    ears = Brain(fail=True)
    play('1', 'hear them argue', '2', 'add milk', 'try another', 'back', 'deliver your ruling', 'faithful', '2', '3',
         understand=ears)
    play('2', '2', '3', understand=ears)  # a calculator key is a test, straight to the court
    assert ears.calls == []


def test_choose_is_the_menu_number():
    ears = Brain({'the last one': {'action': 'choose', 'choice': 3}, 'the fourth': {'action': 'choose', 'choice': 4}})
    _, state = play('1')
    reply, after = turn(state, 'the last one', understand=ears)
    assert reply.startswith('⚖️ How do you rule, Your Honor?') and after['stage'] == 'ruling_prompt'
    assert ears.calls[0]['menu'] == VERDICT and ears.calls[0]['facts']['app'] == 'todo'
    assert ears.calls[0]['cases'] == DOCKET
    assert turn(state, 'the fourth', understand=ears)[0].startswith(PLEASE)


def test_open_case_from_any_stage():
    asked = []

    def run(app, fresh=False):
        asked.append((app, fresh))
        return SUMMARIES[app]
    ears = Brain({'is the calculator legit?': {'action': 'open_case', 'app': 'app1'},
                  'now the other app': {'action': 'open_case', 'app': 'app1'},
                  'open the todo case': {'action': 'open_case', 'app': 'todo'},
                  'show me the docket': {'action': 'open_case', 'app': None},
                  'open pong': {'action': 'open_case', 'app': 'pong'}})
    reply, _ = turn(None, 'is the calculator legit?', run_case=run, understand=ears)
    assert reply.startswith('⚖️ The case of the Calculator: ') and ears.calls[0]['stage'] == 'lobby'
    _, state = play('1', '2', run_case=run)
    reply, after = turn(state, 'now the other app', run_case=run, understand=ears)
    assert reply.startswith('⚖️ The case of the Calculator: ') and after['app'] == 'app1'
    turn(state, 'open the todo case', run_case=run, understand=ears)
    assert asked == [('app1', False), ('todo', False), ('app1', False), ('todo', True)]  # same case: a new run
    for text in ('show me the docket', 'open pong'):  # never a case off the docket
        reply, after = turn(state, text, understand=ears)
        assert nonblank(reply)[-3:] == LOBBY and bare(after) == {'stage': 'lobby'}


def test_test_runs_now_or_says_why_not():
    tried = []

    def court(app, steps):
        tried.append((app, steps))
        if steps == 'what about 8 minus 1':
            raise ValueError('No minus key exists on this keypad, Your Honor.')
        return fake_run_cross(app, steps)
    ears = Brain({'what is 7 divided by 8': {'action': 'test', 'steps': '7/8='},
                  'let me poke at it': {'action': 'test', 'steps': None},
                  'what about 8 minus 1': {'action': 'test', 'steps': None}})
    _, state = play('2')
    reply, after = turn(state, 'what is 7 divided by 8', run_cross=court, understand=ears)  # from the verdict
    assert body(reply)[:2] == ['🔍 Tried on both apps: Pressed 7 ÷ 8 =', 'Original: 0.87 · Revival: 0.88 ❌']
    assert after['stage'] == 'cross_result' and tried == [('app1', '7/8=')]
    reply, after = turn(state, 'let me poke at it', run_cross=court, understand=ears)
    assert reply.endswith('like "7 / 8 =".') and after['stage'] == 'cross_prompt'
    reply, still = turn(after, 'what about 8 minus 1', run_cross=court, understand=ears)  # steps None: the court
    assert reply.startswith('🔍 No minus key exists on this keypad, Your Honor.') and still['stage'] == 'cross_prompt'
    reply, lobby = turn(None, 'what is 7 divided by 8', understand=ears)
    assert body(reply)[0] == '🔨 Pick a case first, Your Honor.' and bare(lobby) == {'stage': 'lobby'}


def test_rule_closes_the_case_and_the_evidence_still_checks():
    ears = Brain({"it's legit": {'action': 'rule', 'ruling': 'faithful'},
                  'i am ready to decide': {'action': 'rule', 'ruling': None}})
    _, state = play('2')
    reply, after = turn(state, "it's legit", understand=ears)
    assert reply.startswith('⚖️ Your Honor rules: Faithful.\n\n❌ Objection, Your Honor! The evidence says 2 '
                            'differences between the apps.') and after['stage'] == 'closed'
    reply, after = turn(state, 'i am ready to decide', understand=ears)
    assert nonblank(reply) == ['⚖️ How do you rule, Your Honor?', *RULING] and after['stage'] == 'ruling_prompt'
    _, prompt = play('2', '2')
    assert turn(prompt, "it's legit", understand=ears)[1]['stage'] == 'closed'  # from the test prompt too


def test_ask_answers_then_shows_the_same_menu():
    ears = Brain({'why did he lose points?': {'action': 'ask', 'answer': 'One claim was struck, Your Honor.\n'
                                                                          'Credibility fell from 1000 to 930.'},
                  'what is your favorite color?': {'action': 'ask', 'answer': None}})
    _, state = play('1')
    reply, after = turn(state, 'why did he lose points?', understand=ears)
    assert nonblank(reply) == ['One claim was struck, Your Honor.', 'Credibility fell from 1000 to 930.',
                               'Your Honor, what now?', *VERDICT]
    assert bare(after) == bare(state)
    reply, _ = turn(state, 'what is your favorite color?', understand=ears)
    assert body(reply)[0] == SAFE
    _, prompt = play('1', '2')
    reply, after = turn(prompt, 'what is your favorite color?', understand=ears)
    assert reply.endswith('like "add milk".') and after['stage'] == 'cross_prompt'


def test_argue_hears_them_from_any_stage():
    ears = Brain({'let them fight': {'action': 'argue', 'topic': 'the struck claim'}})
    _, state = play('1', '2', 'add milk')
    reply, after = turn(state, 'let them fight', understand=ears)
    assert body(reply)[0].startswith('🦉 Hoot: Hoo. Sixteen claims') and after['stage'] == 'verdict'


def test_record_back_how_greet_and_leave_are_their_menu_choices():
    ears = Brain({'show me the ledger': {'action': 'record'}, 'enough testing': {'action': 'back'},
                  'what is this place': {'action': 'how'}, 'hello there': {'action': 'greet'},
                  'i am out': {'action': 'leave'}})
    _, verdict = play('1')
    reply, after = turn(verdict, 'show me the ledger', understand=ears)
    assert '⚖️ Match score: 100 out of 100' in reply and reply.endswith('\n'.join(VERDICT))
    assert after['stage'] == 'verdict'
    _, closed = play('1', '3', '1')
    assert turn(closed, 'show me the ledger', understand=ears)[0].endswith('\n'.join(CLOSED))
    _, crossed = play('1', '2', 'add milk')
    reply, after = turn(crossed, 'enough testing', understand=ears)
    assert reply.startswith('⚖️ Back to the case of Todo.') and after['stage'] == 'verdict'
    reply, after = turn(crossed, 'what is this place', understand=ears)
    assert body(reply)[:5] == HOW and reply.endswith('\n'.join(CROSSED)) and after['stage'] == 'cross_result'
    reply, lobby = turn(None, 'what is this place', understand=ears)
    assert reply.endswith('\n'.join(LOBBY)) and bare(lobby) == {'stage': 'lobby'}
    assert nonblank(turn(None, 'hello there', understand=ears)[0])[0] == GREETING
    assert nonblank(turn(verdict, 'hello there', understand=ears)[0]) == ['Your Honor, what now?', *VERDICT]
    reply, gone = turn(verdict, 'i am out', understand=ears)
    assert reply.startswith('🔨 Court adjourned.') and gone is None


def test_unclear_or_broken_ears_fall_back_to_keywords():
    _, state = play('1', '3')
    for ears in (Brain(), Brain(fail=True), Brain({"Wait a second, it's faithful": {'action': 'dance'}})):
        reply, after = turn(state, "Wait a second, it's faithful", understand=ears)
        assert 'Faithful' in reply and after['stage'] == 'closed'
        reply, same = turn(state, 'hmm, a tough one', understand=ears)
        assert body(reply) == [PLEASE] and bare(same) == bare(state)
    _, prompt = play('1', '2')  # in a test, the court takes what the ears could not
    assert turn(prompt, 'add some eggs please', understand=Brain())[1]['stage'] == 'cross_result'


def test_the_ears_remember_six_lines():
    ears = Brain({'what now?': {'action': 'ask', 'answer': 'Your call, Your Honor.'}})
    _, state = play('1', 'what now?', 'what now?', 'what now?', understand=ears)
    assert len(state['history']) == 6 and state['history'][-2] == ['judge', 'what now?']
    assert state['history'][-1][0] == 'bailiff' and len(state['history'][-1][1].split()) <= 40
    assert len(ears.calls[-1]['history']) == 6 and ears.calls[-1]['history'][2:] == state['history'][:-2]
    assert 'history' in turn(state, 'new case')[1]  # a new case keeps what was said


def test_a_reused_run_says_so_and_a_new_run_is_one_sentence_away():
    asked = []

    def run(app, fresh=False):
        asked.append(fresh)
        return dict(TODO, ran_minutes_ago=4) if not fresh else TODO
    reply, state = turn(None, '1', run_case=run)
    assert nonblank(reply)[1] == '🕰️ The court ran this case 4 minutes ago. Say "run it again" for a fresh trial.'
    reply, state = turn(state, 'run it again', run_case=run, understand=Brain(fail=True))
    assert asked == [False, True] and '🕰️' not in reply and state['stage'] == 'verdict'
    assert 'moments ago' in turn(None, '1', run_case=lambda app, fresh: dict(TODO, ran_minutes_ago=0))[0]
    assert '1 minute ago' in turn(None, '1', run_case=lambda app, fresh: dict(TODO, ran_minutes_ago=1))[0]
