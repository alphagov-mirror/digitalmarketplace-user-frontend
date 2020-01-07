describe("GOVUK.Analytics", function () {
  var analytics;

  beforeEach(function () {
    window.ga = function() {};
    spyOn(window, 'ga');
  });

  describe('when initialised', function () {

    it('should initialise pageviews, events, track external links and virtual pageviews', function () {
      spyOn(window.GOVUK.GDM.analytics, 'register');
      spyOn(window.GOVUK.GDM.analytics.pageViews, 'init');
      spyOn(window.GOVUK.GDM.analytics.events, 'init');
      spyOn(window.GOVUK.GDM.analytics.trackExternalLinks, 'init');

      window.GOVUK.GDM.analytics.init();

      expect(window.GOVUK.GDM.analytics.register).toHaveBeenCalled();
      expect(window.GOVUK.GDM.analytics.pageViews.init).toHaveBeenCalled();
      expect(window.GOVUK.GDM.analytics.events.init).toHaveBeenCalled();
      expect(window.GOVUK.GDM.analytics.trackExternalLinks.init).toHaveBeenCalled();
    });
  });

  describe('when registered', function() {
    var universalSetupArguments;

    beforeEach(function() {
      GOVUK.GDM.analytics.init();
      universalSetupArguments = window.ga.calls.allArgs();
    });

    it('configures a universal tracker', function() {
      expect(universalSetupArguments).toContain(['create', 'UA-49258698-1', {
        'cookieDomain': document.domain
      }]);
      expect(universalSetupArguments).toContain(['send', 'pageview']);
    });
    it('configures a cross domain tracker', function() {
      expect(universalSetupArguments).toContain(['create', 'UA-145652997-1', 'auto', {
        'name': 'govuk_shared'
      }]);
      expect(universalSetupArguments).toContain(['require', 'linker']);
      expect(universalSetupArguments).toContain(['govuk_shared.require', 'linker']);
      expect(universalSetupArguments).toContain(['linker:autoLink', [ 'www.gov.uk' ]]);
      expect(universalSetupArguments).toContain(['govuk_shared.linker:autoLink', [ 'www.gov.uk' ]]);
      expect(universalSetupArguments).toContain(['govuk_shared.set', 'anonymizeIp', true ]);
      expect(universalSetupArguments).toContain(['govuk_shared.send', 'pageview']);
    });
  });

});
