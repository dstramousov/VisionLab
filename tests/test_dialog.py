"""Exercise command validation and dispatch without a camera or model."""
import unittest
from unittest.mock import patch

from backend.app import Lab
from backend.dialog import Command, context_messages, parse_command


class DialogTest(unittest.TestCase):
    def test_valid_commands(self) -> None:
        self.assertEqual(parse_command('```json\n{"action":"find","target":"часы"}\n```').target, 'часы')
        self.assertEqual(parse_command('{"action":"track","target":"часы","verify_interval":15}').verify_interval, 15)

    def test_invalid_commands(self) -> None:
        for text in ('{"action":"shell"}', '{"action":"track"}', '{"action":"clear","target":"x"}',
                     '{"action":"options","verify_interval":-1}', '{"action":"options","trajectory":"true"}',
                     '{"action":"ask","extra":1}', '{"action":"options"}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_command(text)

    def test_dispatch(self) -> None:
        lab = Lab()
        with patch.object(lab, 'submit') as submit:
            self.assertIsNone(lab.execute_dialog(Command(action='find', target='часы'), 'найди часы'))
            submit.assert_called_once_with('часы', 'focus', 'найди часы')
        lab.execute_dialog(Command(action='options', trajectory=False, verify_interval=15), 'options')
        self.assertFalse(lab.attention.trajectory)
        self.assertEqual(lab.attention.verify_interval, 15)
        lab.tracking = True
        lab.execute_dialog(Command(action='clear'), 'stop')
        self.assertFalse(lab.tracking)

    def test_context_is_bounded(self) -> None:
        events = [{'kind': 'question', 'question': str(i), 'answer': 'x'} for i in range(8)]
        events.append({'kind': 'tracking', 'answer': 'ignored'})
        messages = context_messages(events)
        self.assertEqual(len(messages), 8)
        self.assertEqual(messages[0]['content'], '4')

    def test_refine_without_focus(self) -> None:
        with self.assertRaises(RuntimeError):
            Lab().execute_dialog(Command(action='refine'), 'уточни')

    def test_router_requests_non_thinking_json(self) -> None:
        lab = Lab()
        lab.frame = b'frame'
        lab.busy = True
        with patch('backend.app.requests.post') as post, patch.object(lab, 'ready', return_value=True), patch.object(lab, 'submit') as submit:
            post.return_value.json.return_value = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"action":"ask"}'}}]}
            lab.route_dialog('Что ты видишь?', 'stamp', [], (lab.orientation_epoch, lab.track_epoch))
            payload = post.call_args.kwargs['json']
            self.assertEqual(payload['chat_template_kwargs'], {'enable_thinking': False})
            self.assertEqual(payload['response_format'], {'type': 'json_object'})
            submit.assert_called_once_with('Что ты видишь?', 'question', 'Что ты видишь?')

    def test_router_limit_does_not_execute(self) -> None:
        lab = Lab()
        lab.busy = True
        with patch('backend.app.requests.post') as post, patch.object(lab, 'execute_dialog') as execute, patch.object(lab, 'dialog_event') as event:
            post.return_value.json.return_value = {'choices': [{'finish_reason': 'length', 'message': {'content': '', 'reasoning_content': 'thinking'}}]}
            lab.route_dialog('найди часы', 'stamp', [], (lab.orientation_epoch, lab.track_epoch))
            execute.assert_not_called()
            self.assertFalse(lab.busy)
            self.assertIn('лимит генерации', event.call_args.args[2])
