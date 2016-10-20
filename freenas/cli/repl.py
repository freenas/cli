#!/usr/bin/env python
#
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

import copy
import enum
import sys
import os
import glob
import argparse
import imp
import logging
import errno
import fnmatch
import platform
import json
import time
import gettext
import getpass
import traceback
import threading
import six
import paramiko
import inspect
import re
import contextlib
import rollbar
from six.moves.urllib.parse import urlparse
from socket import gaierror as socket_error
from freenas.cli.output import Table
from freenas.cli.descriptions import events
from freenas.cli.utils import SIGTSTPException, SIGTSTP_setter, errors_by_path, quote
from freenas.cli import functions
from freenas.cli import config
from freenas.cli.namespace import (
    Namespace, EntityNamespace, RootNamespace, SingleItemNamespace, ConfigNamespace, Command,
    FilteringCommand, PipeCommand, CommandException,
)
from freenas.cli.parser import (
    parse, unparse, Symbol, Literal, BinaryParameter, UnaryExpr, BinaryExpr, PipeExpr, AssignmentStatement,
    IfStatement, ForStatement, ForInStatement, WhileStatement, FunctionCall, CommandCall, Subscript,
    ExpressionExpansion, CommandExpansion, SyncCommandExpansion, FunctionDefinition, ReturnStatement,
    BreakStatement, UndefStatement, Redirection, AnonymousFunction, ShellEscape, Parentheses, ConstStatement,
    Quote
)
from freenas.cli.output import (
    ValueType, ProgressBar, output_lock, output_msg, read_value, format_value,
    format_output, output_msg_locked
)
from freenas.dispatcher.client import Client, ClientError
from freenas.dispatcher.entity import EntitySubscriber
from freenas.dispatcher.rpc import RpcException
from freenas.utils import first_or_default, include, best_match
from freenas.utils.query import get
from freenas.cli.commands import (
    ExitCommand, PrintoptCommand, SetoptCommand, SetenvCommand, PrintenvCommand,
    ShellCommand, HelpCommand, ShowUrlsCommand, ShowIpsCommand, TopCommand, ClearCommand,
    HistoryCommand, SaveoptCommand, EchoCommand, SourceCommand, MorePipeCommand,
    SearchPipeCommand, ExcludePipeCommand, SortPipeCommand, LimitPipeCommand,
    SelectPipeCommand, FindPipeCommand, LoginCommand, DumpCommand, WhoamiCommand, PendingCommand,
    WaitCommand, OlderThanPipeCommand, NewerThanPipeCommand, IndexCommand, AliasCommand,
    UnaliasCommand, ListVarsCommand, AttachDebuggerCommand, ChangeNamespaceCommand,
    WCommand, TimeCommand, RemoteCommand
)
from freenas.cli.docgen import CliDocGen

import collections

try:
    from shutil import get_terminal_size
except ImportError:
    from backports.shutil_get_terminal_size import get_terminal_size

if platform.system() == 'Darwin':
    import gnureadline as readline
else:
    import readline

DEFAULT_MIDDLEWARE_CONFIGFILE = None
CLI_LOG_DIR = None
if os.environ.get('FREENAS_SYSTEM') == 'YES':
    DEFAULT_MIDDLEWARE_CONFIGFILE = '/usr/local/etc/middleware.conf'
    CLI_LOG_DIR = '/var/tmp'
    rollbar.init('9d317f74118c41059f4046afc446a01e', 'cli_local')
else:
    rollbar.init('9d317f74118c41059f4046afc446a01e', 'cli_remote')

DEFAULT_CLI_CONFIGFILE = os.path.join(os.getcwd(), '.freenascli.conf')



t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


PROGRESS_CHARS = ['-', '\\', '|', '/']
EVENT_MASKS = [
    'client.logged',
    'task.progress',
    'task.updated',
    'service.stopped',
    'service.started',
    'session.message'
]
ENTITY_SUBSCRIBERS = [
    'user',
    'group',
    'disk',
    'disk.enclosure',
    'volume',
    'volume.dataset',
    'volume.snapshot',
    'network.interface',
    'network.host',
    'network.route',
    'service',
    'share',
    'task',
    'tunable',
    'session',
    'crypto.certificate',
    'calendar_task',
    'alert',
    'alert.filter',
    'vm',
    'vm.snapshot',
    'syslog',
    'replication',
    'replication.host',
    'backup',
    'kerberos.realm',
    'kerberos.keytab',
    'directory',
    'boot.environment',
    'peer',
    'docker.host',
    'docker.container',
    'docker.image',
    'vmware.dataset'
]


def sort_args(args):
    positional = []
    kwargs = {}
    opargs = []

    for i in args:
        if type(i) is tuple:
            if i[1] == '=':
                kwargs[i[0]] = i[2]
            else:
                opargs.append(i)
            continue

        positional.append(i)

    return positional, kwargs, opargs


def expand_wildcards(context, args, kwargs, opargs, completions):
    def expand_one(value, completion):
        choices = completion.choices(context, None)
        regex = re.compile(value)
        return list(filter(regex.match, choices))

    for i in completions:
        if not getattr(i, 'list', None):
            continue

        if isinstance(i.name, six.integer_types):
            if not len(args) >= i.name or not isinstance(kwargs[name], six.string_types):
                continue

            args[i.name] = expand_one(args[i.name], i)

        if isinstance(i.name, six.string_types):
            name, op = i.name[:-1], i.name[-1]
            if op == '=':
                if name not in kwargs or not isinstance(kwargs[name], six.string_types):
                    continue

                kwargs[name] = expand_one(kwargs[name], i)

    return args, kwargs, opargs


def convert_to_literals(tokens):
    def conv(t):
        if isinstance(t, list):
            return [conv(i) for i in t]

        if isinstance(t, Symbol):
            return Literal(t.name, str)

        if isinstance(t, BinaryParameter):
            t.right = conv(t.right)

        return t

    return [conv(i) for i in tokens]


class FlowControlInstructionType(enum.Enum):
    RETURN = 'RETURN'
    BREAK = 'BREAK'


class Alias(object):
    def __init__(self, context, string):
        self.ast = parse(string, '<alias>')


class VariableStore(object):
    class Variable(object):
        def __init__(self, default, type, choices=None, readonly=False):
            self.default = default
            self.type = type
            self.choices = choices
            self.value = default
            self.readonly = readonly

        def set(self, value):
            assert not self.readonly, _("Cannot set a readonly opt variable")
            value = read_value(value, self.type)
            if self.choices is not None and value not in self.choices:
                raise ValueError(
                    _("Value not on the list of possible choices"))

            self.value = value

        def __str__(self):
            return format_value(self.value, self.type)

    def __init__(self):
        self.save_to_file = DEFAULT_CLI_CONFIGFILE
        self.variables = {
            'output_format': self.Variable('ascii', ValueType.STRING, ['ascii', 'json']),
            'datetime_format': self.Variable('natural', ValueType.STRING),
            'language': self.Variable(os.getenv('LANG', 'C'), ValueType.STRING),
            'prompt': self.Variable('{jobs_short}{host}:{path}>', ValueType.STRING),
            'timeout': self.Variable(10, ValueType.NUMBER),
            'tasks_blocking': self.Variable(False, ValueType.BOOLEAN),
            'show_events': self.Variable(True, ValueType.BOOLEAN),
            'debug': self.Variable(False, ValueType.BOOLEAN),
            'abort_on_errors': self.Variable(False, ValueType.BOOLEAN),
            'output': self.Variable(None, ValueType.STRING),
            'verbosity': self.Variable(1, ValueType.NUMBER),
            'rollbar_enabled': self.Variable(True, ValueType.BOOLEAN),
            'vm.console_interrupt': self.Variable(r'\035', ValueType.STRING),
            'cli_src_path': self.Variable(
                os.path.dirname(os.path.realpath(__file__)), ValueType.STRING, None, True
            )
        }
        self.variable_doc = {
            'output_format': _('Console output format. Can be set to \'ascii\' or \'json\'.'),
            'datetime_format': _('Date and time format.'),
            'language': _('Display the console language.'),
            'prompt': _('Console prompt.'),
            'timeout': _('Console timeout period in minutes.'),
            'tasks_blocking': _('Toggle tasks blocking console output. Can be set to yes or no.'),
            'show_events': _('Toggle displaying of events. Can be set to yes or no.'),
            'debug': _('Toggle display of debug messages. Can be set to yes or no.'),
            'abort_on_errors': _('Can be set to yes or no. When set to yes, command execution will abort on command errors.'),
            'output': _('Either send all output to specified file or set to \'none\' to display output on the console.'),
            'verbosity': _('Increasing verbosity of event messages. Can be set from 1 to 5.'),
            'rollbar_enabled': _('Toggle rollbar error reporting. Can be set to yes or no.'),
            'vm.console_interrupt': _(r'Set the console interrupt key sequence for virtual machines with support for octal characters of the form \nnn. Default is ^] or octal 035.'),
            'cli_src_path': _('The absolute path of the cli source code on this machine')
        }

    def load(self, filename):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
        except IOError:
            # The file does not exist lets just default to default env settings
            # TODO: Should I report this to the user somehow?
            return
        except ValueError:
            # If the data being deserialized is not a valid JSON document,
            # a ValueError will be raised.
            output_msg(
                _("WARNING: The CLI config file: {0} has ".format(filename) +
                  "improper format. Please check the file for errors. " +
                  "Resorting to Default set of Environment Variables."))
            return
        # Now that we know that this file is legit and that it may be different
        # than the default (DEFAULT_CLI_CONFIGFILE) lets just set this class's
        # 'save_to_file' variable to this file.
        self.save_to_file = filename
        for name, setting in data.items():
            self.set(name, setting['value'],
                     ValueType(setting['type']), setting['default'],
                     setting['choices'])

    def save(self, filename=None):
        env_settings = {}
        for key, variable in self.variables.items():
            if not variable.readonly:
                env_settings[key] = {
                    'default': variable.default,
                    'type': variable.type.value,
                    'choices': variable.choices,
                    'value': variable.value
                }
        try:
            with open(filename or self.save_to_file, 'w') as f:
                json.dump(env_settings, f)
        except IOError:
            raise
        except ValueError as err:
            raise ValueError(
                _("Could not save environemnet to file. Following error " +
                  "occured: {0}".format(str(err))))

    def get(self, name):
        return self.variables[name].value

    def get_all(self):
        return list(self.variables.items())

    def get_all_printable(self):
        for name, var in list(self.variables.items()):
            yield (name, str(var))

    def set(self, name, value, vtype=ValueType.STRING,
            default='', choices=None):
        if name not in self.variables:
            self.variables[name] = self.Variable(default, vtype, choices)

        self.variables[name].set(value)

    def verify(self, name, value):
        if name == 'verbosity':
            try:
                if not 1 <= int(value) <= 5:
                    raise ValueError
            except ValueError as e:
                raise ValueError(_("Invalid value: {0}, "
                                   "verbosity must be an integer value between 1 and 5.".format(value)))


class Context(object):
    def __init__(self):
        self.docgen_run = False
        self.uri = None
        self.parsed_uri = None
        self.hostname = None
        self.connection = Client()
        self.ml = None
        self.logger = logging.getLogger('cli')
        self.plugin_dirs = []
        self.task_callbacks = {}
        self.plugins = {}
        self.reverse_task_mappings = {}
        self.variables = VariableStore()
        self.root_ns = RootNamespace('')
        self.event_masks = ['*']
        self.event_divert = False
        self.event_queue = six.moves.queue.Queue()
        self.output_queue = six.moves.queue.Queue()
        self.keepalive_timer = None
        self.argparse_parser = None
        self.entity_subscribers = {}
        self.call_stack = [CallStackEntry('<stdin>', [], '<stdin>', 1, 1)]
        self.builtin_operators = functions.operators
        self.builtin_functions = functions.functions
        self.global_env = Environment(self)
        self.user = None
        self.pending_tasks = {}
        self.session_id = None
        self.user_commands = []
        self.local_connection = False
        config.instance = self

        self.output_thread = threading.Thread(target=self.output_thread)
        self.output_thread.daemon = True
        self.output_thread.start()

    @property
    def is_interactive(self):
        return os.isatty(sys.stdout.fileno())

    @property
    def pending_jobs(self):
        return len(list(filter(
            lambda t: t['parent'] is None and t['session'] == self.session_id,
            self.pending_tasks.values()
        )))

    def start(self, password=None):
        self.discover_plugins()
        self.connect(password) if not self.docgen_run else None

    def start_entity_subscribers(self):
        for i in ENTITY_SUBSCRIBERS:
            if i in self.entity_subscribers:
                self.entity_subscribers[i].stop()
                del self.entity_subscribers[i]

            e = EntitySubscriber(self.connection, i)
            e.start()
            self.entity_subscribers[i] = e

        def update_task(task, old_task=None):
            self.pending_tasks[task['id']] = task
            descr = task['name']

            if task['description']:
                descr = task['description']['message']

            if task['state'] in ('FINISHED', 'FAILED', 'ABORTED'):
                del self.pending_tasks[task['id']]

            if task['id'] in self.task_callbacks:
                self.handle_task_callback(task)

            if self.variables.get('verbosity') > 1 and task['state'] in ('CREATED', 'FINISHED'):
                self.output_queue.put(_(
                    "Task #{0}: {1}: {2}".format(
                        task['id'],
                        descr,
                        task['state'].lower(),
                    )
                ))

            if self.variables.get('verbosity') > 2 and task['state'] == 'WAITING':
                self.output_queue.put(_(
                    "Task #{0}: {1}: {2}".format(
                        task['id'],
                        descr,
                        task['state'].lower(),
                    )
                ))

            if task['state'] == 'FAILED':
                if not task['parent'] or self.variables.get('verbosity') > 1:
                    self.output_queue.put(_(
                        "Task #{0} error: {1}".format(
                            task['id'],
                            task['error'].get('message', '') if task.get('error') else ''
                        )
                    ))

                    self.print_validation_errors(task)

            if task['state'] == 'ABORTED':
                self.output_queue.put(_("Task #{0} aborted".format(task['id'])))

            if old_task:
                if len(task['warnings']) > len(old_task['warnings']):
                    for i in task['warnings'][len(old_task['warnings']):]:
                        self.output_queue.put(_("Task #{0}: {1}: warning: {2}".format(
                            task['id'],
                            descr,
                            i['message']
                        )))

        self.entity_subscribers['task'].on_add.add(update_task)
        self.entity_subscribers['task'].on_update.add(lambda o, n: update_task(n, o))

    def wait_entity_subscribers(self):
        for i in self.entity_subscribers.values():
            i.wait_ready()

    def connect(self, password=None):
        try:
            self.connection.connect(self.uri, password=password)
        except (socket_error, OSError) as err:
            output_msg(_(
                "Could not connect to host: {0} due to error: {1}".format(
                    self.parsed_uri.hostname or '<local>', err
                )
            ))
            sys.exit(1)
        except paramiko.ssh_exception.AuthenticationException:
            output_msg(_(
                "Could not connect to host: {0} due to error: Incorrect username or password".format(
                    self.parsed_uri.hostname or '<local>'
                )
            ))
            sys.exit(1)

    def login(self, user, password):
        try:
            self.connection.login_user(user, password)
            self.connection.subscribe_events(*EVENT_MASKS)
            self.connection.on_event(self.handle_event)
            self.connection.on_error(self.connection_error)
            self.connection.call_sync('management.enable_features', ['streaming_responses'])
            self.session_id = self.call_sync('session.get_my_session_id')
        except RpcException as e:
            if e.code == errno.EACCES:
                self.connection.disconnect()
                output_msg(_("Wrong username or password"))
                sys.exit(1)

        self.start_entity_subscribers()
        self.login_plugins()

    def keepalive(self):
        if self.connection.opened:
            self.connection.call_sync('management.ping')

    def read_middleware_config_file(self, file):
        """
        If there is a cli['plugin-dirs'] in middleware.conf use that,
        otherwise use the default plugins dir within cli namespace
        """
        plug_dirs = None
        if file:
            with open(file, 'r') as f:
                data = json.load(f)

            if 'cli' in data and 'plugin-dirs' in data['cli']:

                if type(data['cli']['plugin-dirs']) != list:
                    return

                self.plugin_dirs += data['cli']['plugin-dirs']

        if plug_dirs is None:
            # Support for pyinstaller
            if hasattr(sys, '_MEIPASS'):
                plug_dirs = os.path.join(sys._MEIPASS, 'freenas/cli/plugins')
            else:
                plug_dirs = os.path.join(self.variables.get('cli_src_path'), 'plugins')
            self.plugin_dirs += [plug_dirs]

    def discover_plugins(self):
        for dir in self.plugin_dirs:
            self.logger.debug(_("Searching for plugins in %s"), dir)
            self.__discover_plugin_dir(dir)

    def login_plugins(self):
        for i in list(self.plugins.values()):
            if hasattr(i, '_login'):
                i._login(self)

    def __discover_plugin_dir(self, dir):
        for i in glob.glob1(dir, "*.py"):
            self.__try_load_plugin(os.path.join(dir, i))

    def __try_load_plugin(self, path):
        if path in self.plugins:
            return

        self.logger.debug(_("Loading plugin from %s"), path)
        name, ext = os.path.splitext(os.path.basename(path))
        try:
            plugin = imp.load_source(name, path)
            if hasattr(plugin, '_init'):
                plugin._init(self)
                self.plugins[path] = plugin
        except Exception:
            if self.variables.get('rollbar_enabled'):
                rollbar.report_exc_info()
            raise

    def __try_reconnect(self):
        output_lock.acquire()
        self.ml.blank_readline()

        output_msg(_('Connection lost! Trying to reconnect...'))
        retries = 0
        if self.parsed_uri.scheme == 'ssh':
            password = getpass.getpass()
        else:
            password = None

        while True:
            retries += 1
            try:
                time.sleep(2)
                try:
                    self.connection.connect(self.uri, password=password)
                except paramiko.ssh_exception.AuthenticationException:
                    output_msg(_("Incorrect password"))
                    password = getpass.getpass()
                    continue
                except Exception as e:
                    output_msg(_(
                        "Error reconnecting to host {0}: {1}".format(
                            self.hostname, e)))
                    continue
                try:
                    if self.local_connection:
                        self.connection.login_user(self.user, '')
                    else:
                        self.connection.login_token(self.connection.token)

                    self.connection.subscribe_events(*EVENT_MASKS)
                except RpcException as e:
                    output_msg(_(
                        "Reauthentication failed (most likely token expired or server was"
                        " restarted), use the 'login' command to log back in."
                    ))
                    if self.local_connection:
                        # we might've gotten an EACCESS on the local connection if the dispatcher
                        # just barely started but still was not initiated enough for auth
                        # so we should just retry in that case
                        continue
                break
            except Exception as e:
                output_msg(_('Cannot reconnect: {0}'.format(str(e))))

        self.ml.restore_readline()
        output_lock.release()

    def attach_namespace(self, path, ns):
        splitpath = path.split('/')
        ptr = self.root_ns
        ptr_namespaces = ptr.namespaces()

        for n in splitpath[1:-1]:

            if n not in list(ptr_namespaces().keys()):
                self.logger.warn(_("Cannot attach to namespace %s"), path)
                return

            ptr = ptr_namespaces()[n]

        ptr.register_namespace(ns)

    def map_tasks(self, task_wildcard, cls):
        self.reverse_task_mappings[task_wildcard] = cls

    def connection_error(self, event, **kwargs):
        if event == ClientError.LOGOUT:
            self.output_queue.put('Logged out from server.')
            self.connection.disconnect()
            sys.exit(0)

        if event == ClientError.CONNECTION_CLOSED:
            time.sleep(1)
            self.__try_reconnect()
            return

    def handle_event(self, event, data):
        if event == 'task.progress':
            progress = include(data, 'percentage', 'message', 'extra')
            task = self.entity_subscribers['task'].items.get(data['id'])
            if not task:
                return

            task['progress'] = progress
            self.entity_subscribers['task'].update(task)

            if task['id'] in self.pending_tasks:
                self.pending_tasks[data['id']]['progress'] = progress

        self.print_event(event, data)

    def get_validation_errors(self, task):
        __, nsclass = best_match(
            self.reverse_task_mappings.items(),
            task['name'],
            key=lambda f: f[0],
            default=(None, None)
        )

        if not nsclass:
            return

        if callable(nsclass) and not inspect.isclass(nsclass):
            nsclass = nsclass(self, task)

        if not nsclass:
            return

        entityns = nsclass('<temp>', self) if inspect.isclass(nsclass) else nsclass

        if isinstance(entityns, EntityNamespace):
            namespace = SingleItemNamespace('<temp>', entityns, self)
            if task['name'] == entityns.update_task:
                # Update tasks have updated_params as second argument
                errors = errors_by_path(task['error']['extra'], [1])
                obj_id = get(task, 'args.0')
            elif task['name'] == entityns.create_task:
                # Create tasks have object as first argument
                errors = errors_by_path(task['error']['extra'], [0])
                obj_id = get(task, 'args.0.id')
            else:
                return
        elif isinstance(entityns, ConfigNamespace):
            namespace = entityns
            if task['name'] == entityns.update_task:
                errors = errors_by_path(task['error']['extra'], [0])
            else:
                return
        else:
            return

        if isinstance(entityns, EntityNamespace):
            entity_subscriber_name, __ = task['name'].rsplit('.', 1)
            if entity_subscriber_name in self.entity_subscribers:
                obj = self.entity_subscribers[entity_subscriber_name].query(('id', '=', obj_id), single=True)
                if obj:
                    namespace.name = obj[entityns.primary_key_name]
                    namespace.load()

        for i in errors:
            pathname = '.'.join(str(p) for p in i['path'])
            property = namespace.get_mapping_by_field(pathname)
            yield property.name if property else pathname, i['code'], i['message']

    def print_validation_errors(self, task):
        if get(task, 'error.type') == 'ValidationException':
            errors = self.get_validation_errors(task)
            if not errors:
                return

            for prop, __, msg in errors:
                self.output_queue.put(_("Task #{0} validation error: {1}{2}{3}".format(
                    task['id'],
                    prop,
                    ': ' if prop else '',
                    msg
                )))

    def output_thread(self):
        while True:
            item = self.output_queue.get()
            output_msg_locked(item)

    def handle_task_callback(self, data):
        if data['state'] in ('FINISHED', 'CANCELLED', 'ABORTED', 'FAILED'):
            self.task_callbacks[data['id']](data['state'], data)

    def print_event(self, event, data):
        if self.event_divert:
            self.event_queue.put((event, data))
            return

        translation = events.translate(self, event, data)
        if translation:
            self.output_queue.put(translation)

    def call_sync(self, name, *args, **kwargs):
        return self.connection.call_sync(name, *args, **kwargs) if not self.docgen_run else {}

    def call_async(self, name, callback, *args, **kwargs):
        return self.connection.call_async(name, callback, *args, **kwargs) if not self.docgen_run else None

    def call_task_sync(self, name, *args, **kwargs):
        return self.connection.call_task_sync(name, *args)

    def submit_task_common_routine(self, name, callback, *args):
        """
        Just a small subrotuine that is used in bot blocking as
        well as non-blocking tasks in the main submit_task func
        below.
        It returns the id of the task.
        """
        tid = self.connection.call_sync('task.submit', name, args)
        if callback:
            self.task_callbacks[tid] = callback
        self.global_env['_last_task_id'] = Environment.Variable(tid)
        return tid

    def wait_for_task_with_progress(self, tid):
        def update(progress, task):
            message = task['progress']['message'] if 'progress' in task else task['state']
            percentage = task['progress']['percentage'] if 'progress' in task else None
            progress.update(percentage=percentage, message=message)

        generator = None
        progress = None

        try:
            task = self.entity_subscribers['task'].get(tid, timeout=5)
            if not task:
                return _("Task {0} not found".format(tid))

            if task['state'] in ('FINISHED', 'FAILED', 'ABORTED'):
                return _("The task with id: {0} ended in {1} state".format(tid, task['state']))

            # lets set the SIGTSTP (Ctrl+Z) handler
            SIGTSTP_setter(set_flag=True)
            output_msg(_("Hit Ctrl+C to terminate task if needed"))
            output_msg(_("To background running task press 'Ctrl+Z'"))

            progress = ProgressBar()
            update(progress, task)
            generator = self.entity_subscribers['task'].listen(tid)

            for op, old, new in generator:
                update(progress, new)

                if new['state'] == 'FINISHED':
                    progress.finish()
                    break

                if new['state'] == 'FAILED':
                    six.print_()
                    break

                if new['state'] == 'ABORTED':
                    six.print_()
                    break
        except KeyboardInterrupt:
            if progress:
                progress.end()
            six.print_()
            output_msg(_("User requested task termination. Abort signal sent"))
            self.call_sync('task.abort', tid)
        except SIGTSTPException:
                # The User backgrounded the task by sending SIGTSTP (Ctrl+Z)
                if progress:
                    progress.end()
                six.print_()
                output_msg(_("Task {0} will continue to run in the background.".format(tid)))
                output_msg(_("To bring it back to the foreground execute 'wait {0}'".format(tid)))
                output_msg(_("Use the 'pending' command to see pending tasks (of this session)"))
        finally:
            # Now that we are done with the task unset the Ctrl+Z handler
            # lets set the SIGTSTP (Ctrl+Z) handler
            SIGTSTP_setter(set_flag=False)
            if progress:
                progress.end()
            if generator:
                del generator

    def submit_task(self, name, *args, **kwargs):
        callback = kwargs.pop('callback', None)
        tid = self.submit_task_common_routine(name, callback, *args)

        if self.variables.get('tasks_blocking'):
            error_msgs = self.wait_for_task_with_progress(tid)
            if error_msgs:
                output_msg(error_msgs)

        return tid

    def eval(self, *args, **kwargs):
        return self.ml.eval(*args, **kwargs)

    def eval_block(self, *args, **kwargs):
        return self.ml.eval_block(*args, **kwargs)


class FlowControlInstruction(BaseException):
    def __init__(self, type, payload=None):
        self.type = type
        self.payload = payload


class CallStackEntry(object):
    def __init__(self, func, args, file, line, column):
        self.func = func
        self.args = args
        self.file = file
        self.line = line
        self.column = column

    def __str__(self):
        return "at {0}({1}), file {2}, line {3}, column {4}".format(
            self.func,
            ', '.join([str(i) for i in self.args]),
            self.file,
            self.line,
            self.column
        )


class Function(object):
    def __init__(self, context, name, param_names, exp, env):
        self.context = context
        self.name = name
        self.param_names = param_names
        self.exp = exp
        self.env = env

    def __call__(self, *args):
        env = Environment(self.context, self.env, zip(self.param_names, args))
        try:
            self.context.eval_block(self.exp, env, False)
        except FlowControlInstruction as f:
            if f.type == FlowControlInstructionType.RETURN:
                return f.payload

            raise f

    def __str__(self):
        return "<user-defined function '{0}'>".format(self.name)

    def __repr__(self):
        return str(self)


class BuiltinFunction(object):
    def __init__(self, context, name, f):
        self.context = context
        self.name = name
        self.f = f

    def __call__(self, *args):
        return self.f(*args)

    def __str__(self):
        return "<built-in function '{0}'>".format(self.name)

    def __repr__(self):
        return str(self)


class Environment(dict):
    class Variable(object):
        def __init__(self, value, const=False):
            self.value = value
            self.const = const

    def __init__(self, context, outer=None, iterable=None):
        super(Environment, self).__init__()
        self.context = context
        self.outer = outer
        if iterable:
            for k, v in iterable:
                self[k] = Environment.Variable(v)

    def find(self, var):
        if var in self:
            return self[var]

        if self.outer is not None:
            return self.outer.find(var)

        if var in self.context.builtin_functions:
            return BuiltinFunction(self.context, var, self.context.builtin_functions.get(var))

        raise KeyError(var)


class MainLoop(object):
    pipe_commands = {
        'search': SearchPipeCommand,
        'exclude': ExcludePipeCommand,
        'sort': SortPipeCommand,
        'limit': LimitPipeCommand,
        'select': SelectPipeCommand,
        'find': FindPipeCommand,
        'more': MorePipeCommand,
        'less': MorePipeCommand,
        'older_than': OlderThanPipeCommand,
        'newer_than': NewerThanPipeCommand
    }
    base_builtin_commands = {
        '?': IndexCommand,
        'login': LoginCommand,
        'exit': ExitCommand,
        'setopt': SetoptCommand,
        'printopt': PrintoptCommand,
        'saveopt': SaveoptCommand,
        'setenv': SetenvCommand,
        'printenv': PrintenvCommand,
        'shell': ShellCommand,
        'help': HelpCommand,
        'top': TopCommand,
        'showips': ShowIpsCommand,
        'showurls': ShowUrlsCommand,
        'source': SourceCommand,
        'dump': DumpCommand,
        'clear': ClearCommand,
        'history': HistoryCommand,
        'echo': EchoCommand,
        'whoami': WhoamiCommand,
        'pending': PendingCommand,
        'wait': WaitCommand,
        'alias': AliasCommand,
        'unalias': UnaliasCommand,
        'vars': ListVarsCommand,
        'attach_debugger': AttachDebuggerCommand,
        'cd': ChangeNamespaceCommand,
        'w': WCommand,
        'time': TimeCommand,
        'remote': RemoteCommand
    }
    builtin_commands = base_builtin_commands.copy()
    builtin_commands.update(pipe_commands)

    def __init__(self, context):
        self.context = context
        self.root_path = [self.context.root_ns]
        self.path = self.root_path[:]
        self.prev_path = self.path[:]
        self.start_from_root = False
        self.namespaces = []
        self.aliases = {}
        self.connection = None
        self.saved_state = None

    def __get_prompt(self):
        variables = collections.defaultdict(lambda: '', {
            'path': '/'.join([str(x.get_name()) for x in self.path]),
            'host': self.context.uri,
            'user': self.context.user,
            'jobs': self.context.pending_jobs,
            'jobs_short': '[{0}] '.format(self.context.pending_jobs) if self.context.pending_jobs else '',
            '#0': '\001\033[0m\002',
            '#bold': '\001\033[1m\002',
            '#dim': '\001\033[2m\002',
            '#under': '\001\033[4m\002',
            '#blink': '\001\033[5m\002',
            '#reverse': '\001\033[7m\002',
            '#hidden': '\001\033[8m\002',
            '#f_black': '\001\033[30m\002',
            '#f_red': '\001\033[31m\002',
            '#f_green': '\001\033[32m\002',
            '#f_yellow': '\001\033[33m\002',
            '#f_blue': '\001\033[34m\002',
            '#f_magenta': '\001\033[35m\002',
            '#f_cyan': '\001\033[36m\002',
            '#f_white': '\001\033[37m\002',
            '#b_black': '\001\033[40m\002',
            '#b_red': '\001\033[41m\002',
            '#b_green': '\001\033[42m\002',
            '#b_yellow': '\001\033[43m\002',
            '#b_blue': '\001\033[44m\002',
            '#b_magenta': '\001\033[45m\002',
            '#b_cyan': '\001\033[46m\002',
            '#b_white': '\001\033[47m\002'
        })
        return self.context.variables.get('prompt').format(**variables)

    def greet(self):
        # output_msg(
        #     _("Welcome to the FreeNAS CLI! Type 'help' to get started."))
        output_msg(self.context.connection.call_sync(
            'system.general.cowsay',
            "Welcome to the FreeNAS CLI! Type 'help' to get started."
        )[0])
        output_msg("")

    def cd(self, ns):
        if not self.cwd.on_leave():
            return

        self.prev_path = self.path[:]
        self.path.append(ns)
        self.cwd.on_enter()

    def cd_up(self):
        if not self.cwd.on_leave():
            return

        self.prev_path = self.path[:]
        if len(self.path) > 1:
            del self.path[-1]
        self.cwd.on_enter()

    @property
    def cwd(self):
        return self.path[-1]

    @property
    def path_string(self):
        return ' '.join([str(x.get_name()) for x in self.path[1:]])

    def input(self, prompt=None):
        if not prompt:
            prompt = self.__get_prompt()

        line = six.moves.input(prompt).strip()

        if line:
            readline.remove_history_item(readline.get_current_history_length() - 1)

        return line

    def repl(self):
        readline.parse_and_bind('tab: complete')
        readline.set_completer(self.complete)
        readline.set_completer_delims(' \t\n`~!@#$%^&*()=+[{]}\\|;\',<>?')

        self.greet()
        a = ShowUrlsCommand()
        try:
            format_output(a.run(self.context, None, None, None))
        except:
            output_msg(_('Cannot show GUI urls'))

        while True:
            try:
                line = self.input()
            except EOFError:
                six.print_()
                return
            except KeyboardInterrupt:
                six.print_()
                output_msg(_('User terminated command'))
                continue

            output_lock.acquire()
            self.process(line)
            output_lock.release()

    def find_in_scope(self, token, **kwargs):
        cwd = kwargs.pop('cwd', self.cwd)
        env = kwargs.pop('env', self.context.global_env)
        variables = kwargs.pop('variables', self.context.variables)

        if hasattr(cwd, 'namespace_by_name'):
            ns = cwd.namespace_by_name(token)
            if ns:
                return ns

        cwd_namespaces = cwd.namespaces()
        cwd_commands = list(cwd.commands().items())

        if isinstance(token, six.string_types) and token.startswith('@'):
            token = token[1:]
        else:
            for ns in cwd_namespaces:
                if token == ns.get_name():
                    return ns

        for name, cmd in cwd_commands:
            if token == name:
                cmd.env = env
                cmd.variables = variables
                return cmd

        if token in list(self.builtin_commands.keys()):
            cmd = self.builtin_commands[token]()
            cmd.env = env
            cmd.variables = variables
            return cmd

        if token in list(self.aliases.keys()):
            return Alias(self.context, self.aliases[token])

        for ns, name, fn in self.context.user_commands:
            if fnmatch.fnmatch(self.path_string, ns) and name == token:
                fn.env = env
                fn.variables = variables
                return fn

        return None

    def eval_block(self, block, env=None, allow_break=False):
        if env is None:
            env = self.context.global_env

        for stmt in block:
            try:
                ret = self.eval(stmt, env=env, first=True)
            except SystemExit:
                raise
            except BaseException as e:
                if self.context.variables.get('abort_on_errors'):
                    raise e

                continue

            if type(ret) is FlowControlInstruction:
                if ret.type == FlowControlInstructionType.BREAK:
                    if not allow_break:
                        raise SyntaxError("'break' cannot be used in this block")

                raise ret

    def get_cwd(self, path):
        if not path:
            return self.cwd
        else:
            real_path = self.path[:]
            for i in path:
                if i == '..':
                    if len(real_path) > 1:
                        real_path.pop(-1)
                else:
                    real_path.append(i)
            return real_path[-1]

    def reset_on_first_run(self):
        self.context.pipe_cwd = None

    def eval(self, token, **kwargs):
        path = kwargs.pop('path', [])
        serialize_filter = kwargs.pop('serialize_filter', None)
        input_data = kwargs.pop('input_data', None)
        dry_run = kwargs.pop('dry_run', None)
        first = kwargs.pop('first', False)
        env = kwargs.pop('env', self.context.global_env)
        variables = kwargs.pop('variables', self.context.variables)
        cwd = self.get_cwd(path)

        if not token:
            return []

        if first:
            self.reset_on_first_run()

        if self.start_from_root:
            path = self.root_path[:]
            self.start_from_root = False

        try:
            if isinstance(token, list):
                return [self.eval(i, env=env, path=path) for i in token]

            if isinstance(token, Parentheses):
                return self.eval(token.expr, env=env, path=path)

            if isinstance(token, UnaryExpr):
                expr = self.eval(token.expr, env=env)
                if token.op == '-':
                    return -expr

                return self.context.builtin_operators[token.op](expr)

            if isinstance(token, BinaryExpr):
                left = self.eval(token.left, env=env)
                right = self.eval(token.right, env=env)
                return self.context.builtin_operators[token.op](left, right)

            if isinstance(token, Literal):
                if token.type in six.string_types:
                    return token.value.replace('\\\"', '"')

                if token.type is list:
                    return [self.eval(i, env=env) for i in token.value]

                if token.type is dict:
                    return {self.eval(k, env=env): self.eval(v, env=env) for k, v in token.value.items()}

                return token.value

            if isinstance(token, AnonymousFunction):
                return Function(self.context, '<anonymous>', token.args, token.body, env)

            if isinstance(token, Symbol):
                try:
                    item = env.find(token.name)
                    return item.value if isinstance(item, Environment.Variable) else item
                except KeyError:
                    item = self.find_in_scope(token.name, cwd=cwd, env=env, variables=variables)
                    if item is not None:
                        return item

                    item = self.find_in_scope(token.name.split('/')[0], cwd=cwd, env=env, variables=variables) \
                        if isinstance(token.name, str) \
                        else None

                    if item is not None:
                        raise SyntaxError("Use of slashes as separators not allowed. Please use spaces instead or "
                                          "use the 'cd' command to navigate")

                # After all scope checks are done check if this is a
                # config environment var of the cli
                try:
                    return self.context.variables.variables[token.name].value
                except KeyError:
                    pass

                raise SyntaxError(_('{0} not found'.format(token.name)))

            if isinstance(token, AssignmentStatement):
                expr = self.eval(token.expr, env=env, first=first)
               
                # Table data needs to be flattened upon assignment
                if isinstance(expr, Table):
                    rows = list(expr.data)
                    expr.data = rows

                if token.name in self.context.variables.variables:
                    raise SyntaxError(_(
                        "{0} is a configuration variable. Use `setopt` command to set it".format(token.name)
                    ))

                if isinstance(token.name, Subscript):
                    array = self.eval(token.name.expr, env=env)
                    index = self.eval(token.name.index, env=env)
                    array[index] = expr
                    return

                try:
                    var = env.find(token.name)
                    if var.const:
                        raise SyntaxError('{0} is defined as a constant'.format(token.name))

                    var.value = expr
                except KeyError:
                    env[token.name] = Environment.Variable(expr)

                return

            if isinstance(token, ConstStatement):
                expr = self.eval(token.expr, env=env, first=first)
                env[token.name.name] = Environment.Variable(expr, True)
                return

            if isinstance(token, IfStatement):
                expr = self.eval(token.expr, env=env)
                body = token.body if expr else token.else_body
                local_env = Environment(self.context, outer=env)
                self.eval_block(body, local_env, False)
                return

            if isinstance(token, ForStatement):
                local_env = Environment(self.context, outer=env)
                self.eval(token.stmt1, env=local_env)

                while self.eval(token.expr, env=local_env):
                    self.eval_block(token.body, local_env, True)
                    self.eval(token.stmt2, env=local_env)

                return

            if isinstance(token, ForInStatement):
                local_env = Environment(self.context, outer=env)
                expr = self.eval(token.expr, env=env)
                if isinstance(token.var, tuple):
                    if isinstance(expr, dict):
                        expr_iter = expr.items()
                    else:
                        expr_iter = expr.copy()
                    for k, v in expr_iter:
                        local_env[token.var[0]] = k
                        local_env[token.var[1]] = v
                        try:
                            self.eval_block(token.body, local_env, True)
                        except FlowControlInstruction as f:
                            if f.type == FlowControlInstructionType.BREAK:
                                return

                            raise f
                else:
                    for i in expr:
                        local_env[token.var] = i
                        try:
                            self.eval_block(token.body, local_env, True)
                        except FlowControlInstruction as f:
                            if f.type == FlowControlInstructionType.BREAK:
                                return

                            raise f

                return

            if isinstance(token, WhileStatement):
                local_env = Environment(self.context, outer=env)
                while True:
                    expr = self.eval(token.expr, env=env)
                    if not expr:
                        return

                    try:
                        self.eval_block(token.body, local_env, True)
                    except FlowControlInstruction as f:
                        if f.type == FlowControlInstructionType.BREAK:
                            return

                        raise f

            if isinstance(token, ReturnStatement):
                return FlowControlInstruction(
                    FlowControlInstructionType.RETURN,
                    self.eval(token.expr, env=env)
                )

            if isinstance(token, BreakStatement):
                return FlowControlInstruction(FlowControlInstructionType.BREAK)

            if isinstance(token, UndefStatement):
                del env[token.name]
                return

            if isinstance(token, SyncCommandExpansion):
                expr = self.eval(token.expr, env=env, first=first)
                if hasattr(expr, 'wait'):
                    return expr.wait()

            if isinstance(token, (ExpressionExpansion, CommandExpansion)):
                expr = self.eval(token.expr, env=env, first=first)

                # Table data needs to be flattened upon assignment
                if isinstance(expr, Table):
                    rows = list(expr.data)
                    expr.data = rows

                return expr

            if isinstance(token, CommandCall):
                token = copy.deepcopy(token)
                success = True

                try:
                    if len(token.args) == 0:
                        if path[0] == self.context.root_ns:
                            self.path = self.root_path[:]
                            path.pop(0)
                        for i in path:
                            if i == '..':
                                if len(self.path) > 1:
                                    self.cd_up()
                            else:
                                self.cd(i)

                        return

                    top = token.args.pop(0)
                    if top == '..':
                        if len(token.args) > 0 and isinstance(token.args[0], Symbol) and '/' in token.args[0].name:
                            raise SyntaxError("Use of slashes as separators not allowed. Please use spaces instead or "
                                              "use the 'cd' command to navigate")
                        if len(path) == 0:
                            if len(self.path) > 1:
                                self.path[-2].on_enter()
                        elif path[-1] != '..':
                            path[-1].on_enter()
                        else:
                            if len(self.path) > 1:
                                self.path[-2].on_enter()

                        path.append('..')
                        return self.eval(token, env=env, path=path, dry_run=dry_run)
                    elif isinstance(top, Symbol) and top.name == '/':
                        if first:
                            self.start_from_root = True
                            return self.eval(token, env=env, path=path, dry_run=dry_run)

                    if isinstance(top, ExpressionExpansion):
                        top = Symbol(self.eval(top, env=env, path=path))

                    if isinstance(top, Literal):
                        top = Symbol(top.value)

                    item = self.eval(top, env=env, path=path, dry_run=dry_run)

                    if isinstance(item, Namespace):
                        item.on_enter()
                        return self.eval(token, env=env, path=path+[item], dry_run=dry_run)

                    if isinstance(item, Alias):
                        return self.eval(item.ast, env=env, path=path)[0]

                    if isinstance(item, Command):
                        completions = item.complete(self.context)
                        token_args = convert_to_literals(token.args)
                        if len(token_args) > 0 and token_args[0] == '..':
                            args = [token_args[0]]
                            kwargs = None
                            opargs = None
                        else:
                            args, kwargs, opargs = expand_wildcards(
                                self.context,
                                *sort_args([self.eval(i, env=env) for i in token_args]),
                                completions=completions
                            )

                        item.exec_path = path if len(path) >= 1 else self.path
                        item.cwd = self.cwd
                        item.current_env = env
                        item.variables = variables
                        if dry_run:
                            return item, cwd, args, kwargs, opargs

                        if isinstance(item, PipeCommand):
                            if first:
                                raise CommandException(_('Invalid usage.\n{0}'.format(inspect.getdoc(item))))
                            if serialize_filter:
                                ret = item.serialize_filter(self.context, args, kwargs, opargs)
                                if ret is not None:
                                    if 'filter' in ret:
                                        serialize_filter['filter'] += ret['filter']

                                    if 'params' in ret:
                                        serialize_filter['params'].update(ret['params'])

                            return item.run(self.context, args, kwargs, opargs, input=input_data)
                        else:
                            return item.run(self.context, args, kwargs, opargs)

                except BaseException as err:
                    success = False
                    raise err
                finally:
                    env['_success'] = Environment.Variable(success)

                env['_success'] = Environment.Variable(False)
                raise SyntaxError("Command or namespace {0} not found".format(top.name))

            if isinstance(token, FunctionCall):
                args = list(map(lambda a: self.eval(a, env=env, first=True), token.args))
                func = env.find(token.name)
                if func:
                    if isinstance(func, Environment.Variable):
                        func = func.value

                    self.context.call_stack.append(
                        CallStackEntry(func.name, args, token.file, token.line, token.column)
                    )
                    result = func(*args)
                    self.context.call_stack.pop()
                    return result

                raise SyntaxError("Function {0} not found".format(token.name))

            if isinstance(token, Subscript):
                expr = self.eval(token.expr, env=env)
                index = self.eval(token.index, env=env)
                return expr[index]

            if isinstance(token, FunctionDefinition):
                env[token.name] = Function(self.context, token.name, token.args, token.body, env)
                return

            if isinstance(token, BinaryParameter):
                return token.left, token.op, self.eval(token.right, env=env)

            if isinstance(token, PipeExpr):
                if serialize_filter:
                    self.eval(token.left, env=env, path=path, serialize_filter=serialize_filter)
                    self.eval(token.right, env=env, path=path, serialize_filter=serialize_filter)
                    return

                cmd, cwd, args, kwargs, opargs = self.eval(token.left, env=env, path=path, dry_run=True, first=first)

                if self.context.pipe_cwd is None:
                    cwd.on_enter()
                    self.context.pipe_cwd = cwd

                if isinstance(cmd, FilteringCommand):
                    # Do serialize_filter pass
                    filt = {"filter": [], "params": {}}
                    self.eval(token.right, env=env, path=path, serialize_filter=filt)
                    result = cmd.run(self.context, args, kwargs, opargs, filtering=filt)
                elif isinstance(cmd, PipeCommand):
                    result = cmd.run(self.context, args, kwargs, opargs, input=input_data)
                else:
                    result = cmd.run(self.context, args, kwargs, opargs)

                return self.eval(token.right, input_data=result)

            if isinstance(token, ShellEscape):
                return self.builtin_commands['shell']().run(
                    self.context,
                    [self.eval(t) for t in convert_to_literals(token.args)],
                    {}, {}
                )

            if isinstance(token, Quote):
                return token

            if isinstance(token, Redirection):
                with open(token.path, 'a+') as f:
                    format_output(self.eval(token.body, env=env, path=path, first=first), file=f)
                    return None

        except SystemExit as err:
            raise err

        except BaseException as err:
            raise err

        raise SyntaxError("Invalid syntax: {0}".format(token))

    def process(self, line):
        def add_line_to_history(line):
            readline.add_history(line)
            try:
                with open(os.path.expanduser('~/.cli_history'), 'a') as history_file:
                    history_file.write('\n' + line)
            except IOError:
                pass

        if len(line) == 0:
            return

        if line == '-':
            prev = self.prev_path[:]
            self.prev_path = self.path[:]
            self.path = prev
            return

        try:
            try:
                tokens = parse(line, '<stdin>')
            except KeyboardInterrupt:
                return
            except SyntaxError:
                add_line_to_history(line)
                raise

            if not tokens:
                return

            # Unparse AST to string and add to readline history and history file
            line = '; '.join(unparse(t, oneliner=True) for t in tokens)
            add_line_to_history(line)

            for i in tokens:
                try:
                    self.context.call_stack = []
                    ret = self.eval(i, first=True, printable_none=True)
                except SystemExit as err:
                    raise err
                except BaseException as err:
                    output_msg('Error: {0}'.format(str(err)))
                    if len(self.context.call_stack) > 1:
                        output_msg('Call stack: ')
                        for i in self.context.call_stack:
                            output_msg('  ' + str(i))

                    if self.context.variables.get('debug'):
                        output_msg('Python call stack: ')
                        output_msg(traceback.format_exc())

                    return

                if ret is not None:
                    output = self.context.variables.get('output')
                    if output:
                        with open(output, 'a+') as f:
                            format_output(ret, file=f)
                    else:
                        format_output(ret)
        except SyntaxError as e:
            output_msg(_('Syntax error: {0}'.format(str(e))))
        except KeyboardInterrupt:
            output_msg(_('Interrupted'))
        except CommandException as e:
            output_msg(_('Error: {0}'.format(str(e))))
            self.context.logger.error(e.stacktrace)
            if self.context.variables.get('debug'):
                output_msg(e.stacktrace)
        except RpcException as e:
            if self.context.variables.get('rollbar_enabled'):
                rollbar.report_exc_info()
            self.context.logger.error(str(e))
            output_msg(_('RpcException Error: {0}'.format(str(e))))
        except SystemExit as e:
            sys.exit(e)
        except Exception as e:
            if self.context.variables.get('rollbar_enabled'):
                rollbar.report_exc_info()
            output_msg(_('Unexpected Error: {0}'.format(str(e))))
            error_trace = traceback.format_exc()
            self.context.logger.error(error_trace)
            if self.context.variables.get('debug'):
                output_msg(error_trace)

    def get_relative_object(self, ns, tokens):
        path = self.path[:]
        ptr = ns
        first_len = len(tokens) - 1

        while len(tokens) > 0:
            token = tokens.pop(0)
            if not token:
                continue

            if isinstance(token, Symbol):
                name = token.name
            else:
                name = token

            if name == '/' and len(tokens) == first_len:
                ptr = path[0]
            if name == '..' and len(path) > 1:
                del path[-1]
                ptr = path[-1]
            if name == 'help':
                continue

            if issubclass(type(ptr), Namespace):
                for ns in ptr.namespaces():
                    if ns.get_name() == name:
                        path.append(ns)
                        ptr = path[-1]
                        break

                cmds = ptr.commands()
                if name in cmds:
                    return cmds[name]

                if name in self.builtin_commands:
                    return self.builtin_commands[name]()

        return ptr

    def complete(self, text, state):
        if state == 0:
            def find_arg(args, index):
                positional_index = 0
                for a in args:
                    if isinstance(a, (Literal, Symbol)):
                        if a.column <= index <= a.column_end:
                            return positional_index

                        positional_index += 1

                    if isinstance(a, BinaryParameter):
                        if a.column + len(a.left) + 1 <= index <= a.column_end:
                            return a

                        if a.column <= index <= a.column + len(a.left) + 1:
                            return False

                return positional_index

            try:
                readline_buffer = readline.get_line_buffer()
                token = None
                append_space = False
                args = []
                builtin_command_set = list(self.base_builtin_commands.keys())
                self.saved_state = None

                if len(readline_buffer.strip()) > 0:
                    tokens = parse(readline_buffer, '<stdin>', True)
                    if tokens:
                        token = tokens.pop(-1)
                        if isinstance(token, PipeExpr):
                            token = token.right
                            builtin_command_set = list(self.pipe_commands.keys())

                        args = token.args

                if isinstance(token, CommandCall) or not args:
                    obj = self.get_relative_object(self.cwd, args)
                else:
                    return None

                if issubclass(type(obj), Namespace):
                    choices = [quote(i.get_name()) for i in obj.namespaces()]
                    choices += obj.commands().keys()
                    choices += ['..', '/', '-']

                    if type(obj) is RootNamespace:
                        choices += builtin_command_set
                    else:
                        choices += ['help']

                    if text.startswith('/') and isinstance(obj, RootNamespace):
                        choices = ['/' + i for i in choices]

                    append_space = True
                elif issubclass(type(obj), Command):
                    c_args = []
                    c_kwargs = {}
                    c_opargs = []

                    with contextlib.suppress(BaseException):
                        token_args = convert_to_literals(copy.deepcopy(token).args)

                        if len(token_args) > 0 and token_args[0] == '..':
                            args = [token_args[0]]
                        else:
                            c_args, c_kwargs, c_opargs = expand_wildcards(
                                self.context,
                                *sort_args([self.eval(i) for i in token_args]),
                                completions=obj.complete(self.context, text=text)
                            )

                    completions = obj.complete(self.context, text=text, args=c_args, kwargs=c_kwargs, opargs=c_opargs)
                    choices = [c.name for c in completions if isinstance(c.name, six.string_types)]

                    arg = find_arg(args, readline.get_begidx())
                    if arg is False:
                        return None
                    elif isinstance(arg, six.integer_types):
                        completion = first_or_default(lambda c: c.name == arg, completions)
                        if completion:
                            choices = completion.choices(self.context, None)
                    elif isinstance(arg, BinaryParameter):
                        completion = first_or_default(lambda c: c.name == arg.left + '=', completions)
                        if completion:
                            choices = completion.choices(self.context, arg)
                    else:
                        raise AssertionError('Unknown arg returned by find_arg()')
                else:
                    choices = []

                options = [i + (' ' if append_space else '') for i in choices if i.startswith(text)]
                self.saved_state = options

                if options:
                    return options[0]
            except BaseException as err:
                output_msg(str(err))
                if self.context.variables.get('debug'):
                    output_msg(traceback.format_exc())
        else:
            if self.saved_state:
                if state < len(self.saved_state):
                    return self.saved_state[state]
                else:
                    return None

    def sigint(self):
        pass

    def blank_readline(self):
        cols = get_terminal_size((80, 20)).columns
        text_len = len(readline.get_line_buffer()) + 2
        sys.stdout.write('\x1b[2K')
        sys.stdout.write('\x1b[1A\x1b[2K' * int(text_len / (cols or 80)))
        sys.stdout.write('\x1b[0G')
        sys.stdout.flush()

    def restore_readline(self):
        sys.stdout.write(self.__get_prompt() + readline.get_line_buffer().rstrip())
        sys.stdout.flush()


def main(argv=None):
    if not argv:
        argv = sys.argv[1:]

    if CLI_LOG_DIR:
        current_cli_logfile = os.path.join(CLI_LOG_DIR, 'freenascli.{0}.log'.format(os.getpid()))
        logging.basicConfig(filename=current_cli_logfile, level=logging.DEBUG)
        # create symlink to latest created cli log
        # but first check if previous exists and nuke it
        try:
            if platform.system() != 'Windows':
                latest_log = os.path.join(CLI_LOG_DIR, 'freenascli.latest.log')
                if os.path.lexists(latest_log):
                    os.unlink(latest_log)
                os.symlink(current_cli_logfile, latest_log)
                # Try to set the permissions on this symlink to be readable, writable by all
                os.chmod(latest_log, 0o777)
        except OSError:
            # not there no probs or cannot make this symlink move on
            pass

    if os.environ.get('FREENAS_SYSTEM'):
        parser = argparse.ArgumentParser(prog="cli")
    else:
        parser = argparse.ArgumentParser()
    parser.add_argument('uri', metavar='URI', nargs='?',
                        default='unix:')
    parser.add_argument('--makedocs', action='store_true', help='Generate CLI documentation metadata and leave')
    parser.add_argument('-m', metavar='MIDDLEWARECONFIG',
                        default=DEFAULT_MIDDLEWARE_CONFIGFILE)
    parser.add_argument('-c', metavar='CONFIG', default=DEFAULT_CLI_CONFIGFILE)
    parser.add_argument('-e', metavar='COMMANDS')
    parser.add_argument('-f', metavar='INPUT')
    parser.add_argument('-p', metavar='PASSWORD')
    parser.add_argument('-D', metavar='DEFINE', action='append')
    args = parser.parse_args(argv)

    context = Context()
    context.argparse_parser = parser
    context.docgen_run = args.makedocs

    if not context.docgen_run and os.environ.get('FREENAS_SYSTEM') != 'YES' and args.uri == 'unix:':
        args.uri = six.moves.input('Please provide FreeNAS IP: ')

    context.uri = args.uri
    context.parsed_uri = urlparse(args.uri)
    if context.parsed_uri.scheme == '':
        context.parsed_uri = urlparse("ws://" + args.uri)
    if context.parsed_uri.scheme == 'ws':
        context.uri = context.parsed_uri.hostname
    username = None
    if context.parsed_uri.hostname is None:
        context.hostname = 'localhost'
    else:
        context.hostname = context.parsed_uri.hostname
    if (
        not context.docgen_run and
        context.parsed_uri.scheme != 'unix' and
        context.parsed_uri.netloc not in ('localhost', '127.0.0.1', None)
    ):
        if context.parsed_uri.username is None:
            username = six.moves.input('Please provide a username: ')
            if context.parsed_uri.scheme == 'ssh':
                context.uri = 'ssh://{0}@{1}'.format(username, context.parsed_uri.hostname)
                if context.parsed_uri.port is not None:
                    context.uri = "{0}:{1}".format(context.uri, context.parsed_uri.port)
                context.parsed_uri = urlparse(context.uri)
        else:
            username = context.parsed_uri.username
        if args.p is None:
            try:
                args.p = getpass.getpass('Please provide a password: ')
            except KeyboardInterrupt:
                six.print_()
                return
        else:
            args.p = args.p
    else:
        context.local_connection = True

    context.read_middleware_config_file(args.m)
    context.variables.load(args.c)
    context.start(args.p)

    ml = MainLoop(context)
    context.ml = ml

    if args.makedocs:
        builtin_cmds = context.ml.base_builtin_commands
        filtering_cmds = context.ml.pipe_commands

        base_commands = [[name, instance()] for name, instance in builtin_cmds.items()]
        filtering_commands = [[name, instance()] for name, instance in filtering_cmds.items()]
        root_namespaces = context.root_ns.namespaces()

        docgen = CliDocGen()
        docgen.load_global_base_commands(base_commands)
        docgen.load_global_filtering_commands(filtering_commands)
        docgen.load_root_namespaces(root_namespaces)
        docgen.write_docs()
        return

    if username is not None:
        context.login(username, args.p)
        context.user = username
    elif context.local_connection:
        context.user = getpass.getuser()
        context.login(context.user, '')

    if args.D:
        for i in args.D:
            name, value = i.split('=')
            context.variables.set(name, value)

    if args.e:
        context.wait_entity_subscribers()
        ml.process(args.e)
        return

    if args.f:
        context.wait_entity_subscribers()
        try:
            f = sys.stdin if args.f == '-' else open(args.f)
            for line in f:
                ml.process(line.strip())

            f.close()
        except EnvironmentError as e:
            sys.stderr.write('Cannot open input file: {0}'.format(str(e)))
            sys.exit(1)

        return

    try:
        with open(os.path.expanduser('~/.cli_history'), 'rb') as history_file:
            history_list = history_file.read().decode('utf8', 'ignore').splitlines()
            history_list = history_list[-1000:]
            for line in history_list:
                readline.add_history(line)
    except FileNotFoundError:
        pass

    cli_rc_paths = ['/usr/local/etc/clirc', os.path.expanduser('~/.clirc')]
    for path in cli_rc_paths:
        if os.path.isfile(path):
            try:
                with open(path, 'r') as f:
                    ast = parse(f.read(), path)
                    context.eval_block(ast)
            except UnicodeDecodeError as e:
                raise CommandException(_(
                    "Incorrect filetype, cannot parse clirc file: {0}".format(str(e))
                ))

    ml.repl()


if __name__ == '__main__':
    main(sys.argv[1:])
