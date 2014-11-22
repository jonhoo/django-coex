#!/usr/bin/env python2

# Verbosity of output
# 0 = errors and test results only
# 1 = access log, response status, concrete values
# 2 = branch conditions, response headers
# 3 = branch stacks, response bodies
verbose = 1

import os
import re
import symex.fuzzy as fuzzy
import __builtin__
import inspect
import symex.importwrapper as importwrapper
import symex.rewriter as rewriter

importwrapper.rewrite_imports(rewriter.rewriter)

from symex.symdjango import SymDjango, post_data
import symex.symsql
import symex.symeval

app = "zoobar"
appviews = {
        "zapp": {
            "index": (lambda p: p == "/"),
            "users": (lambda p: p == "users/"),
            "transfer": (lambda p: p == "transfer/")
        },
        "zlogio": {
            "login": (lambda p: p == "accounts/login/"),
            "logout": (lambda p: p == "accounts/logout/"),
        },
        "": {}
}

d = SymDjango(app, os.path.abspath(os.path.dirname(__file__) + '/app'), appviews)

# Only safe to load now that it's been patched and added to import path
import zoobar

def report_balance_mismatch():
  print("WARNING: Balance mismatch detected")

def report_zoobar_theft():
  print("WARNING: Zoobar theft detected")

def adduser(username):
  from django.contrib.auth.models import User
  from django.contrib.auth import authenticate
  u = User.objects.create_user(username, '', 'password')
  u.save()
  return u

# TODO(jon): This currently only test single-request actions
def test_stuff():
  method = fuzzy.mk_str('method')
  if not method == 'get' and not method == 'post':
    return

  req = d.new()

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
  path = fuzzy.mk_str('path') + '/'
  if path[0] == '/':
    return

  data = {}
  if method == 'post':
    if path == 'transfer/':
      data = post_data(
        zoobars = fuzzy.mk_int('transfer.zoobars'),
        recipient = fuzzy.mk_str('transfer.recipient')
      )

  logged_in = False
  user = fuzzy.mk_str('user')
  if user == 'alice' or user == 'bob':
      if verbose > 0:
        print('==> accessing %s as %s' % (path, user))

      if user == 'alice':
          req.login(username='alice', password='password')
      elif user == 'bob':
          req.login(username='bob', password='password')

      logged_in = True
  else:
      if verbose > 0:
        print('==> accessing %s anonymously' % path)

  response = None
  if method == 'get':
    response = req.get(path)
  elif method == 'post':
    response = req.post(path, data=data)

  if verbose == 1 and response.status_code == 404:
    print(" -> 404 not found...")
  elif verbose == 1:
    print(' -> %d %s' % (response.status_code, response.reason_phrase))
  elif verbose > 1:
    print(' -> %d %s\n -> %s' % (
      response.status_code,
      response.reason_phrase,
      response.items())
      )

  if verbose > 2 or response.status_code == 500:
    print(80 * "-")
    print(re.sub("^", "\t", response.content))
    print(80 * "-")

  if logged_in and path == "transfer/":
      if "Log out" in response.content:
          print(" -> login works. that's nice.")
      else:
          print(" -> login doesn't work :(")

      if method == "post":
        if "warning" in response.content:
          # success is also notified using a warning span
          wtext = re.search('<span class="warning">([^<]*)</span>', response.content).group(1)
          print(" -> transfer warning: %s" % wtext)
        else:
          print(" -> NO TRANSFER WARNING?!")
          print(80 * "-")
          print(re.sub("^", "\t", response.content))
          print(80 * "-")

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

fuzzy.concolic_test(test_stuff, maxiter=2000, verbose=verbose)
