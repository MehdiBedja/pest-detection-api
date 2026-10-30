import uuid

from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from user_management.models import CustomUser

from .models import BoundingBox, DetectionResult


def make_detection(user, note='', updated_at1=None):
    detection = DetectionResult.objects.create(
        user=user, timestamp=1_700_000_000_000, detection_date=1_700_000_000_000,
        note=note, updated_at1=updated_at1,
    )
    BoundingBox.objects.create(
        detection=detection, x1=0.1, y1=0.1, x2=0.5, y2=0.5, cx=0.3, cy=0.3,
        w=0.4, h=0.4, cnf=0.93, cls=3, cls_name='aphid',
    )
    return detection


class DetectionApiTestCase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='u1', email='u1@example.com', password='pw')
        self.other = CustomUser.objects.create_user(username='u2', email='u2@example.com', password='pw')
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.create(user=self.user).key}')


class AuthRequiredTests(TestCase):
    def test_endpoints_require_authentication(self):
        client = APIClient()
        for method, url in [
            ('post', '/detection/fetch/'),
            ('post', '/detection/upload/'),
            ('get', '/detection/deleted/'),
            ('post', '/detection/delete/batch/'),
            ('post', '/detection/sync/notes/'),
        ]:
            with self.subTest(url=url):
                self.assertEqual(getattr(client, method)(url).status_code, 401)


class FetchDetectionsTests(DetectionApiTestCase):
    def test_returns_detections_missing_on_client_and_server(self):
        on_both = make_detection(self.user)
        only_server = make_detection(self.user)
        only_phone = uuid.uuid4()
        make_detection(self.other)  # must never leak to self.user

        response = self.client.post(
            '/detection/fetch/', {'ids': [str(on_both.server_id), str(only_phone)]}, format='json'
        )

        self.assertEqual(response.status_code, 200)
        sent = response.data['detections_to_send']
        self.assertEqual([d['detection']['serverId'] for d in sent], [str(only_server.server_id)])
        self.assertEqual(sent[0]['boundingBoxes'][0]['clsName'], 'aphid')
        self.assertEqual(response.data['detections_needed_from_phone'], [only_phone])

    def test_soft_deleted_detections_are_not_sent(self):
        detection = make_detection(self.user)
        detection.is_deleted = True
        detection.save()

        response = self.client.post('/detection/fetch/', {'ids': []}, format='json')
        self.assertEqual(response.data['detections_to_send'], [])

    def test_rejects_invalid_ids(self):
        self.assertEqual(self.client.post('/detection/fetch/', {'ids': 'nope'}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/detection/fetch/', {'ids': ['bad-uuid']}, format='json').status_code, 400)
        self.assertEqual(self.client.get('/detection/fetch/').status_code, 400)


class SoftDeleteTests(DetectionApiTestCase):
    def test_soft_delete_single_detection(self):
        detection = make_detection(self.user)
        response = self.client.post(f'/detection/{detection.server_id}/delete/')

        self.assertEqual(response.status_code, 200)
        detection.refresh_from_db()
        self.assertTrue(detection.is_deleted)

    def test_cannot_soft_delete_another_users_detection(self):
        detection = make_detection(self.other)
        response = self.client.post(f'/detection/{detection.server_id}/delete/')

        self.assertEqual(response.status_code, 404)
        detection.refresh_from_db()
        self.assertFalse(detection.is_deleted)

    def test_batch_delete_only_affects_own_detections(self):
        mine = make_detection(self.user)
        theirs = make_detection(self.other)

        response = self.client.post(
            '/detection/delete/batch/',
            {'server_ids': [str(mine.server_id), str(theirs.server_id)]},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('1 detections', response.data['message'])
        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertTrue(mine.is_deleted)
        self.assertFalse(theirs.is_deleted)

    def test_batch_delete_requires_non_empty_list(self):
        response = self.client.post('/detection/delete/batch/', {'server_ids': []}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_list_soft_deleted_ids(self):
        deleted = make_detection(self.user)
        deleted.is_deleted = True
        deleted.save()
        make_detection(self.user)

        response = self.client.get('/detection/deleted/')
        self.assertEqual(response.data['deleted_ids'], [deleted.server_id])


class NotesTests(DetectionApiTestCase):
    def test_update_notes_ignores_other_users(self):
        mine = make_detection(self.user)
        theirs = make_detection(self.other)

        response = self.client.post(
            '/detection/notes/update/',
            {'notes': [
                {'server_id': str(mine.server_id), 'note': 'sprayed'},
                {'server_id': str(theirs.server_id), 'note': 'hijacked'},
            ]},
            format='json',
        )

        self.assertEqual(response.data['updated_ids'], [str(mine.server_id)])
        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertEqual(mine.note, 'sprayed')
        self.assertEqual(theirs.note, '')

    def test_sync_notes_newest_version_wins(self):
        phone_newer = make_detection(self.user, note='old', updated_at1=100)
        server_newer = make_detection(self.user, note='server note', updated_at1=500)

        response = self.client.post(
            '/detection/sync/notes/',
            {'detections': [
                {'serverId': str(phone_newer.server_id), 'updatedAt': 200, 'note': 'from phone'},
                {'serverId': str(server_newer.server_id), 'updatedAt': 300, 'note': 'stale'},
            ]},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        phone_newer.refresh_from_db()
        self.assertEqual(phone_newer.note, 'from phone')
        self.assertEqual(phone_newer.updated_at1, 200)
        self.assertEqual(response.data['detections'], [
            {'serverId': str(server_newer.server_id), 'updatedAt': 500, 'note': 'server note'},
        ])

    def test_sync_notes_rejects_non_list(self):
        response = self.client.post('/detection/sync/notes/', {'detections': 'x'}, format='json')
        self.assertEqual(response.status_code, 400)
