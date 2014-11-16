#!/usr/bin/env python

import sys
import os

# patch Django where needed
from mock import patch

# Dynamic imports
import importlib

# use our Django (currently irrelevant)
ourdjango = os.path.dirname(os.path.abspath(__file__)) + '/../../django-concolic'
if ourdjango not in sys.path:
    sys.path.insert(1, ourdjango)

from django.test.client import RequestFactory

# It's only safe to use SymDjango as a singleton!
class SymDjango():
    def __init__(self, app, path, viewmap):
        self.app = app
        self.path = path
        self.viewmap = viewmap

        # search for modules inside application under test
        sys.path.append(path)

        # Make sure Django reads the correct settings
        os.environ.update({
            "DJANGO_SETTINGS_MODULE": app + ".settings"
        })

    def new(self, response_handler):
        return SymRequestFactory(self, response_handler)

class SymRequestFactory(RequestFactory):
    def __init__(self, symdjango, start_response, **defaults):
        from django.core.servers.basehttp import get_internal_wsgi_application
        self.symdjango = symdjango
        self.start_response = start_response
        self.handler = get_internal_wsgi_application()
        RequestFactory.__init__(self, *defaults)

    def request(self, **request):
        with patch('django.core.urlresolvers.RegexURLResolver', new=SymResolver) as urlmock:
            urlmock.symdjango = self.symdjango
            return self.handler(self._base_environ(**request), self.start_response)

class SymResolver():
    symdjango = None

    def __init__(self, regex, conf):
        self.reverseDict = {}
        for m in SymResolver.symdjango.viewmap:
            self.reverseDict[m] = ("", self)

    def resolve(self, path):
        from django.core.urlresolvers import Resolver404
        for m in SymResolver.symdjango.viewmap:
            for v in SymResolver.symdjango.viewmap[m]:
                s = SymURL(SymResolver.symdjango, m, v)
                r = s.resolve(path)
                if r is not None:
                    return r

        raise Resolver404({'path': path})

    def _reverse_with_prefix(self, v, _prefix, *args, **kwargs):
        return "/"

    @property
    def namespace_dict(self):
        return self.reverseDict

    @property
    def app_dict(self):
        return {}

class SymURL():
    def __init__(self, symdjango, mod, v):
        self.symdjango = symdjango
        self.mod = mod
        self.view = v

    @property
    def callback(self):
        return self.symdjango.viewmap[self.mod][self.view]

    def resolve(self, path):
        from django.core.urlresolvers import ResolverMatch
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
