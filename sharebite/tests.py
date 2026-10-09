import io
import tempfile
from PIL import Image
from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from .models import User, Donation, DropoffLocation

class DonationWorkflowTests(APITestCase):
    def setUp(self):
        self.donor = User.objects.create_user(username='donor', password='Original-Pass-839!', is_donor=True)
        self.receiver = User.objects.create_user(username='receiver', password='Original-Pass-839!', is_receiver=True)
        self.other = User.objects.create_user(username='other', password='Original-Pass-839!')
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.test',
            password='Original-Pass-839!',
        )
        self.collection_point = DropoffLocation.objects.get(name='Ancoats Share Hub')
        self.donation = Donation.objects.create(
            donor=self.donor,
            title='Rice',
            description='Sealed bag',
            location=self.collection_point.address,
            collection_point=self.collection_point,
        )
        self.client.force_authenticate(self.receiver)

    def url(self, suffix=''):
        return f'/api/donations/{self.donation.pk}/{suffix}'

    def test_detail_and_health(self):
        self.client.force_authenticate(self.donor)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.assertEqual(self.client.get('/api/health/').json(), {'status': 'ok'})

    def test_all_donations_list_is_staff_only(self):
        self.assertEqual(self.client.get('/api/donations/').status_code, 403)
        self.assertEqual(self.client.head('/api/donations/').status_code, 403)
        self.client.force_authenticate(self.donor)
        self.assertEqual(self.client.get('/api/donations/').status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/donations/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_available_donations_are_receiver_only_and_redacted(self):
        eligible = Donation.objects.create(
            donor=self.donor,
            title='Available lentils',
            description='A sealed bag of lentils.',
            location=self.collection_point.address,
            collection_point=self.collection_point,
            collection_status='received_at_collection_point',
        )
        Donation.objects.create(
            donor=self.donor,
            title='Not yet received',
            description='Still awaiting drop-off.',
            location=self.collection_point.address,
            collection_point=self.collection_point,
        )
        Donation.objects.create(
            donor=self.donor,
            title='Already reserved',
            description='Reserved test donation.',
            location=self.collection_point.address,
            collection_point=self.collection_point,
            collection_status='received_at_collection_point',
            is_reserved=True,
            reserved_by=self.other,
        )
        Donation.objects.create(
            donor=self.donor,
            title='Already delivered',
            description='Delivered test donation.',
            location=self.collection_point.address,
            collection_point=self.collection_point,
            collection_status='received_at_collection_point',
            is_delivered=True,
        )

        response = self.client.get('/api/donations/available/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data], [eligible.pk])
        self.assertNotIn('email', response.data[0]['donor'])
        self.assertNotIn('reserved_by', response.data[0])
        self.assertNotIn('proof', response.data[0])
        self.assertNotIn('receipt', response.data[0])

        self.client.force_authenticate(self.donor)
        self.assertEqual(self.client.get('/api/donations/available/').status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/donations/available/').status_code, 403)

    def test_donation_detail_is_limited_to_staff_owner_or_reserving_receiver(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

        self.client.force_authenticate(self.donor)
        self.assertEqual(self.client.get(self.url()).status_code, 200)

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(self.url()).status_code, 200)

        self.donation.collection_status = 'received_at_collection_point'
        self.donation.is_reserved = True
        self.donation.reserved_by = self.receiver
        self.donation.save(
            update_fields=['collection_status', 'is_reserved', 'reserved_by'],
        )
        self.client.force_authenticate(self.receiver)
        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_reservation_cancel_and_repeated_reservation(self):
        self.assertEqual(self.client.post(self.url('reserve/')).status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(self.url('confirm-receipt/')).status_code, 200)
        self.client.force_authenticate(self.receiver)
        self.assertEqual(self.client.post(self.url('reserve/')).status_code, 200)
        self.assertEqual(self.client.post(self.url('reserve/')).status_code, 404)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(self.url('reserve/')).status_code, 403)
        self.assertEqual(self.client.post(self.url('cancel/')).status_code, 404)
        self.client.force_authenticate(self.receiver)
        self.assertEqual(self.client.post(self.url('cancel/')).status_code, 200)
        self.donation.refresh_from_db()
        self.assertIsNone(self.donation.reserved_by)
        self.assertFalse(self.donation.is_reserved)

    def test_donor_cannot_reserve_own_donation(self):
        self.donation.collection_status = 'received_at_collection_point'
        self.donation.save(update_fields=['collection_status'])
        self.client.force_authenticate(self.donor)
        self.assertEqual(self.client.post(self.url('reserve/')).status_code, 403)

    def test_only_receivers_can_reserve_received_donations(self):
        self.donation.collection_status = 'received_at_collection_point'
        self.donation.save(update_fields=['collection_status'])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(self.url('reserve/')).status_code, 403)
        self.client.force_authenticate(self.receiver)
        self.assertEqual(self.client.post(self.url('reserve/')).status_code, 200)

    def test_delivered_donation_cannot_be_reserved(self):
        self.donation.is_delivered = True
        self.donation.save()
        self.assertEqual(self.client.post(self.url('reserve/')).status_code, 404)

    def test_create_ignores_client_workflow_flags(self):
        response = self.client.post('/api/donations/', {
            'title': 'Beans',
            'description': 'Sealed',
            'location': self.collection_point.address,
            'collection_point': self.collection_point.pk,
            'is_reserved': True,
            'is_delivered': True,
            'status': 'Successful',
            'collection_status': 'received_at_collection_point',
        })
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data['is_reserved'])
        self.assertFalse(response.data['is_delivered'])
        self.assertEqual(response.data['status'], 'Pending')
        self.assertEqual(response.data['collection_point'], self.collection_point.pk)
        self.assertEqual(response.data['collection_point_details']['name'], 'Ancoats Share Hub')
        self.assertEqual(response.data['collection_status'], 'awaiting_dropoff')

    def test_donation_creation_requires_a_collection_point(self):
        response = self.client.post('/api/donations/', {
            'title': 'Beans',
            'description': 'Sealed',
            'location': 'Manchester',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('collection_point', response.data)

    def test_donor_can_create_donation_with_food_photo(self):
        content = io.BytesIO()
        Image.new('RGB', (8, 8), color='green').save(content, format='PNG')
        photo = SimpleUploadedFile(
            'vegetables.png',
            content.getvalue(),
            content_type='image/png',
        )
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response = self.client.post('/api/donations/', {
                'title': 'Fresh vegetables',
                'description': 'A small box of seasonal vegetables.',
                'location': self.collection_point.address,
                'collection_point': self.collection_point.pk,
                'quantity': '2',
                'expiry_date': '2026-10-20',
                'food_image': photo,
            }, format='multipart')

            self.assertEqual(response.status_code, 201, response.data)
            self.assertTrue(response.data['food_image'].endswith('.png'))
            self.assertEqual(response.data['quantity'], 2)
            self.assertEqual(response.data['expiry_date'], '2026-10-20')
            created_donation = Donation.objects.get(title='Fresh vegetables')
            self.assertTrue(created_donation.food_image.name.startswith('donations/'))

    def test_donation_photo_filename_is_shortened_to_fit_storage_field(self):
        content = io.BytesIO()
        Image.new('RGB', (8, 8), color='green').save(content, format='PNG')
        photo = SimpleUploadedFile(
            f'{"fresh_vegetables_" * 12}.png',
            content.getvalue(),
            content_type='image/png',
        )
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response = self.client.post('/api/donations/', {
                'title': 'Fresh vegetables',
                'description': 'A small box of seasonal vegetables.',
                'location': self.collection_point.address,
                'collection_point': self.collection_point.pk,
                'food_image': photo,
            }, format='multipart')

            self.assertEqual(response.status_code, 201, response.data)
            created_donation = Donation.objects.get(title='Fresh vegetables')
            self.assertLessEqual(len(created_donation.food_image.name), 100)
            self.assertTrue(created_donation.food_image.name.endswith('.png'))

    def test_collection_points_include_staffed_demo_details(self):
        response = self.client.get('/api/collection-points/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)
        self.assertTrue(all(point['address'] for point in response.data))
        self.assertTrue(all(point['latitude'] and point['longitude'] for point in response.data))
        self.assertTrue(all(point['opening_hours'] for point in response.data))
        self.assertTrue(all(point['accepted_food_types'] for point in response.data))
        self.assertTrue(all(point['instructions'] for point in response.data))

    def test_only_admin_can_confirm_collection_point_receipt(self):
        self.assertEqual(self.client.post(self.url('confirm-receipt/')).status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url('confirm-receipt/'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['collection_status'], 'received_at_collection_point')
        self.assertEqual(self.client.post(self.url('confirm-receipt/')).status_code, 200)

    def test_staff_can_confirm_and_non_staff_cannot_confirm_or_reserve_early(self):
        staff = User.objects.create_user(
            username='staff',
            password='Original-Pass-839!',
            is_staff=True,
        )
        self.assertEqual(self.client.post(self.url('confirm-receipt/')).status_code, 403)
        self.assertEqual(self.client.post(self.url('reserve/')).status_code, 404)

        self.client.force_authenticate(staff)
        response = self.client.post(self.url('confirm-receipt/'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['collection_status'], 'received_at_collection_point')

        self.client.force_authenticate(self.receiver)
        self.assertEqual(self.client.post(self.url('reserve/')).status_code, 200)

    def test_registration_cannot_grant_staff_access_and_login_returns_staff_flag(self):
        response = self.client.post('/api/register/', {
            'username': 'new-user',
            'password': 'Original-Pass-839!',
            'is_staff': True,
            'is_superuser': True,
        })
        self.assertEqual(response.status_code, 201, response.data)
        new_user = User.objects.get(username='new-user')
        self.assertFalse(new_user.is_staff)
        self.assertFalse(new_user.is_superuser)

        User.objects.create_user(
            username='staff',
            password='Original-Pass-839!',
            is_staff=True,
        )
        login_response = self.client.post('/api/login/', {
            'username': 'staff',
            'password': 'Original-Pass-839!',
        })
        self.assertEqual(login_response.status_code, 200)
        self.assertTrue(login_response.data['is_staff'])

        non_staff_response = self.client.post('/api/login/', {
            'username': self.receiver.username,
            'password': 'Original-Pass-839!',
        })
        self.assertEqual(non_staff_response.status_code, 200)
        self.assertFalse(non_staff_response.data['is_staff'])

    def test_unauthenticated_collection_point_list_is_rejected(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/collection-points/').status_code, 401)

    def test_profile_password_is_hashed_and_validated(self):
        self.assertEqual(self.client.patch('/api/edituser/', {'password':'short'}).status_code, 400)
        self.assertEqual(self.client.patch('/api/edituser/', {'password':'Replacement-Pass-927!'}).status_code, 200)
        self.receiver.refresh_from_db()
        self.assertTrue(self.receiver.check_password('Replacement-Pass-927!'))

    def test_member_list_and_dropoff_permissions(self):
        self.assertEqual(self.client.get('/api/members/').status_code, 403)
        self.assertEqual(self.client.get('/api/dropoff-sites/').status_code, 403)
        self.assertEqual(self.client.post('/api/dropoff-sites/', {'location':'Manchester'}).status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/dropoff-sites/').status_code, 200)

    def test_uploads_only_allowed_for_donation_participants(self):
        self.assertEqual(self.client.post(self.url('proof/'), {}).status_code, 403)
        self.assertEqual(self.client.post(self.url('receipt/'), {}).status_code, 403)

    def test_proof_and_receipt_use_server_owned_relations(self):
        def image():
            content = io.BytesIO()
            Image.new('RGB', (2, 2)).save(content, format='PNG')
            return SimpleUploadedFile('proof.png', content.getvalue(), content_type='image/png')
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.donation.collection_status = 'received_at_collection_point'
            self.donation.save(update_fields=['collection_status'])
            self.client.post(self.url('reserve/'))
            self.client.force_authenticate(self.donor)
            response = self.client.post(self.url('proof/'), {'proof_image':image()}, format='multipart')
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data['uploaded_by'], self.donor.pk)
            self.assertEqual(self.client.post(self.url('proof/'), {}, format='multipart').status_code, 400)
            self.client.force_authenticate(self.receiver)
            response = self.client.post(self.url('receipt/'), {'proof_image':image()}, format='multipart')
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response.data['user'], self.receiver.pk)
            self.assertEqual(self.client.post(self.url('receipt/'), {}).status_code, 400)

    def test_anonymous_donation_access_rejected(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/donations/').status_code, 401)
