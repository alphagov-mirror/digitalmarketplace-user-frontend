import urllib

import pytest
import mock
from freezegun import freeze_time

from dmapiclient import HTTPError
from dmutils.email import generate_token

from ...helpers import BaseApplicationTest


class TestCreateUser(BaseApplicationTest):

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.create_user.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    user_roles = ['buyer', 'supplier']

    def _generate_token(self, email_address='test@email.com', role='buyer',
                        supplier_id='12345', supplier_name='Supplier Name'):
        token_data = {
            'role': role,
            'email_address': email_address
        }

        if role == 'buyer':
            token_data.update({
                "phoneNumber": "020-7930-4832"
            })
        elif role == 'supplier':
            token_data.update({
                "supplier_id": supplier_id,
                "supplier_name": supplier_name
            })

        return generate_token(
            token_data,
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['INVITE_EMAIL_SALT']
        )

    def test_should_be_an_error_for_missing_token(self):
        res = self.client.get('/user/create')
        assert res.status_code == 404

    def test_should_be_an_error_for_missing_token_trailing_slash(self):
        res = self.client.get('/user/create/')
        assert res.status_code == 301
        assert res.location == 'http://localhost/user/create'

    def test_should_show_correct_error_page_for_invalid_token(self):
        token = "1234"
        res = self.client.get(
            '/user/create/{}'.format(token)
        )

        assert res.status_code == 400
        assert "The link you used to create an account is not valid." in res.get_data(as_text=True)

    def test_invalid_token_contents_500s(self):
        token = generate_token(
            {
                'this_is_not_expected': 1234
            },
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['INVITE_EMAIL_SALT']
        )

        with pytest.raises(KeyError):
            self.client.get(
                '/user/create/{}'.format(token)
            )

    def test_should_render_correct_error_page_if_token_expired(self):
        messages = [
            'Check you’ve entered the correct link or <a href="/buyers/create">send a new one</a>',
            'Check you’ve entered the correct link or ask the person who invited you to send a new invitation.'
        ]
        for role, message in zip(self.user_roles, messages):
            with freeze_time('2016-09-28 16:00:00'):
                token = self._generate_token(role=role)
            res = self.client.get(
                '/user/create/{}'.format(token)
            )

            assert res.status_code == 400
            assert 'The link you used to create an account may have expired.' in res.get_data(as_text=True)
            assert message in res.get_data(as_text=True)

    def test_should_render_create_user_page_if_user_does_not_exist(self):
        self.data_api_client.get_user.return_value = None
        page_titles = ["Create a new Digital Marketplace account", "Add your name and create a password"]
        button_values = ['Create account'] * 2  # the same for now

        for role, page_title, button_value in zip(self.user_roles, page_titles, button_values):
            token = self._generate_token(role=role)
            res = self.client.get(
                '/user/create/{}'.format(token)
            )
            assert res.status_code == 200

            for message in [
                page_title,
                button_value,
                "test@email.com",
                '<form autocomplete="off" action="/user/create/%s" method="POST" id="createUserForm">'
                    % urllib.parse.quote(token)
            ]:
                assert message in res.get_data(as_text=True)

    def test_should_render_an_error_if_already_registered_as_a_buyer(self):
        error_messages = [
            'Account already exists',
            'The details you provided are registered with another supplier.'
        ]
        for role, error_message in zip(self.user_roles, error_messages):
            self.data_api_client.get_user.return_value = self.user(
                123,
                'test@email.com',
                1 if role == 'supplier' else None,
                'Supplier name' if role == 'supplier' else None,
                'Users name'
            )

            token = self._generate_token(role=role)
            res = self.client.get(
                '/user/create/{}'.format(token),
                follow_redirects=True
            )

            assert res.status_code == 400
            assert error_message in res.get_data(as_text=True)

    def test_should_return_an_error_if_already_registered_as_a_supplier(self):
        page_headings = [
            'Your email address is already registered as an account with ‘Supplier’.',
            'The details you provided are registered with another supplier.'
        ]
        for role, heading in zip(self.user_roles, page_headings):
            self.data_api_client.get_user.return_value = self.user(
                999,
                'test@email.com',
                1234,
                'Supplier',
                'Different users name'
            )

            token = self._generate_token(role=role)
            res = self.client.get(
                '/user/create/{}'.format(token)
            )
            assert res.status_code == 400
            assert heading in res.get_data(as_text=True)

    def test_should_return_an_error_if_already_registered_as_an_admin(self):
        for role in self.user_roles:
            self.data_api_client.get_user.return_value = self.user(
                123,
                'test@email.com',
                None,
                None,
                'Users name',
                role='admin'
            )

            token = self._generate_token(role=role)
            res = self.client.get(
                '/user/create/{}'.format(token)
            )

            assert res.status_code == 400
            assert "Account already exists" in res.get_data(as_text=True)

    def test_should_return_an_error_with_locked_message_if_user_is_locked(self):
        for role in self.user_roles:
            self.data_api_client.get_user.return_value = self.user(
                123,
                'test@email.com',
                1 if role == 'supplier' else None,
                'Supplier name' if role == 'supplier' else None,
                'Users name',
                locked=True
            )

            token = self._generate_token(role=role)
            res = self.client.get(
                '/user/create/{}'.format(token)
            )

            assert res.status_code == 400
            assert "Your account has been locked" in res.get_data(as_text=True)

    def test_should_return_an_error_with_inactive_message_if_user_is_not_active(self):
        for role in self.user_roles:
            self.data_api_client.get_user.return_value = self.user(
                123,
                'test@email.com',
                1 if role == 'supplier' else None,
                'Supplier name' if role == 'supplier' else None,
                'Users name',
                active=False
            )

            token = self._generate_token(role=role)
            res = self.client.get(
                '/user/create/{}'.format(token)
            )

            assert res.status_code == 400
            assert "Your account has been deactivated" in res.get_data(as_text=True)

    def test_should_return_an_error_with_wrong_supplier_message_if_invited_by_wrong_supplier(self):
        self.data_api_client.get_user.return_value = self.user(
            123,
            'test@email.com',
            1234,
            'Supplier Name',
            'Users name'
        )

        token = self._generate_token(
            role='supplier',
            supplier_id=9999,
            supplier_name='Different Supplier Name',
            email_address='different_supplier@email.com'
        )

        res = self.client.get(
            '/user/create/{}'.format(token)
        )

        assert res.status_code == 400
        assert u"You were invited by ‘Different Supplier Name’" in res.get_data(as_text=True)
        assert u"Your account is registered with ‘Supplier Name’" in res.get_data(as_text=True)

    def test_should_render_correct_error_page_for_old_style_expired_buyer_token(self):
        with freeze_time('2016-09-28 16:00:00'):
            token = generate_token(
                {"email_address": 'test@example.com'},
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

        res = self.client.get(
            '/user/create/{}'.format(token)
        )

        assert res.status_code == 400

        messages = [
            'The link you used to create an account may have expired.',
            'Check you’ve entered the correct link or <a href="/buyers/create">send a new one</a>'
        ]

        for message in messages:
            assert message in res.get_data(as_text=True)

    def test_should_render_correct_error_page_for_old_style_expired_supplier_token(self):
        with freeze_time('2016-09-28 16:00:00'):
            token = generate_token(
                {
                    "supplier_id": '12345',
                    "supplier_name": 'Supplier Name',
                    "email_address": 'test@example.com'
                },
                self.app.config['SHARED_EMAIL_KEY'],
                self.app.config['INVITE_EMAIL_SALT']
            )

        res = self.client.get(
            '/user/create/{}'.format(token)
        )

        assert res.status_code == 400

        messages = [
            'The link you used to create an account may have expired.',
            'Check you’ve entered the correct link or ask the person who invited you to send a new invitation.'
        ]

        for message in messages:
            assert message in res.get_data(as_text=True)


class TestSubmitCreateUser(BaseApplicationTest):

    user_roles = ['buyer', 'supplier']

    def setup_method(self, method):
        super().setup_method(method)
        self.data_api_client_patch = mock.patch('app.main.views.create_user.data_api_client', autospec=True)
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def _generate_token(self, email_address='test@email.com', role='buyer'):
        token_data = {
            'role': role,
            'email_address': email_address
        }

        if role == 'buyer':
            token_data.update({
                "phoneNumber": "020-7930-4832"
            })
        elif role == 'supplier':
            token_data.update({
                "supplier_id": '12345'
            })

        return generate_token(
            token_data,
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['INVITE_EMAIL_SALT']
        )

    def test_should_fail_if_incorrect_role_param(self):
        token = self._generate_token()
        res = self.client.post(
            '/user/create-notathing/{}'.format(token)
        )
        assert res.status_code == 404

    def test_should_be_an_error_if_invalid_token(self):
        res = self.client.post(
            '/user/create/invalidtoken',
            data={
                'password': '123456789',
                'name': 'name',
                'email_address': 'valid@test.com'
            }
        )

        assert res.status_code == 400
        assert 'Bad request - Digital Marketplace' in res.get_data(as_text=True)
        assert "The link you used to create an account is not valid." in res.get_data(as_text=True)

    def test_should_be_a_bad_request_if_token_expired(self):
        for role in self.user_roles:
            with freeze_time('2016-09-28 16:00:00'):
                token = self._generate_token(role='buyer')
            res = self.client.post(
                '/user/create/{}'.format(token)
            )

            assert res.status_code == 400
            assert 'The link you used to create an account may have expired.' in res.get_data(as_text=True)

    def test_should_be_an_error_if_missing_name_and_password(self):
        validation_messages = ["You must enter a name", "You must enter a password"]

        for role in self.user_roles:
            token = self._generate_token(role=role)
            res = self.client.post(
                '/user/create/{}'.format(token),
                data={}
            )

            assert res.status_code == 400
            for message in validation_messages:
                assert message in res.get_data(as_text=True)

    def test_should_be_an_error_if_too_short_name_and_password(self):
        validation_messages = ["You must enter a name", "Passwords must be between 10 and 50 characters"]

        for role in self.user_roles:
            token = self._generate_token(role=role)
            res = self.client.post(
                '/user/create/{}'.format(token),
                data={
                    'password': "123456789",
                    'name': ""
                }
            )

            assert res.status_code == 400
            for message in validation_messages:
                assert message in res.get_data(as_text=True)

    def test_should_be_an_error_if_too_long_name_and_password(self):
        page_headings = [
            "Create a new Digital Marketplace account",
            "Add your name and create a password"
        ]
        for role, page_heading in zip(self.user_roles, page_headings):
            token = self._generate_token(role=role)
            twofiftysix = "a" * 256
            fiftyone = "a" * 51

            res = self.client.post(
                '/user/create/{}'.format(token),
                data={
                    'password': fiftyone,
                    'name': twofiftysix
                }
            )
            assert res.status_code == 400
            for message in [
                page_heading,
                "Names must be between 1 and 255 characters",
                "Passwords must be between 10 and 50 characters",
                "test@email.com"
            ]:
                assert message in res.get_data(as_text=True)

    def test_should_create_buyer_user_if_user_does_not_exist(self):
        self.data_api_client.create_user.return_value = {
            "users": {
                "id": "1234",
                "emailAddress": "test@email.com",
                "name": "valid name",
                "role": "buyer"
            }
        }
        self.data_api_client.get_user.return_value = None

        token = self._generate_token(role='buyer')
        res = self.client.post(
            '/user/create/{}'.format(token),
            data={
                'password': 'validpassword',
                'name': 'valid name',
                'phone_number': '020-7930-4832'
            }
        )

        self.data_api_client.create_user.assert_called_once_with({
            'role': 'buyer',
            'password': 'validpassword',
            'emailAddress': 'test@email.com',
            'phoneNumber': '020-7930-4832',
            'name': 'valid name'
        })

        assert res.status_code == 302
        assert res.location == 'http://localhost/'
        self.assert_flashes('/?account-created=true', 'track-page-view')

    def test_should_create_suplier_user_if_user_does_not_exist(self):
        self.data_api_client.create_user.return_value = {
            "users": {
                "id": "1234",
                "emailAddress": "test@email.com",
                "name": "valid name",
                "role": "supplier",
                "supplier": {
                    "supplierId": "12345",
                    "name": "Valid supplier"
                }
            }
        }
        token = self._generate_token(role='supplier')

        res = self.client.post(
            '/user/create/{}'.format(token),
            data={
                'password': 'validpassword',
                'name': 'valid name'
            }
        )

        self.data_api_client.create_user.assert_called_once_with({
            'role': 'supplier',
            'password': 'validpassword',
            'emailAddress': 'test@email.com',
            'name': 'valid name',
            'supplierId': '12345'
        })

        assert res.status_code == 302
        assert res.location == 'http://localhost/suppliers'
        self.assert_flashes('/suppliers?account-created=true', 'track-page-view')

    def test_should_return_an_error_if_buyer_user_exists(self):
        self.data_api_client.create_user.side_effect = HTTPError(mock.Mock(status_code=409))

        token = self._generate_token(role='buyer')
        res = self.client.post(
            '/user/create/{}'.format(token),
            data={
                'password': 'validpassword',
                'phone_number': '020-7930-4832',
                'name': 'valid name'
            }
        )

        self.data_api_client.create_user.assert_called_once_with({
            'role': 'buyer',
            'password': 'validpassword',
            'emailAddress': 'test@email.com',
            'phoneNumber': '020-7930-4832',
            'name': 'valid name'
        })

        assert res.status_code == 400

    def test_should_return_an_error_if_supplier_user_exists(self):
        self.data_api_client.create_user.side_effect = HTTPError(mock.Mock(status_code=409))

        token = self._generate_token(role='supplier')
        res = self.client.post(
            '/user/create/{}'.format(token),
            data={
                'password': 'validpassword',
                'name': 'valid name'
            }
        )

        self.data_api_client.create_user.assert_called_once_with({
            'role': 'supplier',
            'password': 'validpassword',
            'emailAddress': 'test@email.com',
            'name': 'valid name',
            'supplierId': '12345'
        })

        assert res.status_code == 400

    def test_should_create_buyer_user_if_no_phone_number(self):
        self.data_api_client.create_user.return_value = {
            "users": {
                "id": "1234",
                "emailAddress": "test@email.com",
                "name": "valid name",
                "role": "buyer",
            }
        }

        token = self._generate_token(role='buyer')
        res = self.client.post(
            '/user/create/{}'.format(token),
            data={
                'password': 'validpassword',
                'name': 'valid name',
                'phone_number': None
            }
        )

        self.data_api_client.create_user.assert_called_once_with({
            'role': 'buyer',
            'password': 'validpassword',
            'emailAddress': 'test@email.com',
            'phoneNumber': '',
            'name': 'valid name'
        })

        assert res.status_code == 302
        assert res.location == 'http://localhost/'

    def test_should_return_an_error_if_bad_phone_number(self):

        token = self._generate_token(role='buyer')
        res = self.client.post(
            '/user/create/{}'.format(token),
            data={
                'password': 'validpassword',
                'name': 'valid name',
                'phone_number': 'Not a number'
            }
        )

        assert res.status_code == 400

    def test_should_strip_whitespace_surrounding_create_user_name_field(self):
        self.data_api_client.create_user.return_value = {
            "users": {
                "id": "1234",
                "emailAddress": "test@email.com",
                "name": "valid name",
                "role": "buyer",
            }
        }
        self.data_api_client.get_user.return_value = None
        token = self._generate_token(role='buyer')
        self.client.post(
            '/user/create/{}'.format(token),
            data={
                'password': 'validpassword',
                'name': '  valid name  ',
                'phone_number': '020-7930-4832'
            }
        )

        self.data_api_client.create_user.assert_called_once_with({
            'role': 'buyer',
            'password': 'validpassword',
            'emailAddress': 'test@email.com',
            'phoneNumber': '020-7930-4832',
            'name': 'valid name'
        })

    def test_should_not_strip_whitespace_surrounding_create_user_password_field(self):
        self.data_api_client.create_user.return_value = {
            "users": {
                "id": "1234",
                "emailAddress": "test@email.com",
                "name": "valid name",
                "role": "buyer",
            }
        }
        token = self._generate_token(role='buyer')
        self.client.post(
            '/user/create/{}'.format(token),
            data={
                'password': '  validpassword  ',
                'name': 'valid name  ',
                'phone_number': '020-7930-4832'

            }
        )

        self.data_api_client.create_user.assert_called_once_with({
            'role': 'buyer',
            'password': '  validpassword  ',
            'emailAddress': 'test@email.com',
            'name': 'valid name',
            'phoneNumber': '020-7930-4832',
        })

    def test_should_be_a_503_if_api_fails(self):
        self.data_api_client.create_user.side_effect = HTTPError("bad email")

        token = self._generate_token(role='buyer')
        res = self.client.post(
            '/user/create/{}'.format(token),
            data={
                'password': 'validpassword',
                'name': 'valid name'
            }
        )
        assert res.status_code == 503

    def test_should_render_error_page_if_invalid_buyer_domain(self):
        self.data_api_client.create_user.side_effect = HTTPError(
            mock.Mock(status_code=400), message='invalid_buyer_domain'
        )

        token = self._generate_token(role='buyer')
        res = self.client.post(
            '/user/create/{}'.format(token),
            data={
                'password': 'validpassword',
                'phone_number': '020-7930-4832',
                'name': 'valid name'
            }
        )

        assert res.status_code == 400
        assert 'You must use a public sector email address' in res.get_data(as_text=True)
