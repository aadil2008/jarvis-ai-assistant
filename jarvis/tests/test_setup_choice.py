import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import setup_assistant
from local_settings import load_settings
from router_client import RouterClientError
import launch


class ChoiceTests(unittest.TestCase):
    def test_local_choice_never_asks_for_api_key(self):
        password = Mock(side_effect=AssertionError)
        with patch('setup_assistant.install_requirements') as dependencies, patch('setup_local.run_setup',return_value=0) as local, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup_assistant.run_setup(input_fn=Mock(return_value='1'),password_fn=password),0)
            self.assertEqual(dependencies.call_args.args[0].name,'requirements-local.txt')
            local.assert_called_once(); password.assert_not_called()

    def test_cloud_choice_never_installs_local_models(self):
        with patch('setup_assistant.install_requirements') as dependencies, patch('setup_assistant.configure_cloud',return_value=True) as cloud, patch('setup_local.run_setup') as local, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup_assistant.run_setup(input_fn=Mock(return_value='2')),0)
            self.assertEqual(dependencies.call_args.args[0].parent.name,'router')
            cloud.assert_called_once(); local.assert_not_called()

    def test_cancel_and_invalid_choice_leave_existing_settings(self):
        with patch('setup_assistant.install_requirements') as dependencies, patch('setup_assistant.configure_cloud') as cloud, contextlib.redirect_stdout(io.StringIO()):
            for value,result in [('q',0),('',1),('invalid',1)]:
                self.assertEqual(setup_assistant.run_setup(input_fn=Mock(return_value=value)),result)
            cloud.assert_not_called(); dependencies.assert_not_called()

    def test_cloud_setup_saves_secret_without_printing_and_preserves_other_settings(self):
        from dotenv import dotenv_values
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'.env'; path.write_text('FAST_MODEL=existing-model\n')
            output=io.StringIO()
            with patch('setup_assistant.write_settings') as save, contextlib.redirect_stdout(output):
                self.assertTrue(setup_assistant.configure_cloud(password_fn=lambda _: 'gsk_test-secret-value',env_path=path))
                save.assert_called_once_with({'provider':'router'})
            values=dotenv_values(path)
            self.assertEqual(values['FAST_MODEL'],'existing-model')
            self.assertEqual(values['GROQ_API_KEY'],'gsk_test-secret-value')
            self.assertGreaterEqual(len(values['ROUTER_API_KEY']),32)
            self.assertNotIn('gsk_test-secret-value',output.getvalue())
            self.assertNotIn(values['ROUTER_API_KEY'],output.getvalue())
            if os.name != 'nt':
                self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_cancelled_or_invalid_cloud_key_leaves_files_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'.env'; path.write_text('FAST_MODEL=original\n')
            with patch('setup_assistant.write_settings') as save, contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(setup_assistant.configure_cloud(password_fn=lambda _: '',env_path=path))
                with self.assertRaises(RouterClientError):
                    setup_assistant.configure_cloud(password_fn=lambda _: 'invalid',env_path=path)
                save.assert_not_called()
            self.assertEqual(path.read_text(),'FAST_MODEL=original\n')

    def test_desktop_environment_never_receives_groq_key(self):
        with patch.dict(os.environ,{'GROQ_API_KEY':'secret','ROUTER_API_KEY':'router-secret','JARVIS_ROUTER_API_KEY':'old-secret'}):
            for backend in ('router','local'):
                result=launch.desktop_environment(backend)
                self.assertNotIn('GROQ_API_KEY',result)
                self.assertNotIn('ROUTER_API_KEY',result)
                self.assertNotIn('JARVIS_ROUTER_API_KEY',result)
                self.assertEqual(result['JARVIS_PROVIDER'],backend)

    def test_local_launch_never_starts_router(self):
        with patch.dict(os.environ,{'JARVIS_PROVIDER':'local'}), patch('launch.subprocess.call',return_value=0) as desktop, patch('launch.subprocess.Popen') as server:
            self.assertEqual(launch.launch('--text'),0)
            server.assert_not_called()
            self.assertEqual(desktop.call_args.kwargs['env']['JARVIS_PROVIDER'],'local')


if __name__ == '__main__':
    unittest.main()

class CloudLaunchTests(unittest.TestCase):
    def test_router_lifecycle_and_desktop_secret_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'jarvis'; base.mkdir()
            fake_socket=Mock(); fake_socket.getsockname.return_value=('127.0.0.1',54321)
            socket_context=Mock(__enter__=Mock(return_value=fake_socket),__exit__=Mock(return_value=None))
            process=Mock(); process.poll.return_value=None
            with patch.dict(os.environ,{'JARVIS_PROVIDER':'router'}), patch('launch.BASE_DIR',base), patch('dotenv.dotenv_values',return_value={'GROQ_API_KEY':'gsk_test','ROUTER_API_KEY':'router-test'}), patch('launch.socket.socket',return_value=socket_context), patch('launch.subprocess.Popen',return_value=process) as server, patch('launch.RouterClient') as client, patch('launch.subprocess.call',return_value=0) as desktop:
                client.return_value.health.return_value=True
                self.assertEqual(launch.launch('--text'),0)
                self.assertEqual(server.call_args.kwargs['env']['GROQ_API_KEY'],'gsk_test')
                self.assertEqual(desktop.call_args.kwargs['env']['JARVIS_ROUTER_API_KEY'],'router-test')
                self.assertNotIn('GROQ_API_KEY',desktop.call_args.kwargs['env'])
                self.assertEqual(desktop.call_args.kwargs['env']['JARVIS_ROUTER_URL'],'http://127.0.0.1:54321')
                process.terminate.assert_called_once(); process.wait.assert_called_once()

    def test_first_launch_prompts_for_choice_and_cancel_does_not_run(self):
        with patch.dict(os.environ,{},clear=True), patch('launch.CONFIG_PATH') as config, patch('setup_assistant.run_setup',return_value=0) as setup, patch('launch.subprocess.call') as desktop:
            config.exists.return_value=False
            self.assertEqual(launch.launch(),1)
            setup.assert_called_once(); desktop.assert_not_called()
