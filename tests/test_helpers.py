from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

skill_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(skill_dir / 'scripts'))
import agent_browser as ab
import save_report as sr

VALID = '学习质量评估报告\n重新练习\n综合评估得\n95\n分\n本次学习共 3个知识点。'


class HelpersTest(unittest.TestCase):
    def test_argument_and_stdin_preservation(self):
        command = ['open', 'https://example.test/?a=1&b=中文', '@e123', '"quoted"']
        payload = 'document.title + "中文"\n'.encode()
        with patch.object(ab, 'resolve_binary', return_value=Path('native.exe')), patch.object(ab.subprocess, 'run') as run:
            run.return_value.returncode = 7
            result = ab.run_agent('owned-test', command, stdin=payload)
            self.assertEqual(result.returncode, 7)
            args, kwargs = run.call_args
            self.assertEqual(args[0][1:], ['--session', 'owned-test', *command])
            self.assertIs(kwargs['shell'], False)
            self.assertEqual(kwargs['input'], payload)

    def test_pipeline_is_inherited(self):
        with patch.object(ab, 'resolve_binary', return_value=Path('native.exe')), patch.object(ab.subprocess, 'run') as run:
            ab.run_agent('owned-test', ['eval', '--stdin'])
            self.assertNotIn('input', run.call_args.kwargs)

    def test_session_guard(self):
        for session in ('default', 'DEFAULT', '', '../bad', 'a b'):
            with self.assertRaises(ValueError):
                ab.validate_session(session)
        with self.assertRaises(ValueError):
            ab.run_agent('owned-test', ['--session', 'default', 'open', 'x'])

    def test_missing_command(self):
        with self.assertRaises(ValueError):
            ab.run_agent('owned-test', [])

    def test_explicit_cmd_rejected(self):
        with self.assertRaises(FileNotFoundError):
            ab.resolve_binary('not-a-native.cmd')

    def test_report_complete(self):
        text, info = sr.parse_report('Earlier conversation\n' + sr.REPORT_MARKER + VALID)
        self.assertEqual(info, {'score': 95, 'knowledge_points': 3})
        self.assertNotIn('Earlier', text)

    def test_report_incomplete_ambiguous_or_invalid(self):
        for body in (VALID.replace('本次学习共 3个知识点。', ''), VALID + '\n综合评估得 80 分', VALID.replace('95', '101'), VALID.replace('3个知识点', '0个知识点'), VALID.replace('重新练习', '生成中')):
            with self.assertRaises(ValueError):
                sr.parse_report(body)

    def test_no_capture_if_incomplete(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sr, 'run_agent', return_value=subprocess.CompletedProcess([], 0, json.dumps('生成中').encode())) as run:
            with self.assertRaises(ValueError):
                sr.capture_report('owned-test', Path(folder) / 'report', None, False)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_existing_output_guard(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sr, 'run_agent') as run:
            prefix = Path(folder) / 'report'
            Path(str(prefix) + '.txt').write_text('original')
            with self.assertRaises(FileExistsError):
                sr.capture_report('owned-test', prefix, None, False)
            run.assert_not_called()

    def test_failed_screenshot_produces_no_success_record(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sr, 'run_agent') as run:
            run.side_effect = [subprocess.CompletedProcess([], 0, json.dumps(VALID).encode()), subprocess.CompletedProcess([], 1, b'')]
            with self.assertRaises(RuntimeError):
                sr.capture_report('owned-test', Path(folder) / 'report', None, False)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_success_artifacts(self):
        def fake_run(session, command, **kwargs):
            if command[0] == 'eval':
                return subprocess.CompletedProcess([], 0, json.dumps(VALID).encode())
            self.assertEqual(command[0], 'screenshot')
            Path(command[1]).write_bytes(b'PNG-fixture')
            return subprocess.CompletedProcess([], 0, b'')
        with tempfile.TemporaryDirectory() as folder, patch.object(sr, 'run_agent', side_effect=fake_run):
            prefix = Path(folder) / 'report'
            info = sr.capture_report('owned-test', prefix, None, False)
            self.assertEqual(info['score'], 95)
            self.assertEqual(sorted(p.suffix for p in Path(folder).iterdir()), ['.json', '.png', '.txt'])
            self.assertEqual(json.loads(Path(str(prefix) + '.json').read_text())['knowledge_points'], 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
