import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

PURGE = '/internal/purge-print-files/'


class DeployGlueTests(TestCase):
    def test_healthz_is_a_plain_ok(self):
        r = self.client.get('/healthz/')
        self.assertEqual((r.status_code, r.content), (200, b'ok'))

    @override_settings(CRON_TOKEN='s3cret-token')
    def test_purge_needs_the_token_and_a_post(self):
        with mock.patch('config.views.call_command') as run:
            self.assertEqual(self.client.post(PURGE).status_code, 404)
            self.assertEqual(self.client.post(PURGE, HTTP_AUTHORIZATION='Bearer wrong').status_code, 404)
            self.assertEqual(self.client.post(PURGE, HTTP_AUTHORIZATION='s3cret-token').status_code, 404)
            self.assertEqual(self.client.get(PURGE, HTTP_AUTHORIZATION='Bearer s3cret-token').status_code, 404)
            run.assert_not_called()
            r = self.client.post(PURGE, HTTP_AUTHORIZATION='Bearer s3cret-token')
        self.assertEqual(r.status_code, 200)
        run.assert_called_once()
        self.assertTrue(r.json()['ok'])

    @override_settings(CRON_TOKEN='')
    def test_purge_is_switched_off_without_a_token(self):
        with mock.patch('config.views.call_command') as run:
            self.assertEqual(self.client.post(PURGE, HTTP_AUTHORIZATION='Bearer ').status_code, 404)
            self.assertEqual(self.client.post(PURGE).status_code, 404)
            run.assert_not_called()

    def test_public_media_is_served_but_private_media_is_not(self):
        with tempfile.TemporaryDirectory() as pub, tempfile.TemporaryDirectory() as priv:
            (Path(pub) / 'photo.txt').write_text('public')
            (Path(priv) / 'secret.txt').write_text('secret')
            with override_settings(MEDIA_ROOT=pub, PRIVATE_MEDIA_ROOT=priv):
                r = self.client.get('/media/photo.txt')
                self.assertEqual(b''.join(r.streaming_content), b'public')
                r.close()
                self.assertEqual(self.client.get('/media/secret.txt').status_code, 404)
                self.assertIn(self.client.get('/media/../' + Path(priv).name + '/secret.txt').status_code, (400, 404))
