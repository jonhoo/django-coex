#!/usr/bin/env python2

# Verbosity of output
# 0 = errors and test results only
# 1 = access log, response status, concrete values
# 2 = branch conditions, response headers
# 3 = branch stacks, response bodies
verbose = 1

import os
import re
import sys
import symex.fuzzy as fuzzy
import __builtin__
import inspect

import sys
sys.path.append("../gradapply")

settings = "settings.eecs"
os.environ.update({
  "DJANGO_SETTINGS_MODULE": settings
})
from symex.symdjango import SymDjango, post_data
import symex.symeval

paths = ["/", "apply/", "review/", "apply/login/", "apply/help/", "apply/page/recrequest"]
appviews = {
	"apply.main.main": (lambda p: p == "/"),
	"apply.main.main": (lambda p: p == "apply/"), 
	"apply.readers_folderlist.list_assignedfolders" : (lambda p: p == "review/"), 
        "apply.login.applylogin" : (lambda p : p == "apply/login/"),
        "apply.help.help": (lambda p: p == "apply/help/"),
	"apply.recs.recrequest": (lambda p: p == "apply/page/recrequest/")
        #"apply.submit.submit": (lambda p: p == "apply/submit/"),
	#"apply.receipt.receipt": (lambda p: p == "apply/receipt/"),
	#"apply.submit.submit": (lambda p: p == "apply/csr/"),
	#"apply.submit.notify1": (lambda p: p == "apply/csr-notify1/"),
	#"apply.submit.notify2": (lambda p: p == "apply/csr-notify2/"),
        #"apply.recommenders.recommenders": (lambda p: p == "apply/page/recommenders/"),
	#"apply.subjects.subjects": (lambda p: p == "apply/page/subjects/"),
	#"apply.recs.recrequest": (lambda p: p == "apply/page/recrequest/"),
	#"apply.attended.attended": (lambda p: p == "apply/page/attended/"),
	#TODO: add more
}

d = SymDjango(settings, os.path.abspath(os.path.dirname(__file__) + '../gradapply'), appviews)

from django.test import TestCase
from django.test.utils import setup_test_environment
# Only safe to load now that it's been patched and added to import path
import apply


# TODO(jon): This currently only test single-request actions
from django.core.management import call_command
class ConcolicTestCase():
  fixtures = ['../gradapply/apply/fixtures/testdb/login_user.xml', '../gradapply/apply/fixtures/testdb/login_conf.xml', '../gradapply/apply/fixtures/testdb/review_reader.xml']
  
  def test_stuff(self):
    for fixture in self.fixtures:
      call_command('loaddata', fixture, verbosity=0)
    
    method = fuzzy.mk_str('method')
    if not method == 'get' and not method == 'post':
      return

    req = d.new()
 
    ## In two cases, we over-restrict the inputs in order to reduce the
    ## number of paths that "make check" explores, so that it finishes
    ## in a reasonable amount of time.  You could pass unconstrained
    ## concolic values for both REQUEST_METHOD and PATH_INFO, but then
    ## zoobar generates around 2000 distinct paths, and that takes many
    ## minutes to check.
    path = fuzzy.mk_str('path') + '/'

    if not path in paths:
      return

    data = {}
    if method == 'post':
      if path == 'apply/login/':
        choice = fuzzy.mk_int("login_choice")
	if choice == 0: #register
          pwd = fuzzy.mk_str('apply.login.password')
          data = post_data(
            username = fuzzy.mk_str('apply.login.username'),
            password1 = pwd,
            password2 = pwd,
            create = ''
          )
        else: #login
          data = post_data(
            username = fuzzy.mk_str('apply.login.username'),
            password = fuzzy.mk_str('apply.login.password')
          )

    logged_in = False
    ok = True
    user = fuzzy.mk_str('user')
    if user == 'eval-kaashoek' or user == 'apply-abarry':
      if verbose > 0:
        print('==> accessing %s as %s' % (path, user))

      if user == 'eval-kaashoek':
          ok = req.login(username='eval-kaashoek', password='yyy')
      elif user == 'apply-abarry':
          ok = req.login(username='apply-abarry', password='yyy')

      logged_in = True
    else:
      if verbose > 0:
        print('==> accessing %s anonymously' % path)
    if (logged_in and ok):
      print(" Login successful") 
    if (logged_in and not ok):
      print(" Login unsuccesful")
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

setup_test_environment()

from django.test.simple import DjangoTestSuiteRunner
olddb = DjangoTestSuiteRunner().setup_databases()
print "Finished setting up database"
concolic_test = ConcolicTestCase()
fuzzy.concolic_test(concolic_test.test_stuff, maxiter=2000, v=verbose,
                    uniqueinputs = True,
                    removeredundant = True,
                    usecexcache = True)

DjangoTestSuiteRunner().teardown_databases(olddb)

