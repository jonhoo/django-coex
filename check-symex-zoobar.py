#!/usr/bin/env python2

verbose = False

import os
import symex.fuzzy as fuzzy
import __builtin__
import inspect
import symex.importwrapper as importwrapper
import symex.rewriter as rewriter

importwrapper.rewrite_imports(rewriter.rewriter)

from symex.symdjango import SymDjango
import symex.symsql
import symex.symeval

# to patch urlparse
from mock import patch

app = "zoobar"
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

def startresp(status, headers):
  if verbose:
    print('startresp', status, headers)

d = SymDjango(app, os.path.abspath(os.path.dirname(__file__) + '/app'), appviews)

# Only safe to load now that it's been patched and added to import path
import zoobar
from django.utils.encoding import force_bytes

def report_balance_mismatch():
  print("WARNING: Balance mismatch detected")

def report_zoobar_theft():
  print("WARNING: Zoobar theft detected")

def adduser(username):
  from django.contrib.auth.models import User
  from django.contrib.auth import authenticate
  u = User.objects.create_user(username, '', 'password')
  u.save()
  return authenticate(username=username, password='password')

# TODO(jon): This currently only test single-request actions
def test_stuff():
  req = d.new(startresp)

  from django.contrib.auth.models import User
  User.objects.all().delete()
  alice = adduser('alice')
  bob = adduser('bob')
  balance1 = sum([u.person.zoobars for u in User.objects.all()])

  from zapp.models import Transfer
  Transfer.objects.all().delete()

  ## In two cases, we over-restrict the inputs in order to reduce the
  ## number of paths that "make check" explores, so that it finishes
  ## in a reasonable amount of time.  You could pass unconstrained
  ## concolic values for both REQUEST_METHOD and PATH_INFO, but then
  ## zoobar generates around 2000 distinct paths, and that takes many
  ## minutes to check.
  path = '/trans' + fuzzy.mk_str('path')
  if '//' in path or '\n' in path:
    ## Don't bother trying to construct paths with lots of slashes;
    ## otherwise, the lstrip() code generates lots of paths..
    return

  from django.contrib.auth import login
  from django.http import HttpRequest
  from django.contrib.sessions.middleware import SessionMiddleware
  user = fuzzy.mk_str('user')
  request = HttpRequest()
  session = SessionMiddleware()
  session.process_request(request)
  logged_in = False
  if user == 'alice':
      print('accessing %s as alice' % path)
      login(request, alice)
      logged_in = True
  elif user == 'bob':
      print('accessing %s as bob' % path)
      login(request, bob)
      logged_in = True

  from urlparse import ParseResult
  with patch('django.test.client.urlparse') as mock:
      mock.return_value = ParseResult(
              scheme = 'http',
              netloc = 'testserver',
              path = path,
              params = '',
              query = '',
              fragment = ''
              )

      if logged_in:
          from django.http import SimpleCookie
          from django.conf import settings
          c = SimpleCookie()
          c[settings.SESSION_COOKIE_NAME] = request.session.session_key

          resp = req.get(path
              , HTTP_COOKIE  = c.output(header='', sep='; ')
              )
      else:
          print('accessing %s anonymously' % path)
          resp = req.get(path)

  if verbose:
    for x in resp:
      print(x)

  if User.objects.all().count() == 2:
    balance2 = sum([u.person.zoobars for u in User.objects.all()])
    if balance1 != balance2:
      report_balance_mismatch()

  utransfers = [t.sender.user.username for t in Transfer.objects.all()]
  for p in User.objects.all():
    if p.username not in utransfers:
      if p.person.zoobars < 10:
        report_zoobar_theft()
        # technically, this check could be fooled if an attacker could insert
        # rows into the transfer db. Instead, we should keep a log of all
        # requests, and which user the request was issued as, but this seems
        # outside the scope of the exercise?

class NewForceBytes():
    def __call__(self, s, *args, **kwargs):
        if isinstance(s, fuzzy.concolic_str):
            return s
        return force_bytes(s, *args, **kwargs)

with patch('django.utils.encoding.force_bytes', new_callable=NewForceBytes) as bmock:
    with patch('django.test.client.force_bytes', new_callable=NewForceBytes) as bmock:
        fuzzy.concolic_test(test_stuff, maxiter=2000, verbose=0)
