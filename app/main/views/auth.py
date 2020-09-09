# coding: utf-8
from flask_login import current_user
from flask import (
    current_app,
    flash,
    get_flashed_messages,
    Markup,
    redirect,
    request,
    session,
    url_for
)
from flask_login import logout_user, login_user

from dmutils.flask import timed_render_template as render_template
from dmutils.forms.errors import (
    get_errors_from_wtform,
    govuk_errors,
)
from dmutils.user import User
from dmutils.email.helpers import hash_string

from .. import main
from ..forms.auth_forms import LoginForm
from ..helpers.login_helpers import redirect_logged_in_user
from ... import data_api_client


NO_ACCOUNT_MESSAGE = Markup("""Make sure you've entered the right email address and password. Accounts
    are locked after 5 failed attempts. If you’ve forgotten your password you can reset it by clicking
    ‘Forgotten password’.""")


@main.route('/login', methods=["GET"])
def render_login():
    next_url = request.args.get('next')
    if current_user.is_authenticated and not get_flashed_messages():
        return redirect_logged_in_user(next_url)

    form = LoginForm()
    errors = get_errors_from_wtform(form)

    return render_template(
        "auth/login.html",
        form=form,
        errors=errors,
        next=next_url), 200


@main.route('/login', methods=["POST"])
def process_login():
    form = LoginForm()
    next_url = request.args.get('next')
    if form.validate_on_submit():
        user_json = data_api_client.authenticate_user(
            form.email_address.data,
            form.password.data)
        if not user_json:
            current_app.logger.info(
                "login.fail: failed to log in {email_hash}",
                extra={'email_hash': hash_string(form.email_address.data)})
            errors = govuk_errors({
                "email_address": {
                    "message": "Check your email address",
                    "input_name": "email_address",
                },
                "password": {
                    "message": "Check your password",
                    "input_name": "password",
                },
            })
            return render_template(
                "auth/login.html",
                form=form,
                errors=errors,
                next=next_url), 403

        user = User.from_json(user_json)

        login_user(user)
        current_app.logger.info("login.success: role={role} user={email_hash}",
                                extra={'role': user.role, 'email_hash': hash_string(form.email_address.data)})
        return redirect_logged_in_user(next_url)

    else:
        errors = get_errors_from_wtform(form)
        return render_template(
            "auth/login.html",
            form=form,
            errors=errors,
            next=next_url), 400


# We allow logging out via GET request so that we can have a simple link in the
# site header. We would prefer to be able to have a degree of protection
# against inadvertent/malicious logout requests without the user knowing, which
# is why we have used POST previously, but our site header design needs work
# before that can happen.
@main.route('/logout', methods=["GET", "POST"])
def logout():
    session.clear()
    logout_user()
    return redirect(url_for('.render_login'))
