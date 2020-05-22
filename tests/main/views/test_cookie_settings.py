# coding: utf-8
from lxml import html

from ...helpers import BaseApplicationTest


class TestCookieSettings(BaseApplicationTest):
    def test_cookie_settings_page(self):
        res = self.client.get('/user/cookie-settings')
        assert res.status_code == 200

        document = html.fromstring(res.get_data(as_text=True))
        assert len(document.xpath('//h1[contains(text(), "Change your cookie settings")]')) == 1
        assert len(document.xpath("//form//input[@name='cookies-analytics']")) == 2
        assert len(document.xpath('//form//button[contains(text(), "Save cookie settings")]')) == 1

        # Alert banners - visibility determined by cookies/JS
        alerts = document.xpath('//div[@data-module="dm-alert"]//h2')
        assert [alert.text_content().strip() for alert in alerts] == [
            "Your cookie settings were saved",
            "Your cookie settings have not yet been saved"
        ]

        assert len(document.xpath('//*[@id="error-summary-title"][contains(text(),'
                                  '"There was a problem saving your settings")]')) == 1

        # 'Go back' link should default to the home page
        assert document.xpath("//a[@class='govuk-link dm-cookie-settings__prev-page']")[0].get('href').strip() == '/'
