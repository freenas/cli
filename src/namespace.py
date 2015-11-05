#+
# Copyright 2014 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################


import re
import copy
import traceback
import errno
import icu
from utils import post_save
from fnutils.query import wrap
from output import (ValueType, Object, Table, output_list,
                    output_msg, read_value)
import collections

t = icu.Transliterator.createInstance("Any-Accents", icu.UTransDirection.FORWARD)
_ = t.transliterate


def description(descr):
    def wrapped(fn):
        fn.description = descr
        return fn

    return wrapped


class Namespace(object):
    def __init__(self, name):
        self.name = name
        self.extra_commands = None
        self.nslist = []
        self.property_mappings = []
        self.localdoc = {}
        self.required_props = None
        self.extra_required_props = None

    def help(self):
        pass

    def get_name(self):
        return self.name

    def commands(self):
        # lazy import to avoid circular import hell
        # TODO: can this be avoided? If so please!
        from commands import HelpCommand
        return {
            '?': IndexCommand(self),
            'help': HelpCommand(),
        }

    def namespaces(self):
        return self.nslist

    def on_enter(self):
        pass

    def on_leave(self):
        return True

    def register_namespace(self, ns):
        self.nslist.append(ns)


class Command(object):
    def run(self, context, args, kwargs, opargs):
        raise NotImplementedError()

    def complete(self, context, tokens):
        return []


class FilteringCommand(Command):
    def run(self, context, args, kwargs, opargs, filtering=None):
        raise NotImplementedError()


class PipeCommand(Command):
    def run(self, context, args, kwargs, opargs, input=None):
        pass

    def serialize_filter(self, context, args, kwargs, opargs):
        raise NotImplementedError()


class CommandException(Exception):
    def __init__(self, message, code=None, extra=None):
        self.code = code
        self.message = message
        self.extra = extra
        self.stacktrace = traceback.format_exc()

    def __str__(self):
        if self.code is None:
            return '{0}'.format(self.message)
        else:
            return '{0}: {1}'.format(errno.errorcode[self.code], self.message)


@description("Provides list of commands in this namespace")
class IndexCommand(Command):
    """
    Usage: ?

    Lists all the possible commands and EntityNamespaces accessible form the
    current namespace or the one supplied in the arguments. It also always lists
    the globally avaible builtin set of commands.

    Example:
    ?
    volumes ?
    """
    def __init__(self, target):
        self.target = target

    def run(self, context, args, kwargs, opargs):
        nss = self.target.namespaces()
        cmds = self.target.commands()

        # Only display builtin items if in the RootNamespace
        obj = context.ml.get_relative_object(context.ml.path[-1], args)
        if obj.__class__.__name__ == 'RootNamespace':
            output_msg('Builtin items:', attrs=['bold'])
            output_list(list(context.ml.builtin_commands.keys()))

        output_msg('Current namespace items:', attrs=['bold'])
        out = list(cmds.keys())
        out += [ns.get_name() for ns in sorted(nss, key=lambda i: i.get_name())]
        output_list(out)


class LongIndexCommand(Command):
    def __init__(self, target):
        self.target = target

    def run(self, context, args, kwargs, opargs):
        pass


class RootNamespace(Namespace):
    pass


class PropertyMapping(object):
    def __init__(self, **kwargs):
        self.name = kwargs.pop('name')
        self.descr = kwargs.pop('descr')
        self.get = kwargs.pop('get')
        self.set = kwargs.pop('set', None) if 'set' in kwargs else self.get
        self.list = kwargs.pop('list', True)
        self.type = kwargs.pop('type', ValueType.STRING)
        self.enum = kwargs.pop('enum', None)
        self.enum_set = kwargs.pop('enum_set') if kwargs.get('enum_set') else self.enum
        self.usersetable = kwargs.pop('usersetable', True)
        self.createsetable = kwargs.pop('createsetable', True)
        self.regex = kwargs.pop('regex', None)
        self.condition = kwargs.pop('condition', None)

    def do_get(self, obj):
        if isinstance(self.get, collections.Callable):
            return self.get(obj)

        return obj.get(self.get)

    def do_set(self, obj, value):
        if self.enum_set:
            if value not in self.enum_set:
                raise ValueError('Invalid value for property. Should be one of: {0}'.format(', '.join(self.enum_set)))

        value = read_value(value, self.type)
        if isinstance(self.set, collections.Callable):
            self.set(obj, value)
            return

        obj.set(self.set, value)

    def do_append(self, obj, value):
        if self.type != ValueType.SET:
            raise ValueError('Property is not a set')

        value = read_value(value, self.type)
        oldvalues = obj.get(self.set)
        if oldvalues is not None:
            newvalues = oldvalues + value
        else:
            newvalues = value

        if isinstance(self.set, collections.Callable):
            self.set(obj, newvalues)
            return

        obj.set(self.set, newvalues)

    def do_remove(self, obj, value):
        if self.type != ValueType.SET:
            raise ValueError('Property is not a set')

        value = read_value(value, self.type)
        oldvalues = obj.get(self.set)
        newvalues = oldvalues
        for v in value:
            if v in newvalues:
                newvalues.remove(v)
            else:
                raise CommandException(_('{0} is not a value in {1}'.format(v, self.set)))

        if isinstance(self.set, collections.Callable):
            self.set(obj, newvalues)
            return

        obj.set(self.set, newvalues)


class ItemNamespace(Namespace):
    @description("Shows single item")
    class ShowEntityCommand(FilteringCommand):
        """
        Usage: show
        """
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs, opargs, filtering=None):
            if len(args) != 0:
                raise CommandException('Wrong arguments count')

            values = Object()
            entity = self.parent.entity

            for mapping in self.parent.property_mappings:
                if not mapping.get:
                    continue

                if mapping.condition is not None:
                    if not mapping.condition(entity):
                        continue

                values.append(Object.Item(
                    mapping.descr,
                    mapping.name,
                    mapping.do_get(entity),
                    mapping.type
                ))
            if self.parent.leaf_entity:
                leaf_res = ListCommand(self.parent).run(context, args, kwargs, opargs, filtering)
                return [
                    values,
                    "-- {0} --".format(self.parent.leaf_ns.description),
                    leaf_res
                ]
            return values

    @description("Prints single item value")
    class GetEntityCommand(Command):
        """
        Usage: get <field>
        """
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs, opargs):
            if len(args) < 1:
                output_msg('Wrong arguments count')
                return

            if not self.parent.has_property(args[0]):
                output_msg('Property {0} not found'.format(args[0]))
                return

            entity = self.parent.entity
            return self.parent.get_property(args[0], entity)

        def complete(self, context, tokens):
            return [x.name for x in self.parent.property_mappings]

    @description("Sets single item property")
    class SetEntityCommand(Command):
        """
        Usage: set <property>=<value> [...]

        For a list of properties for the current namespace, see 'help properties'.
        """
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs, opargs):
            if not (args or kwargs or opargs):
                raise CommandException(_("You have provided no arguments."))
            if args:
                for arg in args:
                    if self.parent.has_property(arg):
                        raise CommandException('Invalid use of property {0}'.format(arg))
                    else:
                        raise CommandException(
                            'Invalid argument or use of argument {0}'.format(arg)
                        )
            for k, v in list(kwargs.items()):
                if not self.parent.has_property(k):
                    raise CommandException('Property {0} not found'.format(k))

            entity = self.parent.entity

            for k, v in list(kwargs.items()):
                prop = self.parent.get_mapping(k)
                if prop.set is None or not prop.usersetable:
                    raise CommandException('Property {0} is not writable'.format(k))
                if prop.regex is not None and not re.match(prop.regex, str(v)):
                    raise CommandException('Invalid input {0} for property {1}.'.format(v, k))
                prop.do_set(entity, v)

            for k, op, v in opargs:
                if op not in ('=+', '=-'):
                    raise CommandException(
                        "Syntax error, invalid operator used")

                prop = self.parent.get_mapping(k)

                if op == '=+':
                    prop.do_append(entity, v)

                if op == '=-':
                    prop.do_remove(entity, v)

            self.parent.modified = True
            self.parent.save()

        def complete(self, context, tokens):
            return [x.name + '=' for x in self.parent.property_mappings if x.set]

    def __init__(self, name):
        super(ItemNamespace, self).__init__(name)
        self.name = name
        if not hasattr(self, 'description'):
            self.description = name
        self.entity = None
        self.leaf_entity = False
        self.orig_entity = None
        self.allow_edit = True
        self.modified = False
        self.subcommands = {}
        self.nslist = []

    def on_enter(self):
        self.load()

    def on_leave(self):
        # if self.modified:
        #     output_msg('Object was modified. '
        #                'Type either "save" or "discard" to leave')
        #     return False

        return True

    def get_name(self):
        return self.name

    def get_changed_keys(self):
        for i in list(self.entity.keys()):
            if i not in list(self.orig_entity.keys()):
                yield i
                continue

            if self.entity[i] != self.orig_entity[i]:
                yield i

    def get_diff(self):
        return {k: self.entity[k] for k in self.get_changed_keys()}

    def load(self):
        raise NotImplementedError()

    def save(self):
        raise NotImplementedError()

    def has_property(self, prop):
        return any([x for x in self.property_mappings if x.name == prop])

    def get_mapping(self, prop):
        return list([x for x in self.property_mappings if x.name == prop])[0]

    def add_property(self, **kwargs):
        self.property_mappings.append(PropertyMapping(**kwargs))

    def get_property(self, prop, obj):
        mapping = self.get_mapping(prop)
        return mapping.do_get(obj)

    def commands(self):
        base = {
            '?': IndexCommand(self),
            'get': self.GetEntityCommand(self),
            'show': self.ShowEntityCommand(self),
        }

        if self.allow_edit:
            base.update({
                'set': self.SetEntityCommand(self),
            })

        if self.commands is not None:
            base.update(self.subcommands)

        return base


class ConfigNamespace(ItemNamespace):
    def __init__(self, name, context):
        super(ConfigNamespace, self).__init__(name)
        self.context = context
        self.saved = name is not None
        self.config_call = None
        self.config_extra_params = None

    def get_name(self):
        name = self.name

        return name if not self.modified else '[{0}]'.format(name)

    def commands(self):
        base = super(ConfigNamespace, self).commands()

        if self.extra_commands:
            base.update(self.extra_commands)

        return base

    def load(self):
        if self.saved:
            if self.config_extra_params:
                config_extra = self.config_extra_params() if isinstance(self.config_extra_params, collections.Callable) else self.config_extra_params
                self.entity = self.context.call_sync(self.config_call, config_extra)
            else:
                self.entity = self.context.call_sync(self.config_call)
            self.orig_entity = copy.deepcopy(self.entity)
        else:
            # This is in case the task failed!
            self.entity = copy.deepcopy(self.orig_entity)
        self.modified = False


class SingleItemNamespace(ItemNamespace):
    def __init__(self, name, parent, **kwargs):
        super(SingleItemNamespace, self).__init__(name)
        self.parent = parent
        self.saved = name is not None
        self.property_mappings = parent.property_mappings
        self.localdoc = parent.entity_localdoc
        self.leaf_harborer = False
        self.leaf_entity = kwargs.get('leaf_entity', False)
        self.leaf_entity_namespace = self.parent.leaf_entity_namespace
        self.leaf_ns = None

        if parent.entity_commands:
            self.subcommands = parent.entity_commands(self)

        if parent.entity_namespaces:
            self.nslist = parent.entity_namespaces(self)

        if parent.leaf_entity_namespace:
            self.leaf_ns = parent.leaf_entity_namespace(self)
            if self.nslist:
                self.nslist.append(self.leaf_ns)
            else:
                self.nslist = [self.leaf_ns]

        if hasattr(parent, 'allow_edit'):
            self.allow_edit = parent.allow_edit

    @property
    def primary_key(self):
        return self.parent.primary_key.do_get(self.entity)

    def get_name(self):
        name = self.primary_key if self.entity else self.name
        if not name and name != 0:
            name = 'unnamed'

        return name if self.saved and not self.modified else '[{0}]'.format(name)

    def load(self):
        if self.saved:
            self.entity = self.parent.get_one(self.get_name())
            self.orig_entity = copy.deepcopy(self.entity)
        else:
            # This is in case the task failed!
            self.entity = copy.deepcopy(self.orig_entity)
        self.modified = False

    def save(self):
        self.parent.save(self, not self.saved)

    def commands(self):
        command_set = super(SingleItemNamespace, self).commands()
        if self.parent.leaf_harborer:
            if self.leaf_ns.allow_create:
                command_set.update({
                    'create': CreateEntityCommand(self),
                    'delete': DeleteEntityCommand(self),
                })
        return command_set

    def namespaces(self):
        if not self.leaf_entity:
            return super(SingleItemNamespace, self).namespaces()
        if self.leaf_ns.primary_key is None:
            return

        # for some reason yield does not work below
        nslst = []
        for i in self.leaf_ns.query([], {}):
            name = self.leaf_ns.primary_key.do_get(i)
            nslst.append(SingleItemNamespace(name, self.leaf_ns, leaf_entity=self.leaf_harborer))
        return nslst


@description("Lists items")
class ListCommand(FilteringCommand):
    """
    Usage: show [<field> <operator> <value> ...] [limit=<n>] [sort=<field>,-<field2>]

    Lists items in current namespace, optinally doing filtering and sorting.

    Examples:
        show
        show username=root
        show uid>1000
        show fullname~="John" sort=fullname
    """
    def __init__(self, parent):
        if hasattr(parent, 'leaf_entity') and parent.leaf_entity:
            self.parent = parent.leaf_ns
        else:
            self.parent = parent

    def __map_filter_properties(self, expr):
        for i in expr:
            if len(i) == 2:
                op, l = i
                yield op, list(self.__map_filter_properties(l))

            if len(i) == 3:
                k, op, v = i
                if op == '==': op = '='
                if op == '~=': op = '~'

                prop = self.parent.get_mapping(k)
                yield k if isinstance(prop.get, collections.Callable) else prop.get, op, v

    def run(self, context, args, kwargs, opargs, filtering=None):
        cols = []
        params = []
        options = {}

        if filtering:
            for k, v in list(filtering['params'].items()):
                if k == 'limit':
                    options['limit'] = int(v)
                    continue

                if k == 'sort':
                    for sortkey in v:
                        prop = self.parent.get_mapping(sortkey)
                        options.setdefault('sort', []).append(prop.get)
                    continue

                if not self.parent.has_property(k):
                    raise CommandException('Unknown field {0}'.format(k))

            params = list(self.__map_filter_properties(filtering['filter']))

        for col in [x for x in self.parent.property_mappings if x.list]:
            cols.append(Table.Column(col.descr, col.get, col.type))

        return Table(self.parent.query(params, options), cols)


@description("Creates new item")
class CreateEntityCommand(Command):
    """
    Usage: create [<property>=<value> ...]

    For a list of properties for the current namespace, see 'help properties'.
    """
    def __init__(self, parent):
        if hasattr(parent, 'leaf_entity') and parent.leaf_entity:
            self.parent = parent.leaf_ns
        else:
            self.parent = parent

    def run(self, context, args, kwargs, opargs):
        ns = SingleItemNamespace(None, self.parent)
        ns.orig_entity = wrap(copy.deepcopy(self.parent.skeleton_entity))
        ns.entity = wrap(copy.deepcopy(self.parent.skeleton_entity))

        if len(args) > 0:
            prop = self.parent.primary_key
            prop.do_set(ns.entity, args.pop(0))

        for k, v in list(kwargs.items()):
            if not self.parent.has_property(k):
                output_msg('Property {0} not found'.format(k))
                return
            mapping = self.parent.get_mapping(k)
            if mapping.set is None or not mapping.createsetable:
                output_msg('Property {0} is not writable'.format(k))
                return
            if mapping.regex is not None and not re.match(mapping.regex, str(v)):
                output_msg('Invalid input {0} for property {1}.'.format(v, k))
                return

        if self.parent.required_props:
            missing_args = []
            for prop in self.parent.required_props:
                if isinstance(prop, list):
                    has_arg = False
                    for p in prop:
                        if p in kwargs.keys():
                            has_arg = True
                    if not has_arg:
                        missing_args.append("{0}".format(' or '.join(prop)))
                else:
                    if prop not in kwargs.keys():
                        missing_args.append(prop)
            if self.parent.extra_required_props:
                for prop_set in self.parent.extra_required_props:
                    found_one = False
                    missing = False
                    for prop in prop_set:
                        if prop in kwargs.keys():
                            found_one = True
                        else:
                            if found_one:
                                missing = True
                    if found_one and missing:
                        missing_args.append(' and '.join(prop_set))
            if len(missing_args) > 0:
                output_msg('Required properties not met, still missing: {0}'.format(', '.join(missing_args)))
                return
        else:
            if not args and not kwargs:
                return

        for k, v in kwargs.items():
            prop = self.parent.get_mapping(k)
            prop.do_set(ns.entity, v)

        self.parent.save(ns, new=True)

    def complete(self, context, tokens):
        return [x.name + '=' for x in self.parent.property_mappings if x.set]


@description("Removes item")
class DeleteEntityCommand(Command):
    """
    Usage: delete <primary-key>

    Examples:
        delete john
    """
    def __init__(self, parent):
        if hasattr(parent, 'leaf_entity') and parent.leaf_entity:
            self.parent = parent.leaf_ns
        else:
            self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if len(args) == 0:
            raise CommandException(_("Please specify item to delete."))
        self.parent.delete(args[0])


class EntityNamespace(Namespace):

    def __init__(self, name, context):
        super(EntityNamespace, self).__init__(name)
        self.context = context
        self.primary_key = None
        self.entity_commands = None
        self.entity_namespaces = None
        self.allow_edit = True
        self.allow_create = True
        self.skeleton_entity = {}
        self.entity_localdoc = {}
        self.leaf_harborer = False
        self.leaf_entity_namespace = None

    def has_property(self, prop):
        return any([x for x in self.property_mappings if x.name == prop])

    def get_mapping(self, prop):
        return list(filter(lambda x: x.name == prop, self.property_mappings))[0]

    def get_property(self, prop, obj):
        mapping = self.get_mapping(prop)
        return mapping.do_get(obj)

    def get_one(self, name):
        raise NotImplementedError()

    def update_entity(self, name):
        raise NotImplementedError()

    def query(self, params, options):
        raise NotImplementedError()

    def add_property(self, **kwargs):
        self.property_mappings.append(PropertyMapping(**kwargs))

    def commands(self):
        base = {
            '?': IndexCommand(self),
            'show': ListCommand(self)
        }

        if self.extra_commands:
            base.update(self.extra_commands)

        if self.allow_create:
            base.update({
                'create': CreateEntityCommand(self),
                'delete': DeleteEntityCommand(self)
            })

        return base

    def namespaces(self):
        if self.primary_key is None:
            return

        for i in self.query([], {}):
            name = self.primary_key.do_get(i)
            yield SingleItemNamespace(name, self, leaf_entity=self.leaf_harborer)


class RpcBasedLoadMixin(object):
    def __init__(self, *args, **kwargs):
        super(RpcBasedLoadMixin, self).__init__(*args, **kwargs)
        self.primary_key_name = 'id'
        self.extra_query_params = []

    def query(self, params, options):
        return wrap(self.context.connection.call_sync(
            self.query_call,
            self.extra_query_params + params, options))

    def get_one(self, name):
        return self.context.call_sync(
            self.query_call,
            self.extra_query_params + [(self.primary_key_name, '=', name)],
            {'single': True})


class TaskBasedSaveMixin(object):
    def __init__(self, *args, **kwargs):
        super(TaskBasedSaveMixin, self).__init__(*args, **kwargs)
        self.save_key_name = getattr(self, 'primary_key_name', 'id')

    def save(self, this, new=False):
        if new:
            self.context.submit_task(
                self.create_task,
                this.entity,
                callback=lambda s: post_save(this, s))
            return

        self.context.submit_task(
            self.update_task,
            this.orig_entity[self.save_key_name],
            this.get_diff(),
            callback=lambda s: post_save(this, s))

    def delete(self, name):
        entity = self.get_one(name)
        if entity:
            self.context.submit_task(self.delete_task, entity[self.save_key_name])
        else:
            output_msg("Cannot delete {0}, item does not exist".format(name))
