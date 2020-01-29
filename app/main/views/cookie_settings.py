# coding: utf-8
from .. import main
from dmutils.flask import timed_render_template as render_template


@main.route('/cookie-settings', methods=["GET"])
def cookie_settings():
    # Preferences saved client side as cookies, so no POST required
    return render_template('cookies/cookie_settings.html')
