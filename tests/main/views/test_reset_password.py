import mock
import pytest
from lxml import html, cssselect

from dmutils.email import generate_token
from dmutils.email.exceptions import EmailError
from dmtestutils.comparisons import AnyStringMatching

from ...helpers import BaseApplicationTest, MockMatcher

from app.main.views import reset_password

EMAIL_EMPTY_ERROR = "You must provide an email address"
EMAIL_INVALID_ERROR = "You must provide a valid email address"

PASSWORD_INVALID_LENGTH_ERROR = "Passwords must be between 10 and 50 characters"
PASSWORD_INVALID_BLACKLISTED_ERROR = "Your password must be hard to guess"
PASSWORD_MISMATCH_ERROR = "The passwords you entered do not match"
NEW_PASSWORD_EMPTY_ERROR = "You must enter a new password"
NEW_PASSWORD_CONFIRM_EMPTY_ERROR = "Please confirm your new password"
PASSWORD_RESET_EMAIL_ERROR = "Try again later."
PASSWORD_CHANGE_AUTH_ERROR = "Make sure you’ve entered the right password."
PASSWORD_CHANGE_EMAIL_ERROR = "Failed to send password change alert."
PASSWORD_CHANGE_UPDATE_ERROR = "Could not update password due to an error."

PASSWORD_CHANGE_SUCCESS_MESSAGE = "You have successfully changed your password."


class TestSendResetPasswordEmail(BaseApplicationTest):

    _user = None
    expected_email_hash = '8yc90Y2VvBnVHT5jVuSmeebxOCRJcnKicOe7VAsKu50='

    def setup_method(self, method):
        super().setup_method(method)

        data_api_client_config = {'get_user.return_value': self.user(
            123, "email@email.com", 1234, 'name', 'Name'
        )}

        self._user = {
            "user": 123,
            "email": 'email@email.com',
        }

        self.data_api_client_patch = mock.patch(
            'app.main.views.reset_password.data_api_client', **data_api_client_config
        )
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_email_should_not_be_empty(self):
        res = self.client.post("/user/reset-password", data={})
        content = self.strip_all_whitespace(res.get_data(as_text=True))
        assert res.status_code == 400
        assert self.strip_all_whitespace(EMAIL_EMPTY_ERROR) in content

    def test_email_should_be_valid(self):
        res = self.client.post("/user/reset-password", data={
            'email_address': 'invalid'
        })
        content = self.strip_all_whitespace(res.get_data(as_text=True))
        assert res.status_code == 400
        assert self.strip_all_whitespace(EMAIL_INVALID_ERROR) in content

    @pytest.mark.parametrize("user_role", (
        "admin",
        "admin-ccs-category",
        "admin-ccs-sourcing",
        "admin-ccs-data-controller",
        "admin-framework-manager",
        "buyer",
        "supplier",
    ))
    @mock.patch('app.main.views.reset_password.DMNotifyClient.send_email')
    def test_reset_password_request_redirects_to_same_page_and_shows_flash_message(self, send_email, user_role):
        self.data_api_client.get_user.return_value = self.user(
            123, "email@email.com", 1234, "Ahoy", name="Bob", role=user_role,
        )

        res = self.client.post("/user/reset-password", data={
            'email_address': 'email@email.com'
        }, follow_redirects=True)

        assert res.status_code == 200
        content = self.strip_all_whitespace(res.get_data(as_text=True))
        assert self.strip_all_whitespace("we'll send a link to reset the password") in content
        assert send_email.call_args_list == [mock.call(
            'email@email.com',
            personalisation={'url': AnyStringMatching(r"http://localhost/user/reset-password/*")},
            reference="reset-password-{}".format(self.expected_email_hash),
            template_name_or_id=self.app.config['NOTIFY_TEMPLATES']['reset_password']
        )]

    @mock.patch('app.main.views.reset_password.DMNotifyClient.send_email')
    def test_nonexistent_account_sends_email_to_sandbox_address(self, send_email):
        self.data_api_client.get_user.return_value = None

        with mock.patch('app.main.views.reset_password.current_app') as current_app_mock:
            res = self.client.post("/user/reset-password", data={
                'email_address': 'email@email.com'
            })

        assert res.status_code == 302
        self.assert_flashes("we'll send a link to reset the", expected_category='message')
        assert send_email.call_args_list == [mock.call(
            reset_password.NOTIFY_SANDBOX_ADDRESS,
            reference="reset-password-nonexistent-user-{}".format(self.expected_email_hash),
            template_name_or_id=current_app_mock.config['NOTIFY_TEMPLATES']['reset_password_inactive']
        )]
        assert current_app_mock.logger.info.call_args_list == [mock.call(
            '{code}: Sent password (non-)reset email for invalid user email_hash {email_hash}',
            extra={
                'email_hash': self.expected_email_hash,
                'code': 'login.reset-email.invalid-email'
            }
        )]

    @mock.patch('app.main.views.reset_password.DMNotifyClient.send_email')
    def test_should_strip_whitespace_surrounding_reset_password_email_address_field(self, send_email):
        self.client.post("/user/reset-password", data={
            'email_address': ' email@email.com'
        })
        self.data_api_client.get_user.assert_called_with(email_address='email@email.com')
        assert send_email.call_args_list == [mock.call(
            'email@email.com',
            personalisation={'url': AnyStringMatching(r"http://localhost/user/reset-password/*")},
            reference="reset-password-{}".format(self.expected_email_hash),
            template_name_or_id=self.app.config['NOTIFY_TEMPLATES']['reset_password']
        )]

    @mock.patch('app.main.helpers.logging_helpers.current_app')
    @mock.patch('app.main.views.reset_password.DMNotifyClient.send_email')
    def test_should_be_an_error_if_send_email_fails_for_real_user(self, send_email, current_app):
        send_email.side_effect = EmailError(Exception('Notify API is down'))

        res = self.client.post(
            '/user/reset-password',
            data={'email_address': 'email@email.com'}
        )

        assert res.status_code == 503
        assert PASSWORD_RESET_EMAIL_ERROR in res.get_data(as_text=True)

        assert current_app.logger.error.call_args_list == [mock.call(
            '{code}: {email_type} email for email_hash {email_hash} failed to send. Error: {error}',
            extra={
                'email_hash': self.expected_email_hash,
                'error': 'Notify API is down',
                'code': 'login.reset-email.notify-error',
                'email_type': "Password reset"
            }
        )]

    @mock.patch('app.main.helpers.logging_helpers.current_app')
    @mock.patch('app.main.views.reset_password.DMNotifyClient.send_email')
    def test_should_be_an_error_if_send_email_fails_for_nonexistent_user(self, send_email, current_app):
        send_email.side_effect = EmailError(Exception('Notify API is down'))
        self.data_api_client.get_user.return_value = None

        res = self.client.post(
            '/user/reset-password',
            data={'email_address': 'email@email.com'}
        )

        assert res.status_code == 503
        assert PASSWORD_RESET_EMAIL_ERROR in res.get_data(as_text=True)

        assert current_app.logger.error.call_args_list == [mock.call(
            '{code}: {email_type} email for email_hash {email_hash} failed to send. Error: {error}',
            extra={
                'email_hash': self.expected_email_hash,
                'error': 'Notify API is down',
                'code': 'login.reset-email-nonexistent.notify-error',
                'email_type': "Password reset (non-existent user)"
            }
        )]

    @mock.patch('app.main.views.reset_password.DMNotifyClient.send_email', autospec=True)
    def test_inactive_user_attempts_password_reset(self, send_email):
        self.data_api_client.get_user.return_value = self.user(
            123, "email@email.com", 1234, 'email', 'Name', active=False,
        )
        res = self.client.post(
            '/user/reset-password',
            data={'email_address': 'email@email.com'}
        )

        assert res.status_code == 302
        # Asserting the whole flash message is a bit messy due to line breaks
        self.assert_flashes("we'll send a link to reset the", expected_category='message')
        assert send_email.call_args_list == [mock.call(
            mock.ANY,  # self
            "email@email.com",
            template_name_or_id=self.app.config['NOTIFY_TEMPLATES']['reset_password_inactive'],
            reference="reset-password-inactive-{}".format(self.expected_email_hash),
        )]

    @mock.patch('app.main.helpers.logging_helpers.current_app')
    @mock.patch('app.main.views.reset_password.DMNotifyClient.send_email', autospec=True)
    def test_should_be_an_error_if_send_email_fails_for_inactive_user(self, send_email, current_app):
        send_email.side_effect = EmailError(Exception('Notify API is down'))
        self.data_api_client.get_user.return_value = self.user(
            123, "email@email.com", 1234, 'email', 'Name', active=False,
        )
        res = self.client.post(
            '/user/reset-password',
            data={'email_address': 'email@email.com'}
        )

        assert res.status_code == 503
        assert PASSWORD_RESET_EMAIL_ERROR in res.get_data(as_text=True)

        assert current_app.logger.error.call_args_list == [mock.call(
            '{code}: {email_type} email for email_hash {email_hash} failed to send. Error: {error}',
            extra={
                'email_hash': self.expected_email_hash,
                'error': 'Notify API is down',
                'code': 'login.reset-email-inactive.notify-error',
                'email_type': "Password reset (inactive user)"
            }
        )]

    @mock.patch("app.main.views.reset_password.DMNotifyClient.send_email", autospec=True)
    def test_admin_manager_does_not_get_reset_email(self, send_email):
        self.data_api_client.get_user.return_value = self.user(
            123, "email@email.com", name="Eve", role="admin-manager",
            supplier_id=None, supplier_name=None,
        )
        res = self.client.post(
            "/user/reset-password",
            data={"email_address": "email@email.com"}
        )

        # to prevent revealing email addresses for admins we still show the usual result
        assert res.status_code == 302
        self.assert_flashes("we'll send a link to reset the", expected_category='message')
        assert send_email.call_args_list == []


class TestResetPassword(BaseApplicationTest):
    _user = None

    def setup_method(self, method):
        super().setup_method(method)

        data_api_client_config = {'get_user.return_value': self.user(
            123, "email@email.com", 1234, 'name', 'Name'
        )}

        self._user = {
            "user": 123,
            "email": 'email@email.com',
        }

        self.data_api_client_patch = mock.patch(
            'app.main.views.reset_password.data_api_client', **data_api_client_config
        )
        self.data_api_client = self.data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        super().teardown_method(method)

    def test_email_should_be_decoded_from_token(self):
        token = generate_token(
            self._user,
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['RESET_PASSWORD_SALT'])
        url = '/user/reset-password/{}'.format(token)

        res = self.client.get(url)
        assert res.status_code == 200
        assert "Reset password for email@email.com" in res.get_data(as_text=True)

        # Reset form should not display the 'Old password' field
        document = html.fromstring(res.get_data(as_text=True))
        form_labels = document.xpath('//main//form//label/text()')

        for label in ['New password', 'Confirm new password']:
            assert label in form_labels
        assert self.data_api_client.update_user_password.called is False

    def test_password_should_not_be_empty(self):
        token = generate_token(
            self._user,
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['RESET_PASSWORD_SALT'])
        url = '/user/reset-password/{}'.format(token)

        res = self.client.post(url, data={
            'password': '',
            'confirm_password': ''
        })
        assert res.status_code == 400
        assert NEW_PASSWORD_EMPTY_ERROR in res.get_data(as_text=True)
        assert NEW_PASSWORD_CONFIRM_EMPTY_ERROR in res.get_data(as_text=True)
        assert self.data_api_client.update_user_password.called is False

    def test_password_should_be_over_ten_chars_long(self):
        token = generate_token(
            self._user,
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['RESET_PASSWORD_SALT'])
        url = '/user/reset-password/{}'.format(token)

        res = self.client.post(url, data={
            'password': '123456789',
            'confirm_password': '123456789'
        })
        assert res.status_code == 400
        assert PASSWORD_INVALID_LENGTH_ERROR in res.get_data(as_text=True)
        assert self.data_api_client.update_user_password.called is False

    @pytest.mark.parametrize("bad_password", ("digitalmarketplace", "dIgItAlMaRkEtPlAcE", "1234567890"))
    def test_password_should_not_be_in_blacklist(self, bad_password):
        token = generate_token(
            self._user,
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['RESET_PASSWORD_SALT'])
        url = '/user/reset-password/{}'.format(token)

        res = self.client.post(url, data={
            'password': bad_password,
            'confirm_password': bad_password,
        })
        assert res.status_code == 400
        assert PASSWORD_INVALID_BLACKLISTED_ERROR in res.get_data(as_text=True)
        assert self.data_api_client.update_user_password.called is False

    def test_password_should_be_under_51_chars_long(self):
        token = generate_token(
            self._user,
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['RESET_PASSWORD_SALT'])
        url = '/user/reset-password/{}'.format(token)

        res = self.client.post(url, data={
            'password':
                '123456789012345678901234567890123456789012345678901',
            'confirm_password':
                '123456789012345678901234567890123456789012345678901'
        })
        assert res.status_code == 400
        assert PASSWORD_INVALID_LENGTH_ERROR in res.get_data(as_text=True)
        assert self.data_api_client.update_user_password.called is False

    def test_passwords_should_match(self):
        token = generate_token(
            self._user,
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['RESET_PASSWORD_SALT'])
        url = '/user/reset-password/{}'.format(token)

        res = self.client.post(url, data={
            'password': 'password12345',
            'confirm_password': 'o123456789'
        })
        assert res.status_code == 400
        assert PASSWORD_MISMATCH_ERROR in res.get_data(as_text=True)
        assert self.data_api_client.update_user_password.called is False

    def test_redirect_to_login_page_on_success(self):
        token = generate_token(
            self._user,
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['RESET_PASSWORD_SALT'])
        url = '/user/reset-password/{}'.format(token)

        res = self.client.post(url, data={
            'password': 'password12345',
            'confirm_password': 'password12345'
        })
        assert res.status_code == 302
        assert res.location == 'http://localhost/user/login'
        res = self.client.get(res.location)

        assert reset_password.PASSWORD_UPDATED_MESSAGE in res.get_data(as_text=True)
        self.data_api_client.update_user_password.assert_called_with(
            self._user.get('user'), 'password12345', self._user.get('email'))

    def test_password_change_unknown_failure(self):
        self.data_api_client.update_user_password.return_value = False
        token = generate_token(
            self._user,
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['RESET_PASSWORD_SALT'])
        url = '/user/reset-password/{}'.format(token)

        res = self.client.post(url, data={
            'password': 'password12345',
            'confirm_password': 'password12345'
        })
        assert res.status_code == 302
        assert res.location == 'http://localhost/user/login'
        res = self.client.get(res.location)

        assert reset_password.PASSWORD_NOT_UPDATED_MESSAGE in res.get_data(as_text=True)
        self.data_api_client.update_user_password.assert_called_with(
            self._user.get('user'), 'password12345', self._user.get('email'))

    def test_should_not_strip_whitespace_surrounding_reset_password_password_field(self):
        token = generate_token(
            self._user,
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['RESET_PASSWORD_SALT'])
        url = '/user/reset-password/{}'.format(token)

        self.client.post(url, data={
            'password': '  password12345',
            'confirm_password': '  password12345'
        })
        self.data_api_client.update_user_password.assert_called_with(
            self._user.get('user'), '  password12345', self._user.get('email'))

    def test_token_created_before_last_updated_password_cannot_be_used(self):
        self.data_api_client.get_user.return_value = self.user(
            123, "email@email.com", 1234, 'email', 'Name', is_token_valid=False
        )
        token = generate_token(
            self._user,
            self.app.config['SHARED_EMAIL_KEY'],
            self.app.config['RESET_PASSWORD_SALT'])
        url = '/user/reset-password/{}'.format(token)

        res = self.client.post(url, data={
            'password': 'password12345',
            'confirm_password': 'password12345'
        }, follow_redirects=True)

        assert res.status_code == 200
        document = html.fromstring(res.get_data(as_text=True))
        error_selector = cssselect.CSSSelector('div.banner-destructive-without-action')
        error_elements = error_selector(document)
        assert len(error_elements) == 1
        assert reset_password.EXPIRED_PASSWORD_RESET_TOKEN_MESSAGE in error_elements[0].text_content()
        assert self.data_api_client.update_user_password.called is False


class TestChangePassword(BaseApplicationTest):

    _user = None

    def setup_method(self, method):
        super().setup_method(method)

        data_api_client_config = {'get_user.return_value': self.user(
            123, "email@email.com", 1234, 'name', 'Name'
        )}
        auth_forms_extra_data_api_client_config = {
            'authenticate_user.return_value': self.user(
                123, "email@email.com", 1234, 'Supplier Name', 'Name', role='supplier')
        }

        self._user = {
            "user": 123,
            "email": 'email@email.com',
        }

        self.data_api_client_patch = mock.patch(
            'app.main.views.reset_password.data_api_client', **data_api_client_config
        )
        self.data_api_client = self.data_api_client_patch.start()

        self.auth_forms_data_api_client_patch = mock.patch(
            'app.main.forms.auth_forms.data_api_client', **data_api_client_config,
            **auth_forms_extra_data_api_client_config
        )
        self.auth_forms_data_api_client = self.auth_forms_data_api_client_patch.start()

    def teardown_method(self, method):
        self.data_api_client_patch.stop()
        self.auth_forms_data_api_client.stop()
        super().teardown_method(method)

    @pytest.mark.parametrize(
        'user_role, redirect_url',
        [('buyer', '/buyers'), ('supplier', '/suppliers'), ('admin', '/admin')]
    )
    def test_change_password_page_displays_correctly(self, user_role, redirect_url):
        if user_role == 'buyer':
            self.login_as_buyer()
        elif user_role == 'admin':
            self.login_as_admin()
        else:
            self.login_as_supplier()
        response = self.client.get('/user/change-password')

        assert response.status_code == 200
        document = html.fromstring(response.get_data(as_text=True))

        self.assert_breadcrumbs(response, [("Your account", redirect_url), ("Change your password", None)])

        form_labels = document.xpath('//form//label/text()')

        for label in ['Old password', 'New password', 'Confirm new password']:
            assert label in form_labels

        assert len(document.xpath('//a[text()="Return to your account"]')) == 1
        assert self.data_api_client.update_user_password.called is False

    @pytest.mark.parametrize(
        'user_role, redirect_url, user_email',
        [
            ('buyer', '/buyers', 'buyer@email.com'),
            ('supplier', '/suppliers', 'email@email.com'),
            ('admin', '/admin', 'admin@email.com')
        ]
    )
    @pytest.mark.parametrize(
        "old_password",
        (
            "password12345",
            # test that changing from an invalid "old password" to a valid new one is allowed
            "3nf9s",
            "digitalmarketplace",
        ),
    )
    @mock.patch('app.main.views.reset_password.DMNotifyClient.send_email', autospec=True)
    def test_user_can_change_password(self, send_email, user_role, redirect_url, user_email, old_password):
        if user_role == 'buyer':
            self.login_as_buyer()
        elif user_role == 'admin':
            self.login_as_admin()
        else:
            self.login_as_supplier()
        response = self.client.post(
            '/user/change-password',
            data={
                'old_password': old_password,
                'password': 'o987654321',
                'confirm_password': 'o987654321'
            }
        )
        assert response.status_code == 302
        assert response.location == 'http://localhost{}'.format(redirect_url)

        self.data_api_client.update_user_password.assert_called_once_with(123, 'o987654321', updater=user_email)
        self.assert_flashes(PASSWORD_CHANGE_SUCCESS_MESSAGE)

        send_email.assert_called_once_with(
            mock.ANY,  # self
            user_email,
            template_name_or_id=self.app.config['NOTIFY_TEMPLATES']['change_password_alert'],
            personalisation={
                'url': MockMatcher(lambda x: '/user/reset-password/gAAAA' in x),
            },
            reference=MockMatcher(lambda x: 'change-password-alert' in x)
        )

    def test_old_password_needs_to_match_user_password(self):
        self.login_as_supplier()
        self.auth_forms_data_api_client.authenticate_user.return_value = None
        response = self.client.post(
            '/user/change-password',
            data={
                'old_password': 'o987654321',
                'password': 'password12345',
                'confirm_password': 'password12345'
            }
        )
        assert self.strip_all_whitespace(PASSWORD_CHANGE_AUTH_ERROR) \
            in self.strip_all_whitespace(response.get_data(as_text=True))
        assert response.status_code == 400
        assert self.data_api_client.update_user_password.called is False

    def test_new_password_should_be_over_ten_chars_long(self):
        self.login_as_supplier()
        response = self.client.post(
            '/user/change-password',
            data={
                'old_password': 'password12345',
                'password': 'o9876',
                'confirm_password': 'o9876'
            }
        )
        assert response.status_code == 400
        assert PASSWORD_INVALID_LENGTH_ERROR in response.get_data(as_text=True)
        assert self.data_api_client.update_user_password.called is False

    @pytest.mark.parametrize("bad_password", ("digitalmarketplace", "dIgItAlMaRkEtPlAcE", "1234567890"))
    def test_new_password_shouldnt_be_in_blacklist(self, bad_password):
        self.login_as_supplier()
        response = self.client.post(
            '/user/change-password',
            data={
                'old_password': 'password12345',
                'password': bad_password,
                'confirm_password': bad_password,
            }
        )
        assert response.status_code == 400
        assert PASSWORD_INVALID_BLACKLISTED_ERROR in response.get_data(as_text=True)
        assert self.data_api_client.update_user_password.called is False

    def test_password_should_be_under_51_chars_long(self):
        self.login_as_supplier()
        response = self.client.post(
            '/user/change-password',
            data={
                'old_password': 'password12345',
                'password': 'o' * 51,
                'confirm_password': 'o' * 51
            }
        )
        assert response.status_code == 400
        assert PASSWORD_INVALID_LENGTH_ERROR in response.get_data(as_text=True)
        assert self.data_api_client.update_user_password.called is False

    def test_passwords_should_match(self):
        self.login_as_supplier()
        response = self.client.post(
            '/user/change-password',
            data={
                'old_password': 'password12345',
                'password': 'o987654321',
                'confirm_password': 'password12345'
            }
        )
        assert response.status_code == 400
        assert PASSWORD_MISMATCH_ERROR in response.get_data(as_text=True)
        assert self.data_api_client.update_user_password.called is False

    def test_user_must_be_logged_in_to_change_password(self):
        response = self.client.post(
            '/user/change-password',
            data={
                'old_password': 'password12345',
                'password': 'o987654321',
                'confirm_password': 'o987654321'
            }
        )
        assert response.status_code == 302
        assert response.location == 'http://localhost/user/login?next=%2Fuser%2Fchange-password'
        assert self.data_api_client.update_user_password.called is False

    def test_update_password_failure_redirects_and_shows_flashed_error_message(self):
        self.login_as_supplier()
        self.data_api_client.update_user_password.return_value = None
        response = self.client.post(
            '/user/change-password',
            data={
                'old_password': 'password12345',
                'password': 'o987654321',
                'confirm_password': 'o987654321'
            }
        )
        assert response.status_code == 302
        assert response.location == 'http://localhost/suppliers'
        self.assert_flashes(PASSWORD_CHANGE_UPDATE_ERROR, 'error')
        self.data_api_client.update_user_password.assert_called_once_with(
            123,
            'o987654321',
            updater=self._user.get('email'),
        )

    @mock.patch('app.main.helpers.logging_helpers.current_app')
    @mock.patch('app.main.views.reset_password.DMNotifyClient.send_email')
    def test_should_log_an_error_and_redirect_if_change_password_email_sending_fails(self, send_email, current_app):
        self.login_as_supplier()
        send_email.side_effect = EmailError(Exception('Notify API is down'))

        response = self.client.post(
            '/user/change-password',
            data={
                'old_password': 'password12345',
                'password': 'o987654321',
                'confirm_password': 'o987654321'
            }
        )

        assert response.status_code == 302
        assert response.location == 'http://localhost/suppliers'
        self.assert_flashes(PASSWORD_CHANGE_SUCCESS_MESSAGE)

        assert current_app.logger.error.call_args_list == [
            mock.call(
                '{code}: {email_type} email for email_hash {email_hash} failed to send. Error: {error}',
                extra={
                    'email_hash': '8yc90Y2VvBnVHT5jVuSmeebxOCRJcnKicOe7VAsKu50=',
                    'error': 'Notify API is down',
                    'code': 'login.password-change-alert-email.notify-error',
                    'email_type': "Password change alert"
                }
            )
        ]

        # the email failure shouldn't have prevented the password from being changed though
        self.data_api_client.update_user_password.assert_called_once_with(
            123,
            'o987654321',
            updater=self._user.get('email'),
        )
