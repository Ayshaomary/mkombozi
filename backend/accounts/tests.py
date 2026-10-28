from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from . import password_reset
from .models import PasswordResetCode, User
from .testing import client_for, make_business
from .utils import normalize_phone, phone_too_long


class PhoneNormalizationTests(TestCase):
    def test_tanzanian_formats_become_one(self):
        for raw in ['0712345678', '0712 345 678', '255712345678', '+255712345678', '+255 712-345-678']:
            self.assertEqual(normalize_phone(raw), '+255712345678')

    def test_phone_length_limits(self):
        # Without a country code: at most 10 digits
        self.assertFalse(phone_too_long('0712 345 678'))
        self.assertTrue(phone_too_long('07123456789'))
        # With Tanzania's code: at most 12 digits; with another code: at most 15
        self.assertFalse(phone_too_long('+255 712 345 678'))
        self.assertFalse(phone_too_long('255712345678'))
        self.assertTrue(phone_too_long('+2557123456789'))
        self.assertFalse(phone_too_long('+447911123456'))


class RegisterAndLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def register(self, **overrides):
        data = {
            'business_name': 'Duka la Amina',
            'first_name': 'Amina',
            'phone': '0754111222',
            'password': 'Mukombozi2026!',
            **overrides,
        }
        return self.client.post('/api/auth/register/', data, format='json')

    def test_register_creates_business_owner_and_trial(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn('access', response.data)
        user = User.objects.get(phone='+255754111222')
        self.assertEqual(user.role, User.Role.OWNER)
        self.assertEqual(user.business.name, 'Duka la Amina')
        self.assertTrue(user.business.subscription.is_valid)

    def test_register_saves_shop_type(self):
        self.register(business_type='hardware')
        user = User.objects.get(phone='+255754111222')
        self.assertEqual(user.business.business_type, 'hardware')
        response = client_for(user).get('/api/auth/me/')
        self.assertEqual(response.data['business']['business_type'], 'hardware')

    def test_register_without_shop_type_uses_other(self):
        self.register()
        self.assertEqual(User.objects.get(phone='+255754111222').business.business_type, 'other')

    def test_register_refuses_unknown_shop_type(self):
        response = self.register(business_type='casino')
        self.assertEqual(response.status_code, 400)
        self.assertIn('business_type', response.data)

    def test_register_refuses_too_long_phone(self):
        response = self.register(phone='07541112223')
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.data)

    def test_duplicate_phone_rejected_in_any_format(self):
        self.register()
        response = self.register(phone='+255 754 111 222')
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.data)

    def test_login_with_different_phone_format(self):
        self.register()
        response = self.client.post(
            '/api/auth/login/', {'phone': '255754111222', 'password': 'Mukombozi2026!'}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['user']['business']['name'], 'Duka la Amina')

    def test_wrong_password_rejected(self):
        self.register()
        response = self.client.post(
            '/api/auth/login/', {'phone': '0754111222', 'password': 'wrong-password'}, format='json'
        )
        self.assertEqual(response.status_code, 401)


class SuperuserLoginTests(TestCase):
    """createsuperuser saves the phone as typed; login must still work in every format."""

    def setUp(self):
        User.objects.create_superuser(phone='0712 345 678', password='Admin2026!', first_name='Admin')

    def test_phone_is_stored_normalized(self):
        self.assertTrue(User.objects.filter(phone='+255712345678').exists())

    def test_api_login_with_local_format(self):
        response = APIClient().post('/api/auth/login/', {'phone': '0712345678', 'password': 'Admin2026!'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def test_admin_login_with_local_format(self):
        response = self.client.post(
            '/admin/login/?next=/admin/', {'username': '0712345678', 'password': 'Admin2026!'}
        )
        self.assertRedirects(response, '/admin/')


class StaffTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()

    def test_owner_adds_staff_who_cannot_manage_staff(self):
        response = client_for(self.owner).post(
            '/api/staff/',
            {'first_name': 'Neema', 'phone': '0655000111', 'password': 'Muuzaji2026!'},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        staff = User.objects.get(phone='+255655000111')
        self.assertEqual(staff.role, User.Role.STAFF)
        self.assertEqual(staff.business, self.business)
        self.assertEqual(client_for(staff).get('/api/staff/').status_code, 403)

    def test_owner_cannot_delete_themselves(self):
        response = client_for(self.owner).delete(f'/api/staff/{self.owner.pk}/')
        self.assertEqual(response.status_code, 404)
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())


@mock.patch.object(password_reset, 'send_sms')
class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()  # resets the request limit between tests
        self.business, self.owner = make_business(phone='+255742000001')
        self.client = APIClient()

    def ask_code(self, phone='0742 000 001'):
        return self.client.post('/api/auth/password-reset/', {'phone': phone}, format='json')

    def sent_code(self, send_sms):
        return send_sms.call_args.args[1].split()[1]

    def confirm(self, code, password='NewPassword2026!', phone='0742000001'):
        return self.client.post(
            '/api/auth/password-reset/confirm/',
            {'phone': phone, 'code': code, 'new_password': password},
            format='json',
        )

    def test_code_by_sms_sets_new_password(self, send_sms):
        self.assertEqual(self.ask_code().status_code, 200)
        send_sms.assert_called_once()
        self.assertEqual(send_sms.call_args.args[0], '+255742000001')
        code = self.sent_code(send_sms)
        self.assertRegex(code, r'^\d{6}$')

        self.assertEqual(self.confirm(code).status_code, 200)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password('NewPassword2026!'))
        # A code works only once
        self.assertEqual(self.confirm(code, password='Another2026!pw').status_code, 400)

    def test_unknown_number_gets_same_answer_and_no_sms(self, send_sms):
        response = self.ask_code('0752999999')
        self.assertEqual(response.status_code, 200)
        send_sms.assert_not_called()

    def test_wrong_code_is_refused_and_locks_after_5_tries(self, send_sms):
        self.ask_code()
        code = self.sent_code(send_sms)
        wrong = f'{(int(code) + 1) % 1_000_000:06d}'
        for _ in range(PasswordResetCode.MAX_ATTEMPTS):
            self.assertEqual(self.confirm(wrong).status_code, 400)
        # Even the right code no longer works
        self.assertEqual(self.confirm(code).status_code, 400)

    def test_expired_code_is_refused(self, send_sms):
        self.ask_code()
        PasswordResetCode.objects.update(created_at=timezone.now() - timedelta(minutes=11))
        self.assertEqual(self.confirm(self.sent_code(send_sms)).status_code, 400)

    def test_new_code_only_after_a_minute(self, send_sms):
        self.ask_code()
        self.ask_code()
        self.assertEqual(send_sms.call_count, 1)
        PasswordResetCode.objects.update(created_at=timezone.now() - timedelta(minutes=2))
        self.ask_code()
        self.assertEqual(send_sms.call_count, 2)

    def test_weak_password_is_refused(self, send_sms):
        self.ask_code()
        response = self.confirm(self.sent_code(send_sms), password='12345678')
        self.assertEqual(response.status_code, 400)
        self.assertIn('new_password', response.data)

    def test_live_site_never_shows_the_code(self, send_sms):
        response = self.ask_code()
        self.assertNotIn('simulated_code', response.data)
        send_sms.assert_called_once()

    @override_settings(DEBUG=True, BEEM_API_KEY='', BEEM_SECRET_KEY='')
    def test_simulation_shows_the_code_instead_of_sending(self, send_sms):
        response = self.ask_code()
        code = response.data['simulated_code']
        self.assertRegex(code, r'^\d{6}$')
        send_sms.assert_not_called()
        self.assertEqual(self.confirm(code).status_code, 200)

    @override_settings(DEBUG=True, BEEM_API_KEY='key', BEEM_SECRET_KEY='secret')
    def test_no_simulation_when_sms_keys_are_set(self, send_sms):
        self.assertNotIn('simulated_code', self.ask_code().data)
        send_sms.assert_called_once()

    def test_sms_failure_is_reported_and_not_counted(self, send_sms):
        from notifications.sms import SMSError

        send_sms.side_effect = SMSError('down')
        self.assertEqual(self.ask_code().status_code, 503)
        self.assertFalse(PasswordResetCode.objects.exists())


class AdminUserFormTests(TestCase):
    def test_admin_made_user_gets_standard_phone_and_can_log_in(self):
        from .admin import UserCreationForm

        form = UserCreationForm(data={
            'phone': '0745 111 222', 'first_name': 'Neema', 'role': 'owner',
            'is_staff': True, 'is_superuser': True,
            'password1': 'Msimamizi2026!', 'password2': 'Msimamizi2026!',
        })
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.phone, '+255745111222')
        self.assertTrue(user.is_superuser)
        response = APIClient().post(
            '/api/auth/login/', {'phone': '0745111222', 'password': 'Msimamizi2026!'}, format='json'
        )
        self.assertEqual(response.status_code, 200)


class ProfilePhotoTests(TestCase):
    # The smallest valid JPEG header bytes are enough: the server checks the type, not the picture
    JPEG = b'\xff\xd8\xff\xe0' + b'\x00' * 100

    def setUp(self):
        self.business, self.owner = make_business()
        self.client = client_for(self.owner)

    def upload(self, data, prefix='data:image/jpeg;base64,'):
        import base64

        return self.client.put('/api/auth/me/photo/', {'image': prefix + base64.b64encode(data).decode()}, format='json')

    def test_upload_show_and_remove(self):
        response = self.upload(self.JPEG)
        self.assertEqual(response.status_code, 200, response.data)
        key = response.data['avatar_key']
        self.assertIsNotNone(key)

        # Anyone with the address can see it (it is shown in <img> tags), with safe headers
        image = APIClient().get(f'/api/avatars/{key}/')
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image['Content-Type'], 'image/jpeg')
        self.assertEqual(image['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(image.content, self.JPEG)

        # A new photo gets a new address; the old one is gone
        new_key = self.upload(self.JPEG + b'\x01').data['avatar_key']
        self.assertNotEqual(new_key, key)
        self.assertEqual(APIClient().get(f'/api/avatars/{key}/').status_code, 404)

        response = self.client.delete('/api/auth/me/photo/')
        self.assertIsNone(response.data['avatar_key'])
        self.assertEqual(APIClient().get(f'/api/avatars/{new_key}/').status_code, 404)

    def test_type_comes_from_the_file_not_the_label(self):
        png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 50
        key = self.upload(png, prefix='data:image/jpeg;base64,').data['avatar_key']
        self.assertEqual(APIClient().get(f'/api/avatars/{key}/')['Content-Type'], 'image/png')

    def test_refuses_svg_and_other_files(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        self.assertEqual(self.upload(svg, prefix='data:image/svg+xml;base64,').status_code, 400)
        self.assertEqual(self.upload(b'<html>hi</html>').status_code, 400)
        self.assertEqual(self.client.put('/api/auth/me/photo/', {'image': 'not a photo'}, format='json').status_code, 400)

    def test_refuses_too_big_photo(self):
        self.assertEqual(self.upload(self.JPEG + b'\x00' * 310 * 1024).status_code, 400)

    def test_must_be_logged_in_to_upload(self):
        self.assertEqual(APIClient().put('/api/auth/me/photo/', {'image': ''}, format='json').status_code, 401)

    def test_email_can_be_added_to_profile(self):
        response = self.client.patch('/api/auth/me/', {'email': 'juma@example.com'}, format='json')
        self.assertEqual(response.data['email'], 'juma@example.com')
        self.assertEqual(self.client.patch('/api/auth/me/', {'email': 'not-an-email'}, format='json').status_code, 400)
