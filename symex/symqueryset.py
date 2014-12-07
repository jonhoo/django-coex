from django.db.models import Manager
from django.db.models.query import QuerySet
from django.utils import six
from django.db.models import Model
from django.db import IntegrityError

from random import randrange

from fuzzy import ast, sym_eq, sym_not, sym_or, sym_and, sym_gt, sym_lt, concolic_int

import fuzzy
import traceback
import base64
import string

class SymMixin():
  def _old_get(self, cls, *args, **kwargs):
    return super(cls, self).get(*args, **kwargs)


# SymQuerySet that creates concolic variables from DB object fields. Example:
# - user = User.objects.get(username='alice') will return an object 
# where user.person.zoobars and the other fields are concolic
# - z3 solves constraints and finds concrete values to test
# - Concrete values are then included in the query: 
#   user = User.objects.get(username='alice', person.zoobars=1)
# - If no such user exists, create it
# This makes it possible to test branches that would not otherwise be covered
# when there are no objects in the DB with the required fields. But it makes it
# more difficult to test invariants since the DB will change
class SQLSymQuerySet(QuerySet, SymMixin):
  cache = {},
  _id = 0

  def get(self, *args, **kwargs):
    import django.contrib.sessions.models
    if self.model is django.contrib.sessions.models.Session or len(kwargs) != 1:
      return self._old_get(SQLSymQuerySet, *args, **kwargs)

    #key = kwargs.keys()[0]
    #if '_' in key:
      #return self._old_get(*args, **kwargs)
    
    #if key == 'pk':
      #key = self.model._meta.pk.name
      #kwargs[key] = kwargs['pk']
      #del kwargs['pk']

    ##m = self._get_random_object()
    #for m in self.model.objects.all():
      #v = kwargs[key]

      ## support model attribute passthrough
      #if isinstance(v, Model) and hasattr(v, key):
        #v = getattr(v, key)

      #if getattr(m, key) == v:
        #pass

    # If this query has already been called, some or all of its object's 
    # properties may be symbolic and have constraints
    query_id = self._create_query_id()

    # Get any concrete values that are available for this query
    index = len(query_id)
    concrete = {}
    for id in fuzzy.concrete_values:
      if not id.startswith(query_id):
        continue

      concrete[id[index:]] = fuzzy.concrete_values[id]


    if len(concrete) > 0:
      for field in concrete:
        kwargs[field] = concrete[field]

    unique = self._get_unique_fields()

    try:
      obj = self._old_get(SQLSymQuerySet, *args, **kwargs)
    except self.model.DoesNotExist:
      # Django does not allow empty strings in 'unique' fields
      for field in unique:
        if field.name in kwargs and kwargs[field.name] == '':
          raise self.model.DoesNotExist()

      # If searching by primary key and a row exists, update the row
      # to avoid errors with duplicate primary keys
      obj = None
      for field in unique:
        if field.name in kwargs:
          #newkwargs = {field.name: kwargs[field.name]}
          #obj = self._old_get(SQLSymQuerySet, *args, **newkwargs)
          if obj is not None:
            break

      if obj is None: 
        obj = self.model()
        obj.save()
        setattr(obj, self.model._meta.pk.name, hash(str(self._id)))
        self._id = self._id + 1

      for arg in kwargs:
        if arg != self.model._meta.pk.name:
          setattr(obj, arg, kwargs[arg])

      try:
        print obj
        print self.all()
        obj.save()
      except IntegrityError:
        raise self.model.DoesNotExist()

    obj = self._make_fields_concolic(query_id, obj)
    return obj 

  def _get_unique_fields(self):
    return [f for f in self.model._meta.fields if f.unique]

  def _make_fields_concolic(self, query_id, obj, blacklist = set(), prefix = ''):
    blacklist.add('_' + type(obj)._meta.model_name + '_cache')
    for prop in vars(obj):
      # Ignore private fields
      if (prop.startswith('_') and not prop.endswith('_cache')) or prop in blacklist:
        continue

      value = getattr(obj, prop)
      if isinstance(value, fuzzy.concolic_int) or isinstance(value, fuzzy.concolic_str):
        continue

      if hasattr(value, '__dict__'):
        setattr(obj, prop, self._make_fields_concolic(query_id, value, blacklist, type(value)._meta.model_name))

      if isinstance(value, int):
        setattr(obj, prop, fuzzy.mk_int(query_id + prefix + '__' + prop, value))
      elif isinstance(value, str) or isinstance(value, unicode):
        setattr(obj, prop, fuzzy.mk_str(query_id + prefix + '__' + prop, value))

    return obj

  # Each SymQuerySet has a unique ID based on where it was created (i.e. call
  # stack contents when it was created)
  def _create_query_id(self):
    return base64.b64encode(str(hash(''.join(traceback.format_stack()))))

  # If the query returns DoesNotExist, then it is probably the case that we are
  # looking up the DB with an empty key (e.g. at the beginning of testing when 
  # 'username' has a default value of ''), so we create a synthetic branch to
  # ensure that on a subsequent iteration we actually get a real object
  def _create_synthetic_branch(self, **kwargs):
    obj = self._get_random_object() 
    for obj in self.model.objects.all():
      if len(kwargs) == 1:
        key = kwargs.keys()[0]

        if key == 'pk':
          key = self.model._meta.pk.name
          kwargs[key] = kwargs['pk']
          del kwargs['pk']

        value = kwargs[key]

        if isinstance(value, Model) and hasattr(value, key):
          value = getattr(value, key)

        if getattr(obj, key) == value:
          pass

  def _get_random_object(self):
    return self.model.objects.all()[randrange(self.count())]

  def _exists(self, query_id):
    return query_id in self.cache

  def _add_query_constraints(self):
    pass


# SymQuerySet that creates mutations based on ConSMutate
class MutationSymQuerySet(QuerySet, SymMixin):
  operators = ['lte', 'gte', 'gt', 'lt', 'exact']

  def filter(self, *args, **kwargs):
    (op, value, mutations) = self._mutate(*args, **kwargs)
    actual = self._apply_filter(*args, **kwargs)

    self.test(op, value)
    if isinstance(value, concolic_int):
      mutations = self._remove_dead_mutations(actual, mutations)
      self._create_constraints(op, value, mutations)
    return actual

  def test(self, op, value):
    import pdb; pdb.set_trace()
    if op == 'gt':
      if value > value:
        pass
    elif op == 'lt':
      if value < value:
        pass
    elif op == 'exact':
      if value == value:
        pass

  def _apply_filter(self, *args, **kwargs):
    from django.core.exceptions import FieldError
    try:
      return super(SymQuerySet, self).filter(*args, **kwargs)
    except FieldError: 
      return None

  #
  # Based on ConSMutate: SQL mutants for guiding concolic testing of database 
  # applications (T. Sarkar, S. Basu, and J.S. Wong, 2012)
  #
  # Mutate the current queryset when it is filtered
  #
  # Suppose the filter is Transfer.objects.filter(zoobars__gt=10) (all 
  # transfers of more than 10 zoobars)
  #
  # 1. Split the input string: filter_column = zoobars, operator = gt,
  # filter_value = 10
  # 2. Create possible mutations:
  #   i. Create mutated querysets by varying the 'operator', e.g. create 
  #      querysets with operator = 'lt' (less than), 'gte' (greater than or
  #      equal), etc.
  #   ii.Should end up with several mutations: e.g. 
  #      Transfer.objects.filter(zoobars__lt=10), 
  #      Transfer.objects.filter(zoobars__gte=10), etc.
  # 3. Run original filter
  # 4. For each mutation: 
  #   i. Run it and compare with original
  #   ii.If result is different (called 'dead' mutations in the paper): discard
  #   iii.If result is the same: Add the symmetric difference of the original 
  #       and the mutation to the path constraints
  #
  def _mutate(self, *args, **kwargs):
    mutations = {} 
    for arg in kwargs:
      lookups, parts, reffed_aggregate = self.query.solve_lookup_type(arg)

      if len(lookups) != 1:
        continue

      mutated_filters = {}
      operator = lookups[0]
      filter_column = '_'.join(parts)
      filter_value = kwargs[arg]

      mutate_operators = [op for op in self.operators if op != operator]
      for op in mutate_operators:
        mutated_filters[op] = {filter_column + '__' + op: filter_value}

      # TODO: currently only handles filters with single column queries
      # e.g. username='alice'. Ideally, this would handle filters over
      # multiple columns e.g. find the transfers of more than 10 zoobars 
      # to alice recipient='alice' && zoobars > 10
      #break
      return (operator, filter_value, self._create_mutated_querysets(mutated_filters, *args))

    #mutations.append(mutation_set)

    return mutations

  def _create_mutated_querysets(self, mutated_filters, *args):
    mutations = {}
    for op in mutated_filters:
      filter_kv = mutated_filters[op]
      mutated_queryset = self._apply_filter(*args, **filter_kv)
      mutations[op] = mutated_queryset
    return mutations

  def _remove_dead_mutations(self, original_queryset, mutations):
    unique_mutations = {}
    items = list(six.moves.map(repr, original_queryset))
    for op in mutations:
      mutation = mutations[op]
      if self._is_equal(items, mutation):
        unique_mutations[op] = mutation
    return unique_mutations

  def _is_equal(self, values, other_queryset):
    items = list(six.moves.map(repr, other_queryset))
    return items == values


  def _create_constraints(self, original_op, sym, mutations):
    original = self._create_condition(original_op, sym)
    t_original = sym_eq(original, True)
    f_original = sym_eq(original, False)

    for op in mutations:
      mutant = self._create_condition(op, sym)
      if mutant is None:
        return None

      t_mutant = sym_eq(mutant, True)
      f_mutant = sym_eq(mutant, False)
    
      return sym_or(sym_and(t_original, f_mutant), sym_and(f_original, t_mutant))

  def _create_condition(self, op, sym):
    sym_type = None

    if op == 'gt':
      sym_type = sym_gt
    elif op == 'lt':
      sym_type = sym_lt
    elif op == 'exact':
      sym_type = sym_eq

    if sym_type is None:
      return None

    return sym_type(ast(sym), ast(sym.concrete_value()))


# SymQuerySet that just iterates through every row in the DB
class AllSymQuerySet(QuerySet, SymMixin):
  def get(self, *args, **kwargs):
    import django.contrib.sessions.models
    if self.model is django.contrib.sessions.models.Session or len(kwargs) != 1:
      return self._old_get(AllSymQuerySet, *args, **kwargs)

    key = kwargs.keys()[0]
    if '_' not in key:
      if key == 'pk':
        key = self.model._meta.pk.name
        kwargs[key] = kwargs['pk']
        del kwargs['pk']

      for m in self.model.objects.all():
        value = kwargs[key]

        # support model attribute passthrough
        if isinstance(value, Model) and hasattr(value, key):
          value = getattr(value, key)

        if getattr(m, key) == value:
          real = self._old_get(AllSymQuerySet, *args, **kwargs)
          assert m == real
          return m

      # this should raise an exception, or we've done something wrong
      self._old_get(AllSymQuerySet, *args, **kwargs)
      assert False
    else:
      e = "newget: special keys like %s not yet supported" % key

    return self._old_get(AllSymQuerySet, *args, **kwargs)

class SymManager(Manager, SymMixin):
  def __init__(self, manager, queryset_cls):
    self.manager = manager
    self.queryset_cls = queryset_cls

  def __getattr__(self, attr):
    #print 'getattr' + attr
    return getattr(self.manager, attr)

  def get_queryset(self):
    #import pdb; pdb.set_trace()
    if self.queryset_cls == AllSymQuerySet:
      return AllSymQuerySet(self.model, using=self._db, hints=self._hints)

    if self.queryset_cls == SQLSymQuerySet:
      return SQLSymQuerySet(self.model, using=self._db, hints=self._hints)

    print 'No SymQuerySet selected'
    return QuerySet(self.model, using=self._db, hints=self._hints)
