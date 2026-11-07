"""Courtroom flow tests, using the two summaries the court measured today."""
import json
import re

import pytest

from agents.mesh.courtroom import CASES, LOBBY, VERDICT, respond

TODO = {
    'app': 'todo', 'title': 'Todo', 'about': 'a 2016 to-do app, archived on GitHub',
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
    'app': 'app1', 'title': 'the Calculator', 'about': 'a pocket calculator revived by AI',
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


def fake_run_case(app_id):
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



GREETING = '🔨 All rise! Your Honor, a dead app awaits your judgment.'
PLEASE = 'Your Honor, please choose 1, 2, or 3.'


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
    assert re.match(r'3\) ', last) or last.startswith(('Your Honor, type something to try', 'Type "all rise"')), reply


def turn(state, text, run_case=fake_run_case, run_cross=fake_run_cross):
    reply, state = respond(state, text, run_case=run_case, run_cross=run_cross)
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


def test_two_cases_on_the_docket():
    assert CASES == {'1': 'todo', '2': 'app1'}


def test_todo_is_an_honest_win():
    (lobby, how, verdict, argue, prompt, crossed, ask, ruled, record, bye), state = play(
        '@thebailiff hello', '3', '1', '1', '2', 'add milk', '3', '1', '2', '3')
    assert nonblank(lobby) == [GREETING] + LOBBY
    assert len(body(how)) <= 4 and how.endswith('\n'.join(LOBBY))
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
    assert '🔍 Typed "milk", pressed Enter\n\nOriginal: 1 item: milk · Revival: 1 item: milk ✅' in crossed
    assert ask == '⚖️ How do you rule, Your Honor?\n\n1) Faithful\n2) Forgery\n3) Needs repair'
    assert ruled.startswith('⚖️ Your Honor rules: Faithful.\n\n✅ The evidence agrees with Your Honor.')
    assert '🔨 Case closed.' in ruled
    assert len(body(record)) <= 5
    for fact in ('15 claims locked, 1 struck', 'No differences found', 'Fidelity score: 100 out of 100',
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
    assert '🔍 Pressed 7 ÷ 8 =\n\nOriginal: 0.87 · Revival: 0.88 ❌' in crossed
    assert ruled.startswith('⚖️ Your Honor rules: Forgery.\n\n✅ The evidence agrees with Your Honor.')
    for fact in ('11 claims locked, 0 struck', '2 differences found', 'Fidelity score: 93 out of 100',
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
    assert '🔍 Pressed 7 ÷ 8 =' in turn(state, '@thebailiff 7 / 8 =')[0]


def test_unknown_input_repeats_the_choices():
    greeting, lobby = turn(None, 'what is going on')
    assert nonblank(greeting) == [GREETING] + LOBBY
    reply, same = turn(lobby, 'banana')
    assert nonblank(reply) == [PLEASE] + LOBBY and same == lobby
    _, verdict = turn(lobby, '1')
    for text in ('maybe later', '1 or 2', '@thebailiff', 'no'):
        reply, same = turn(verdict, text)
        assert nonblank(reply) == [PLEASE] + VERDICT and same == verdict
    _, ask = turn(verdict, '3')
    reply, same = turn(ask, 'not faithful')
    assert reply.startswith(PLEASE) and same == ask


def test_case_error_offers_a_way_out():
    def broken(app_id):
        raise Exception('The original app would not start.')
    reply, state = turn(None, '1', run_case=broken)
    assert nonblank(reply) == ['🔨 The court could not open that case. The original app would not start.',
                                 'Your Honor, what now?', '1) Try again', '2) Other case', '3) How this court works']
    assert state == {'stage': 'case_error', 'case': '1'}
    assert turn(state, 'try again')[0].startswith('⚖️ The case of Todo: ')
    assert turn(state, '2')[0].startswith('⚖️ The case of the Calculator: ')
    reply, lobby = turn(state, '3')
    assert reply.endswith('\n'.join(LOBBY)) and lobby == {'stage': 'lobby'}
    reply, state = turn(None, '2', run_case=lambda app_id: {'title': 'Half a case'})
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
    assert nonblank(lobby) == [GREETING] + LOBBY and state == {'stage': 'lobby'}


def test_outside_text_still_obeys_the_rules():
    wordy = dict(TODO, title='{Todo}', argument=[{'who': 'hoot', 'line': ' '.join(['hoo'] * 45)}],
                 examples=[{'did': 'Typed [x]', 'original': '[]', 'revival': '{}'}])
    (verdict, argue), _ = play('1', '1', run_case=lambda app_id: wordy)
    assert verdict.startswith('⚖️ The case of Todo: ')
    assert argue.count('hoo') == 45  # split across lines, not cut


def test_lines_are_paragraphs_and_choices_a_list():
    """ASI:One renders Markdown: one blank line between thoughts, the three choices together."""
    reply, _ = turn(None, 'hello')
    assert reply == GREETING + '\n\n' + '\n'.join(LOBBY)


def test_they_argue_live_when_the_parties_answer():
    _, state = play('1')
    live = [{'who': 'hoot', 'line': 'Hoo. One perjury.'}, {'who': 'mcclusky', 'line': 'Fifteen held!'},
            {'who': 'hoot', 'line': 'Still one.'}]
    reply, same = respond(state, '1', run_case=fake_run_case, run_cross=fake_run_cross, run_argue=lambda app: live)
    assert body(reply)[:3] == ['🦉 Hoot: Hoo. One perjury.', '🐧 McClusky: Fifteen held!', '🦉 Hoot: Still one.']
    assert same == state

    def down(app):
        raise TimeoutError('Dr. Hoot did not answer')
    reply, _ = respond(state, '1', run_case=fake_run_case, run_cross=fake_run_cross, run_argue=down)
    assert body(reply)[0].startswith('🦉 Hoot:')  # the argument on file


@pytest.mark.parametrize('stage_texts, text', [
    (('1', '3'), "Wait a second, it's faithful"),  # keyword faithful wins only when nothing contradicts it
])
def test_free_text_ruling_needs_one_clear_choice(stage_texts, text):
    _, state = play(*stage_texts)
    reply, after = turn(state, text)
    assert 'Faithful' in reply and after['stage'] == 'closed'


@pytest.mark.parametrize('text', ["it doesn't look faithful", '1 forgery', 'hmm, tough one', 'that one'])
def test_contradictions_ask_again(text):
    _, state = play('1', '3')
    reply, same = turn(state, text)
    assert body(reply) == [PLEASE] and same == state


@pytest.mark.parametrize('text', ['the other one', 'which one should I pick?'])
def test_the_lobby_never_guesses_a_case(text):
    reply, state = turn(None, text)
    assert state == {'stage': 'lobby'} and 'The case of' not in body(reply)[0]


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
    reply, after = turn(state, '3')
    assert body(reply)[0].startswith('🔍') and after['stage'] in ('cross_prompt', 'cross_result')
