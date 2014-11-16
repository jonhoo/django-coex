#!/usr/bin/env python

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/app')
sys.path.insert(1, os.path.dirname(os.path.abspath(__file__)) + '/../django-concolic')

import importlib
from django.core.urlresolvers import ResolverMatch, Resolver404, RegexURLResolver
from django.core.handlers.wsgi import WSGIRequest
from django.core.servers.basehttp import get_internal_wsgi_application
from django.conf import settings
from django.test.client import FakePayload, RequestFactory

app = "zoobar"
appviews = {
        "zapp": {
            "index": (lambda p: p == "/")
        },
        "zlogio": {
            "login": (lambda p: p == "accounts/login/"),
            "logout": (lambda p: p == "accounts/logout/"),
            }

        }
reverse = {
        "zapp": {
            "index": "/"
        },
        "": {
            "login": "/accounts/login/",
            "logout": "/accounts/logout/"
        },
}

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

class SymNS():
    def __init__(self, m):
        self.mod = m
        RegexURLResolver.__init__(self, "^$", app + ".urls", namespace=self.mod)

    def __repr__(self):
        return str("SymNS for %s" % self.mod)

    def resolve(self, path):
        print("%s resolving %s" % (self.mod, path))
        if self.mod == "app":
            print("hmm")
            return None

        for v in appviews[self.mod]:
            s = SymURL(self.mod, v)
            r = s.resolve(path)
            if r is not None:
                return r

    @property
    def handles_namespace(self):
        return self.mod

    @property
    def handles_reverse(self):
        global reverse
        if self.mod in reverse:
            return reverse[self.mod].keys()
        return []

    def handle_reverse(self, v):
        return self._reverse_with_prefix(v, '')

    def _reverse_with_prefix(self, v, _prefix, *args, **kwargs):
        global reverse

        print("looking up reverse for '%s' using namespace '%s'" % (v, self.mod))
        if self.mod in reverse and v in reverse[self.mod]:
            return reverse[self.mod][v]

        raise NoReverseMatch("Reverse for '%s' with arguments '%s' and keyword "
                + "arguments '%s' not found." % (v, args, kwargs))

syms = []
for m in appviews:
    syms.append(SymNS(m))
syms.append(SymNS(""))

class SymWSGIRequest(WSGIRequest):
    def __init__(self, environ):
        WSGIRequest.__init__(self, environ)

    @property
    def urlpatterns(self):
        global syms
        return syms

    @property
    def urlconf(self):
        return self

    def _reverse_with_prefix(self, *args, **kwargs):
        print("asked to do something")


class SymRequestFactory(RequestFactory):
    def __init__(self, start_response, **defaults):
        self.start_response = start_response
        RequestFactory.__init__(self, *defaults)

    def request(self, **request):
        handler = get_internal_wsgi_application()
        handler.request_class = SymWSGIRequest
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
