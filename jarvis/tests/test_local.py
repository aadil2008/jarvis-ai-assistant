from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_setup import Memory, MODELS, choices_for, describe, detect_memory
from local_settings import load_settings, save_settings, provider
from local_client import LocalClient, OLLAMA_URL, NoRedirects, local_opener
from router_client import RouterClientError
from brain import Brain
import setup_local


class RecommendationTests(unittest.TestCase):
    def test_ram_tiers_and_boundaries(self):
        for total, model in [(3.9, None), (4, 'qwen3:0.6b'), (7.9, 'qwen3:0.6b'),
                             (8, 'qwen3:1.7b'), (15.9, 'qwen3:1.7b'), (16, 'qwen3:4b'),
                             (24, 'qwen3:4b'), (32, 'qwen3:8b'), (64, 'qwen3:8b')]:
            with self.subTest(ram=total):
                choices = choices_for(Memory(total, total - 1))
                self.assertEqual(choices[-1].name if choices else None, model)

    def test_available_ram_can_lower_or_block_recommendation(self):
        self.assertEqual(choices_for(Memory(32, 4))[-1].name, 'qwen3:1.7b')
        self.assertEqual(choices_for(Memory(32, 2)), [])

    def test_unknown_or_invalid_memory_never_guesses_large_model(self):
        for total, available in [(None, None), (0, 0), (float('nan'), 10), (8, -1), (8, float('nan'))]:
            self.assertEqual(choices_for(Memory(total, available)), [])
        self.assertIn('unavailable', describe(Memory(None, None)))
        self.assertEqual(choices_for(Memory(8, None))[-1].name, 'qwen3:1.7b')

    def test_system_probe_reads_total_and_available(self):
        fake = SimpleNamespace(virtual_memory=lambda: SimpleNamespace(total=16*1024**3, available=6*1024**3))
        with patch.dict(sys.modules, {'psutil': fake}):
            self.assertEqual(detect_memory(), Memory(16, 6))
        with patch.dict(sys.modules, {'psutil': None}):
            self.assertEqual(detect_memory(), Memory(None, None))


class SettingsTests(unittest.TestCase):
    def test_persistence_and_invalid_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'local_config.json'
            self.assertEqual(load_settings(path), {})
            save_settings('qwen3:1.7b', path)
            self.assertEqual(load_settings(path), {'provider': 'local', 'model': 'qwen3:1.7b', 'whisper_model': 'tiny.en'})
            self.assertFalse(path.with_suffix('.tmp').exists())
            for text in ('[]', '{broken'):
                path.write_text(text)
                with self.assertRaises(RouterClientError):
                    load_settings(path)

    def test_local_default_and_explicit_router_opt_in(self):
        with patch.dict('os.environ', {}, clear=True), patch('local_settings.load_settings', return_value={}):
            self.assertEqual(provider(), 'local')
        with patch.dict('os.environ', {'JARVIS_PROVIDER': 'router'}):
            self.assertEqual(provider(), 'router')

    def test_remote_cloud_and_unknown_models_not_accepted(self):
        for name in ('qwen3:cloud', 'gpt-oss:120b-cloud', 'remote/model', None):
            with self.assertRaises(RouterClientError):
                LocalClient({'model': name})


class LocalInferenceTests(unittest.TestCase):
    def client(self, payload=None, opener=None, **kwargs):
        self.requests = []
        def fake_open(request, timeout):
            self.requests.append(request)
            return io.BytesIO(json.dumps(payload).encode())
        return LocalClient({'model': 'qwen3:1.7b', 'whisper_model': 'tiny.en'}, opener=opener or fake_open, **kwargs)

    def test_chat_protocol_local_only_and_bounded_context(self):
        client = self.client({'done': True, 'message': {'content': 'Ready.'}})
        reply = client.chat('Hello', conversation=[{'role':'user','content':'x'*500}]*16, max_tokens=1000)
        self.assertEqual(reply.answer, 'Ready.')
        self.assertEqual(reply.route, 'local')
        request = self.requests[0]
        self.assertEqual(request.full_url, OLLAMA_URL + '/api/chat')
        self.assertIsNone(request.get_header('Authorization'))
        payload = json.loads(request.data)
        self.assertFalse(payload['think'])
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['options']['num_ctx'], 2048)
        self.assertEqual(payload['options']['num_predict'], 350)
        self.assertLessEqual(len(payload['messages']), 8)

    def test_network_error_does_not_fall_back_to_cloud_or_pollute_history(self):
        opener = Mock(side_effect=urllib.error.URLError('private-details'))
        client = self.client(opener=opener)
        with patch('brain.RouterClient') as router:
            brain = Brain(client=client)
            self.assertIn('No cloud fallback', brain.ask('Hello'))
            router.assert_not_called()
            self.assertEqual(brain.history, [])
            self.assertNotIn('private-details', brain.last_error)

    def test_missing_model_and_malformed_answers(self):
        client = self.client({'models': []})
        with self.assertRaisesRegex(RouterClientError, 'Download'):
            client.health()
        for payload in ({'done': False,'message':{'content':'partial'}}, {'done':True,'message':{}}, [], {'error':'secret'}):
            with self.subTest(payload=payload), self.assertRaises(RouterClientError):
                self.client(payload).chat('Hello')

    def test_too_long_query_is_rejected_before_network(self):
        client = self.client({})
        with self.assertRaises(RouterClientError):
            client.chat('x'*2001)
        self.assertEqual(self.requests, [])

    def test_proxy_and_redirects_are_disabled(self):
        opener = local_opener().__self__
        self.assertTrue(any(isinstance(h, NoRedirects) for h in opener.handlers))
        self.assertIsNone(NoRedirects().redirect_request(None,None,302,'',{},'https://example.com'))
        with patch.dict('os.environ', {'HTTP_PROXY':'http://secret-proxy.example'}):
            opener = local_opener().__self__
            self.assertFalse(any(hasattr(h, 'proxies') and h.proxies for h in opener.handlers))

    def test_speech_runs_from_local_files_and_does_not_write_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp)/'whisper-tiny.en'; model.mkdir()
            for name in ('model.bin','config.json','tokenizer.json'):
                (model/name).write_text('test')
            engine = Mock()
            engine.transcribe.return_value = (iter([SimpleNamespace(text=' open Safari ')]), None)
            factory = Mock(return_value=engine)
            client = self.client({}, transcriber_factory=factory, model_dir=Path(tmp))
            self.assertEqual(client.transcribe(b'wav'), 'open Safari')
            self.assertTrue(factory.call_args.kwargs['local_files_only'])
            self.assertEqual(factory.call_args.kwargs['device'], 'cpu')
            self.assertEqual(factory.call_args.kwargs['compute_type'], 'int8')
            self.assertIsInstance(engine.transcribe.call_args.args[0], io.BytesIO)
            self.assertEqual(self.requests, [])
            self.assertEqual(len(list(Path(tmp).rglob('*'))), 4)

    def test_missing_speech_files_never_trigger_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            factory = Mock()
            client = self.client({}, transcriber_factory=factory, model_dir=Path(tmp))
            with self.assertRaisesRegex(RouterClientError, 'missing'):
                client.transcribe(b'audio')
            factory.assert_not_called()


class SetupTests(unittest.TestCase):
    def test_recommend_only_and_declining_download_have_no_side_effects(self):
        with patch('setup_local.detect_memory',return_value=Memory(8,6)), patch('setup_local.install') as install:
            with patch('sys.stdout',new=io.StringIO()):
                self.assertEqual(setup_local.run_setup(recommend_only=True, input_fn=Mock(side_effect=AssertionError)),0)
                self.assertEqual(setup_local.run_setup(input_fn=Mock(side_effect=['','n'])),0)
                self.assertEqual(setup_local.run_setup(input_fn=Mock(side_effect=['q'])),0)
            install.assert_not_called()

    def test_selected_smaller_model_is_honored(self):
        with patch('setup_local.detect_memory',return_value=Memory(16,12)), patch('setup_local.install') as install, patch('sys.stdout',new=io.StringIO()):
            self.assertEqual(setup_local.run_setup(input_fn=Mock(side_effect=['1','y'])),0)
            install.assert_called_once_with(MODELS[0])

    def test_low_memory_and_bad_selection_do_not_install(self):
        with patch('setup_local.install') as install, patch('sys.stdout',new=io.StringIO()):
            with patch('setup_local.detect_memory',return_value=Memory(2,1)):
                self.assertEqual(setup_local.run_setup(input_fn=Mock(side_effect=AssertionError)),1)
            with patch('setup_local.detect_memory',return_value=Memory(8,6)):
                for choice in ('0','-1','999','not a number'):
                    self.assertEqual(setup_local.run_setup(input_fn=Mock(return_value=choice)),1)
            install.assert_not_called()

    def test_missing_ollama_and_low_disk_stop_before_download_or_save(self):
        with patch('setup_local.save_settings') as save, patch('setup_local.subprocess.run') as run:
            with patch('setup_local.shutil.which',return_value=None):
                with self.assertRaisesRegex(RouterClientError, 'Install Ollama'):
                    setup_local.install(MODELS[0])
            with patch('setup_local.shutil.which',return_value='/fake/ollama'), patch('setup_local.LocalClient'), patch('setup_local.disk_free',return_value=0):
                with self.assertRaisesRegex(RouterClientError, 'disk space'):
                    setup_local.install(MODELS[0])
            save.assert_not_called(); run.assert_not_called()

    def test_failed_pull_preserves_settings(self):
        with patch('setup_local.shutil.which',return_value='/fake/ollama'), patch('setup_local.LocalClient'), patch('setup_local.disk_free',return_value=100), patch('setup_local.subprocess.run',side_effect=subprocess.CalledProcessError(1,'ollama')), patch('setup_local.save_settings') as save, patch('sys.stdout',new=io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError):
                setup_local.install(MODELS[0])
            save.assert_not_called()

    def test_success_checks_chat_and_speech_before_saving(self):
        fake_whisper = SimpleNamespace(WhisperModel=Mock())
        fake_whisper.WhisperModel.return_value.transcribe.return_value = (iter([]), None)
        fake_utils = SimpleNamespace(download_model=Mock())
        with patch.dict(sys.modules,{'faster_whisper':fake_whisper,'faster_whisper.utils':fake_utils}), patch('setup_local.shutil.which',return_value='/fake/ollama'), patch('setup_local.LocalClient') as client, patch('setup_local.disk_free',return_value=100), patch('setup_local.subprocess.run') as run, patch('setup_local.save_settings') as save, patch('sys.stdout',new=io.StringIO()):
            setup_local.install(MODELS[0])
            self.assertEqual(run.call_args.args[0], ['/fake/ollama','pull','qwen3:0.6b'])
            self.assertEqual(run.call_args.kwargs['env']['OLLAMA_HOST'], OLLAMA_URL)
            client.return_value.chat.assert_called_once()
            fake_utils.download_model.assert_called_once()
            self.assertTrue(fake_whisper.WhisperModel.call_args.kwargs['local_files_only'])
            save.assert_called_once_with('qwen3:0.6b')


if __name__ == '__main__':
    unittest.main()
