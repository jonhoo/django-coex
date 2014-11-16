#!/usr/bin/env python

# name of app being mocked
app = "zoobar"

# route matches module.view if [module][view] lambda returns true
appviews = {
        "zapp": {
            "index": (lambda p: p == "/")
        },
        "zlogio": {
            "login": (lambda p: p == "/accounts/login/"),
            "logout": (lambda p: p == "/accounts/logout/"),
        },
        "": {}
}

import sys
import os

# search for modules inside application under test
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/app')

# use our Django (currently irrelevant)
sys.path.insert(1, os.path.dirname(os.path.abspath(__file__)) + '/../django-concolic')

# patch Django where needed
from unittest.mock import patch

# Dynamic imports
import importlib

# Various items needed to invoke Django directly
from django.core.urlresolvers import ResolverMatch, Resolver404, NoReverseMatch
from django.core.handlers.wsgi import WSGIRequest
from django.core.servers.basehttp import get_internal_wsgi_application
from django.conf import settings
from django.test.client import FakePayload, RequestFactory

# Make sure Django reads the correct settings
os.environ.update({
    "DJANGO_SETTINGS_MODULE": "app." + app + ".settings"
})

class SymURL():
    def __init__(self, mod, v):
        self.mod = mod
        self.view = v

    @property
    def callback(self):
        global appviews
        return appviews[self.mod][self.view]

    def resolve(self, path):
        if self.callback(path):
            print("%s matches against %s.%s" % (path, self.mod, self.view))
            kwargs = {
                    # named groups in url
                    }

            if kwargs:
                args = ()
            else:
                args = [] # unnamed args in url

            kwargs.update({}) # extra args passed to view from urls.py
            views = importlib.import_module(self.mod + '.views')
            return ResolverMatch(getattr(views, self.view), args, kwargs, self.view)

class SymResolver():
    def __init__(self, regex, conf):
        self.mod = ""

    def setMod(self, mod):
        self.mod = mod

    def resolve(self, path):
        print("resolving path '%s'" % path)
        for m in appviews:
            for v in appviews[m]:
                s = SymURL(m, v)
                r = s.resolve(path)
                if r is not None:
                    return r

        raise Resolver404({'path': path})

    def _reverse_with_prefix(self, v, _prefix, *args, **kwargs):
        return "/"

    @property
    def namespace_dict(self):
        global reverseDict
        return reverseDict

    @property
    def app_dict(self):
        return {}

reverseDict = {}
for m in appviews:
    s = SymResolver("", None)
    s.setMod(m)
    reverseDict[m] = ("", s)

class SymRequestFactory(RequestFactory):
    def __init__(self, start_response, **defaults):
        self.start_response = start_response
        RequestFactory.__init__(self, *defaults)

    def request(self, **request):
        handler = get_internal_wsgi_application()
        with patch('django.core.urlresolvers.RegexURLResolver', new=SymResolver) as urlmock:
            return handler(self._base_environ(**request), start_response)

def start_response(status, response_headers):
    print("\n%18s: %s" % ("RESULT", status))
    print("%18s: %s" % ("------", "--------------"))
    for h, v in response_headers:
        print("%18s: %s" % (h, v))
    print("")

f = open('result.html', 'wb')
req = SymRequestFactory(start_response)
body = req.get('/accounts/login/')
for c in body:
    f.write(c)
body.close()
f.close()
