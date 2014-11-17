#!/usr/bin/env python

import sys
import os
import fuzzy

# patch Django where needed
from mock import patch

# Dynamic imports
import importlib

# use our Django (currently irrelevant)
ourdjango = os.path.dirname(os.path.abspath(__file__)) + '/../../django-concolic'
if ourdjango not in sys.path:
    sys.path.insert(1, ourdjango)

# Mock out force_str and relatives
from django.utils.encoding import force_bytes
class NewForceBytes():
    def __call__(self, s, *args, **kwargs):
        if isinstance(s, fuzzy.concolic_str):
            return s
        return force_bytes(s, *args, **kwargs)

patcher = patch('django.utils.encoding.force_bytes', new_callable=NewForceBytes)
patcher.start()
patcher = patch('django.test.client.force_bytes', new_callable=NewForceBytes)
patcher.start()

# Mock DB queries so they play nicely with concolic execution
import django.db.models.query

notdict = {}
oldget = django.db.models.QuerySet.get
def newget(self, *args, **kwargs):
  import django.contrib.sessions.models
  if self.model is not django.contrib.sessions.models.Session:
    if len(kwargs) == 1:
      key = kwargs.keys()[0]
      if '_' not in key:
        if key == 'pk':
          key = self.model._meta.pk.name
          kwargs[key] = kwargs['pk']
          del kwargs['pk']

        for m in self.model.objects.all():
          if getattr(m, key) == kwargs[key]:
            real = oldget(self, *args, **kwargs)
            assert m == real
            return m

        # this should raise an exception, or we've done something wrong
        oldget(self, *args, **kwargs)
        assert False
      else:
        e = "newget: special keys like %s not yet supported" % key
        if e not in notdict:
          print(e)
        notdict[e] = True
    else:
      e = "newget: multi-key lookups not yet supported: %s" % kwargs
      if e not in notdict:
        print(e)
      notdict[e] = True
  return oldget(self, *args, **kwargs)

django.db.models.QuerySet.get = newget

# Mock requests by mocking routing + url parsing
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
        return SymRequestFactory(self
            , response_handler
            , SERVER_NAME = 'concolic.io'
            )

class SymRequestFactory(RequestFactory):
    def __init__(self, symdjango, start_response, **defaults):
        from django.core.servers.basehttp import get_internal_wsgi_application
        self.symdjango = symdjango
        self.start_response = start_response
        self.handler = get_internal_wsgi_application()
        RequestFactory.__init__(self, **defaults)

    def request(self, **request):
      environ = self._base_environ(**request)
      with patch('django.core.urlresolvers.RegexURLResolver', new=SymResolver) as mock:
        mock.symdjango = self.symdjango
        res = self.handler(environ, self.start_response)
      return res

    def generic(self, method, path, data='',
        content_type='application/octet-stream', secure=False, **extra):
      environ = self._base_environ(PATH_INFO=path, **extra)

      from urlparse import ParseResult
      with patch('django.test.client.urlparse') as mock:
        mock.return_value = ParseResult(
                scheme = environ['wsgi.url_scheme'],
                netloc = environ['SERVER_NAME'],
                path = environ['PATH_INFO'],
                params = '',
                query = 'QUERY_STRING' in environ and environ['QUERY_STRING'] or '',
                fragment = ''
                )
        res = super(SymRequestFactory, self).generic(method, path, data,
            content_type=content_type, secure=secure, **extra)
      return res

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
        return "<reverse: %s>" % v

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
