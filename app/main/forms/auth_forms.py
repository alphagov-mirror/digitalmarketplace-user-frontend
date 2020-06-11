from itertools import chain
from pathlib import Path

from flask import current_app
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp, ValidationError

from dmutils.email.helpers import hash_string
from dmutils.forms.fields import DMStripWhitespaceStringField

from app import data_api_client


PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 50


EMAIL_REGEX = r"^[^@^\s]+@[^@^\.^\s]+(\.[^@^\.^\s]+)+$"
EMAIL_LOGIN_HINT = "Enter the email address you used to register with the Digital Marketplace"
PASSWORD_HINT = f"Password must be between {PASSWORD_MIN_LENGTH} and {PASSWORD_MAX_LENGTH} characters"
PASSWORD_LENGTH_ERROR_MESSAGE = f"Enter a password between {PASSWORD_MIN_LENGTH} and {PASSWORD_MAX_LENGTH} characters"
PASSWORD_BLACKLISTED_ERROR_MESSAGE = "Enter a password that is harder to guess"
PHONE_NUMBER_HINT = "If there are any urgent problems with your requirements, we need your phone number so the " \
                    "support team can help you fix them quickly."


class NotInPasswordBlacklist:
    # path, relative to flask app root_path, to look for password blacklist files. all files found here will be read,
    # one password per line
    BLACKLIST_DIR_PATH = "data/password_blacklist"

    @staticmethod
    def _normalized_password(password):
        return password.strip().lower()

    @classmethod
    def _lines_from_filepath(cls, filepath):
        with filepath.open("r", encoding="utf-8") as f:
            # we exclude passwords that can't be used anyway as they fall short of the minimum password length - doing
            # this allows us to keep "original" password lists in the blacklist dir without modification, making them
            # easier to maintain yet still memory-efficient.
            return tuple(
                password
                for password in (cls._normalized_password(line) for line in f)
                if len(password) >= PASSWORD_MIN_LENGTH
            )

    # this value is not populated until first access because construction depends on current_app being available
    _blacklist_set = None

    @classmethod
    def get_blacklist_set(cls):
        # cache blacklist set class-wide
        if cls._blacklist_set is None:
            cls._blacklist_set = frozenset(chain.from_iterable(
                cls._lines_from_filepath(filepath)
                for filepath in (Path(current_app.root_path) / cls.BLACKLIST_DIR_PATH).iterdir()
                if filepath.is_file()
            ))
        return cls._blacklist_set

    def __init__(self, message):
        self.message = message

    def __call__(self, form, field):
        if self._normalized_password(field.data) in self.get_blacklist_set():
            raise ValidationError(self.message)


class LoginForm(FlaskForm):
    email_address = DMStripWhitespaceStringField(
        'Email address', id="input-email_address",
        hint=EMAIL_LOGIN_HINT,
        validators=[
            DataRequired(message="You must provide an email address"),
            Regexp(EMAIL_REGEX,
                   message="You must provide a valid email address")
        ]
    )
    password = PasswordField(
        'Password', id="input-password",
        validators=[
            DataRequired(message="You must provide your password")
        ]
    )


class EmailAddressForm(FlaskForm):
    email_address = DMStripWhitespaceStringField(
        'Email address', id="input-email_address",
        hint=EMAIL_LOGIN_HINT,
        validators=[
            DataRequired(message="You must provide an email address"),
            Regexp(EMAIL_REGEX,
                   message="You must provide a valid email address")
        ]
    )


class MatchesCurrentPassword:
    def __init__(self, message):
        self.message = message

    def __call__(self, form, field):
        user_json = data_api_client.authenticate_user(current_user.email_address, field.data)

        if user_json is None:
            current_app.logger.info("change_password.fail: failed to authenticate user {email_hash}",
                                    extra={'email_hash': hash_string(current_user.email_address)})

            raise ValidationError(self.message)


class PasswordChangeForm(FlaskForm):
    old_password = PasswordField(
        'Old password', id="input-old_password",
        validators=[
            DataRequired(message="You must enter your old password"),
            MatchesCurrentPassword(message="Make sure you’ve entered the right password."),
        ]
    )
    password = PasswordField(
        'New password', id="input-password",
        validators=[
            DataRequired(message="You must enter a new password"),
            Length(
                min=PASSWORD_MIN_LENGTH,
                max=PASSWORD_MAX_LENGTH,
                message=PASSWORD_LENGTH_ERROR_MESSAGE,
            ),
            NotInPasswordBlacklist(message=PASSWORD_BLACKLISTED_ERROR_MESSAGE),
        ]
    )
    confirm_password = PasswordField(
        'Confirm new password', id="input-confirm_password",
        validators=[
            DataRequired(message="Please confirm your new password"),
            EqualTo('password', message="The passwords you entered do not match")
        ]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.password.hint = PASSWORD_HINT


class PasswordResetForm(PasswordChangeForm):
    """
    Subclasses PasswordChangeForm so we can keep validation/password policy in one place
    'Old password' not required for PasswordReset (as the user likely doesn't know it)
    """
    old_password = None


class CreateUserForm(FlaskForm):
    name = DMStripWhitespaceStringField(
        'Your name', id="input-name",
        validators=[
            DataRequired(message="Enter your name"),
            Length(min=1,
                   max=255,
                   message="Your name must be between 1 and 255 characters"
                   )
        ]
    )

    phone_number = StringField(
        'Phone number (optional)', id="input-phone_number",
        validators=[
            Regexp("^$|^\\+?([\\d\\s()-]){9,20}$",
                   message=("Enter a phone number, like 01632 960 001, +44 0808 157 0192 or (020)-7946-0001")
                   )
        ]
    )

    password = PasswordField(
        'Password', id="input-password",
        validators=[
            DataRequired(message="Enter a password"),
            Length(
                min=PASSWORD_MIN_LENGTH,
                max=PASSWORD_MAX_LENGTH,
                message=PASSWORD_LENGTH_ERROR_MESSAGE,
            ),
            NotInPasswordBlacklist(message=PASSWORD_BLACKLISTED_ERROR_MESSAGE),
        ]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.phone_number.hint = PHONE_NUMBER_HINT
        self.password.hint = PASSWORD_HINT
