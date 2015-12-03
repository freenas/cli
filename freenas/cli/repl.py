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

import sys
import os
import glob
import argparse
import shlex
import imp
import logging
import errno
import platform
import json
import time
import gettext
import getpass
import traceback
import six
import paramiko
from urllib.parse import urlparse
from socket import gaierror as socket_error
from freenas.cli.descriptions import events
from freenas.cli import config
from freenas.cli.namespace import Namespace, RootNamespace, Command, FilteringCommand, CommandException
from freenas.cli.parser import parse, Symbol, Set, CommandExpansion, Literal, BinaryExpr, PipeExpr
from freenas.cli.output import (
    ValueType, Object, Table, ProgressBar, output_lock, output_msg, read_value, format_value,
    output_object, output_table
)
from freenas.dispatcher.client import Client, ClientError
from freenas.dispatcher.entity import EntitySubscriber
from freenas.dispatcher.rpc import RpcException
from freenas.utils.query import wrap
from freenas.cli.commands import (
    ExitCommand, PrintenvCommand, SetenvCommand, ShellCommand, ShutdownCommand,
    RebootCommand, EvalCommand, HelpCommand, ShowUrlsCommand, ShowIpsCommand,
    TopCommand, ClearCommand, HistoryCommand, SaveenvCommand, EchoCommand,
    SourceCommand, LessPipeCommand, SearchPipeCommand, ExcludePipeCommand,
    SortPipeCommand, LimitPipeCommand, SelectPipeCommand, LoginCommand
)
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
CLI_LOG_DIR = os.getcwd()
if os.environ.get('FREENAS_SYSTEM') == 'YES':
    DEFAULT_MIDDLEWARE_CONFIGFILE = '/usr/local/etc/middleware.conf'
    CLI_LOG_DIR = '/var/tmp'

DEFAULT_CLI_CONFIGFILE = os.path.join(os.getcwd(), '.freenascli.conf')

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


PROGRESS_CHARS = ['-', '\\', '|', '/']
EVENT_MASKS = [
    'client.logged',
    'task.created',
    'task.updated',
    'task.progress',
    'service.stopped',
    'service.started'
]
ENTITY_SUBSCRIBERS = [
    'user',
    'group',
    'disk',
    'volume',
    'volume.snapshot',
    'share',
    'task',
    'alert'
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


class VariableStore(object):
    class Variable(object):
        def __init__(self, default, type, choices=None):
            self.default = default
            self.type = type
            self.choices = choices
            self.value = default

        def set(self, value):
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
            'output_format': self.Variable('ascii', ValueType.STRING,
                                           ['ascii', 'json', 'table']),
            'datetime_format': self.Variable('natural', ValueType.STRING),
            'language': self.Variable(os.getenv('LANG', 'C'),
                                      ValueType.STRING),
            'prompt': self.Variable('{host}:{path}>', ValueType.STRING),
            'timeout': self.Variable(10, ValueType.NUMBER),
            'tasks_blocking': self.Variable(False, ValueType.BOOLEAN),
            'show_events': self.Variable(True, ValueType.BOOLEAN),
            'debug': self.Variable(False, ValueType.BOOLEAN)
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


class Context(object):
    def __init__(self):
        self.uri = None
        self.parsed_uri = None
        self.hostname = None
        self.connection = Client()
        self.ml = None
        self.logger = logging.getLogger('cli')
        self.plugin_dirs = []
        self.task_callbacks = {}
        self.plugins = {}
        self.variables = VariableStore()
        self.root_ns = RootNamespace('')
        self.event_masks = ['*']
        self.event_divert = False
        self.event_queue = six.moves.queue.Queue()
        self.keepalive_timer = None
        self.argparse_parser = None
        self.entity_subscribers = {}
        config.instance = self

    @property
    def is_interactive(self):
        return os.isatty(sys.stdout.fileno())

    def start(self, password=None):
        self.discover_plugins()
        self.connect(password)

    def start_entity_subscribers(self):
        for i in ENTITY_SUBSCRIBERS:
            e = EntitySubscriber(self.connection, i)
            e.start()
            self.entity_subscribers[i] = e

    def connect(self, password=None):
        try:
            self.connection.connect(self.uri, password=password)
        except socket_error as err:
            output_msg(_(
                "Could not connect to host: {0} due to error: {1}".format(
                    self.parsed_uri.hostname, err)
            ))
            self.argparse_parser.print_help()
            sys.exit(1)
        except paramiko.ssh_exception.AuthenticationException as err:
            output_msg(_(
                "Incorrect username or password"))
            sys.exit(1)
        except ConnectionRefusedError as err:
            output_msg(_(
                "Connection refused by host: {0}".format(
                    self.parsed_uri.hostname)))
            sys.exit(1)

    def login(self, user, password):
        try:
            self.connection.login_user(user, password)
            self.connection.subscribe_events(*EVENT_MASKS)
            self.connection.on_event(self.handle_event)
            self.connection.on_error(self.connection_error)
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
                plug_dirs = os.path.join(
                    os.path.dirname(os.path.realpath(__file__)), 'plugins'
                )
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
        plugin = imp.load_source(name, path)

        if hasattr(plugin, '_init'):
            plugin._init(self)
            self.plugins[path] = plugin

    def __try_reconnect(self):
        output_lock.acquire()
        self.ml.blank_readline()

        output_msg(_('Connection lost! Trying to reconnect...'))
        retries = 0
        while True:
            retries += 1
            try:
                time.sleep(2)
                self.connect(getpass.getpass())
                try:
                    if self.parsed_uri.hostname == '127.0.0.1' or \
                            self.parsed_uri.scheme == 'unix':
                        self.connection.login_user(getpass.getuser(), '')
                    else:
                        self.connection.login_token(self.connection.token)

                    self.connection.subscribe_events(*EVENT_MASKS)
                except RpcException:
                    output_msg(_("Reauthentication failed (most likely token expired or server was restarted)"))
                    sys.exit(1)
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

    def connection_error(self, event, **kwargs):
        if event == ClientError.LOGOUT:
            output_msg('Logged out from server.')
            self.connection.disconnect()
            sys.exit(0)

        if event == ClientError.CONNECTION_CLOSED:
            time.sleep(1)
            self.__try_reconnect()
            return

    def handle_event(self, event, data):
        if event == 'task.updated':
            if data['id'] in self.task_callbacks:
                self.handle_task_callback(data)

        self.print_event(event, data)

    def handle_task_callback(self, data):
        if data['state'] in ('FINISHED', 'CANCELLED', 'ABORTED', 'FAILED'):
            self.task_callbacks[data['id']](data['state'])

    def print_event(self, event, data):
        if self.event_divert:
            self.event_queue.put((event, data))
            return

        if event == 'task.progress':
            return

        output_lock.acquire()
        self.ml.blank_readline()

        translation = events.translate(self, event, data)
        if translation:
            output_msg(translation)
            if 'state' in data:
                if data['state'] == 'FAILED':
                    status = self.connection.call_sync('task.status', data['id'])
                    output_msg(_(
                        "Task #{0} error: {1}".format(
                            data['id'],
                            status['error'].get('message', '') if status.get('error') else ''
                        )
                    ))

        sys.stdout.flush()
        self.ml.restore_readline()
        output_lock.release()

    def call_sync(self, name, *args, **kwargs):
        return wrap(self.connection.call_sync(name, *args, **kwargs))

    def call_task_sync(self, name, *args, **kwargs):
        self.ml.skip_prompt_print = True
        wrapped_result = wrap(self.connection.call_task_sync(name, *args))
        self.ml.skip_prompt_print = False
        return wrapped_result

    def submit_task(self, name, *args, **kwargs):
        callback = kwargs.pop('callback', None)
        message_formatter = kwargs.pop('message_formatter', None)

        if not self.variables.get('tasks_blocking'):
            tid = self.connection.call_sync('task.submit', name, args)
            if callback:
                self.task_callbacks[tid] = callback

            return tid
        else:
            output_msg(_("Hit Ctrl+C to terminate task if needed"))
            self.event_divert = True
            tid = self.connection.call_sync('task.submit', name, args)
            progress = ProgressBar()
            try:
                while True:
                    event, data = self.event_queue.get()

                    if event == 'task.progress' and data['id'] == tid:
                        message = data['message']
                        if isinstance(message_formatter, collections.Callable):
                            message = message_formatter(message)
                        progress.update(percentage=data['percentage'], message=message)

                    if event == 'task.updated' and data['id'] == tid:
                        progress.update(message=data['state'])
                        if data['state'] == 'FINISHED':
                            progress.finish()
                            break

                        if data['state'] == 'FAILED':
                            print()
                            break
            except KeyboardInterrupt:
                print()
                output_msg(_("User requested task termination. Task abort signal sent"))
                self.call_sync('task.abort', tid)

        self.event_divert = False
        return tid


class MainLoop(object):
    pipe_commands = {
        'search': SearchPipeCommand(),
        'exclude': ExcludePipeCommand(),
        'sort': SortPipeCommand(),
        'limit': LimitPipeCommand(),
        'select': SelectPipeCommand(),
        'less': LessPipeCommand()
    }
    base_builtin_commands = {
        'login': LoginCommand(),
        'exit': ExitCommand(),
        'setenv': SetenvCommand(),
        'printenv': PrintenvCommand(),
        'saveenv': SaveenvCommand(),
        'shell': ShellCommand(),
        'eval': EvalCommand(),
        'shutdown': ShutdownCommand(),
        'reboot': RebootCommand(),
        'help': HelpCommand(),
        'top': TopCommand(),
        'showips': ShowIpsCommand(),
        'showurls': ShowUrlsCommand(),
        'source': SourceCommand(),
        'clear': ClearCommand(),
        'history': HistoryCommand(),
        'echo': EchoCommand(),
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
        self.connection = None
        self.skip_prompt_print = False
        self.cached_values = {
            'rel_cwd': None,
            'rel_tokens': None,
            'rel_ptr': None,
            'rel_ptr_namespaces': None,
            'obj': None,
            'obj_namespaces': None,
            'choices': None,
            'scope_cwd': None,
            'scope_namespaces': None,
            'scope_commands': None,
        }

    def __get_prompt(self):
        variables = {
            'path': '/'.join([str(x.get_name()) for x in self.path]),
            'host': self.context.uri
        }
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

    def repl(self):
        readline.parse_and_bind('tab: complete')
        readline.set_completer(self.complete)

        self.greet()
        a = ShowUrlsCommand()
        try:
            a.run(self.context, None, None, None)
        except:
            output_msg(_('Cannot show GUI urls'))

        while True:
            try:
                line = six.moves.input(self.__get_prompt()).strip()
            except EOFError:
                print()
                return
            except KeyboardInterrupt:
                print()
                output_msg(_('User terminated command'))
                continue

            self.process(line)

    def find_in_scope(self, token):
        if token in list(self.builtin_commands.keys()):
            return self.builtin_commands[token]

        cwd_namespaces = self.cached_values['scope_namespaces']
        cwd_commands = self.cached_values['scope_commands']
        if (
            self.cached_values['scope_cwd'] != self.cwd or
            self.cached_values['scope_namespaces'] is not None
           ):
            cwd_namespaces = self.cwd.namespaces()
            cwd_commands = list(self.cwd.commands().items())
            self.cached_values.update({
                'scope_cwd': self.cwd,
                'scope_namespaces': cwd_namespaces,
                'scope_commands': cwd_commands,
                })
        for ns in cwd_namespaces:
            if token == ns.get_name():
                return ns

        for name, cmd in cwd_commands:
            if token == name:
                return cmd

        return None

    def convert_literals(self, tokens):
        for i in tokens:
            if isinstance(i, Symbol):
                # Convert symbol to string
                yield i.name

            if isinstance(i, Set):
                yield i.value

            if isinstance(i, Literal):
                yield i.value

            if isinstance(i, BinaryExpr):
                if isinstance(i.right, Literal):
                    yield (i.left, i.op, i.right.value)

                if isinstance(i.right, Symbol):
                    # Convert symbol to string
                    yield (i.left, i.op, i.right.name)

                if isinstance(i.right, Set):
                    yield (i.left, i.op, i.right.value)

                if isinstance(i.right, CommandExpansion):
                    yield (i.left, i.op, self.eval(i.right.expr))

    def format_output(self, object):
        if isinstance(object, list):
            for i in object:
                self.format_output(i)

        if isinstance(object, Object):
            output_object(object)

        if isinstance(object, Table):
            output_table(object)

        if isinstance(object, (str, int, bool)):
            output_msg(object)

    def eval(self, tokens):
        oldpath = self.path[:]
        if self.start_from_root:
            self.path = self.root_path[:]
            self.start_from_root = False
        command = None
        pipe_stack = []
        args = []

        while tokens:
            token = tokens.pop(0)

            if isinstance(token, Symbol):
                if token.name == '..':
                    self.cd_up()
                    continue

                item = self.find_in_scope(token.name)

                if command:
                    args.append(token)
                    continue

                if isinstance(item, Namespace):
                    self.cd(item)
                    continue

                if isinstance(item, Command):
                    command = item
                    continue

                try:
                    raise SyntaxError("Command or namespace {0} not found".format(token.name))
                finally:
                    self.path = oldpath

            if isinstance(token, CommandExpansion):
                if not command:
                    try:
                        raise SyntaxError("Command expansion cannot replace command or namespace name")
                    finally:
                        self.path = oldpath

                result = self.eval(token.expr)
                if not isinstance(result, str):
                    try:
                        raise SyntaxError("Can only use command expansion with commands returning single value")
                    finally:
                        self.path = oldpath

                args.append(Literal(result, type(result)))
                continue

            if isinstance(token, Set):
                if not command:
                    try:
                        raise SyntaxError(_('Command or namespace "{0}" not found'.format(token.value)))
                    finally:
                        self.path = oldpath

                continue

            if isinstance(token, (Literal, BinaryExpr)):
                if not command and isinstance(token, Literal):
                    item = self.find_in_scope(token.value)
                    if isinstance(item, Namespace):
                        self.cd(item)
                        continue

                args.append(token)
                continue

            if isinstance(token, PipeExpr):
                pipe_stack.append(token.right)
                tokens += token.left

        args = list(self.convert_literals(args))
        args, kwargs, opargs = sort_args(args)
        filter_ops = []
        filter_params = {}

        if not command:
            if len(args) > 0:
                raise SyntaxError('No command specified')

            return

        tmpath = self.path[:]

        if isinstance(command, FilteringCommand):
            top_of_stack = True
            for p in pipe_stack[:]:
                pipe_cmd = self.find_in_scope(p[0].name)
                if not pipe_cmd:
                    try:
                        raise SyntaxError("Pipe command {0} not found".format(p[0].name))
                    finally:
                        self.path = oldpath
                if pipe_cmd.must_be_last and not top_of_stack:
                    try:
                        raise SyntaxError(_("The {0} command must be used at the end of the pipe list").format(p[0].name))
                    finally:
                        self.path = oldpath
                top_of_stack = False

                pipe_args = self.convert_literals(p[1:])
                try:
                    ret = pipe_cmd.serialize_filter(self.context, *sort_args(pipe_args))

                    if 'filter' in ret:
                        filter_ops += ret['filter']

                    if 'params' in ret:
                        filter_params.update(ret['params'])

                except NotImplementedError:
                    continue
                except CommandException:
                    raise
                finally:
                    self.path = oldpath

                # If serializing filter succeeded, remove it from pipe stack
                pipe_stack.remove(p)

            ret = command.run(self.context, args, kwargs, opargs, filtering={
                'filter': filter_ops,
                'params': filter_params
            })
        else:
            try:
                ret = command.run(self.context, args, kwargs, opargs)
            finally:
                self.path = oldpath

        for i in pipe_stack:
            pipe_cmd = self.find_in_scope(i[0].name)
            pipe_args = self.convert_literals(i[1:])
            try:
                ret = pipe_cmd.run(self.context, *sort_args(pipe_args), input=ret)
            except CommandException:
                raise
            except Exception as e:
                raise CommandException(_('Unexpected Error: {0}'.format(str(e))))
            finally:
                self.path = oldpath

        if self.path != tmpath:
            # Command must have modified the path
            return ret

        self.path = oldpath
        return ret

    def process(self, line):
        if len(line) == 0:
            return

        if line[0] == '!':
            self.builtin_commands['shell'].run(
                self.context, [line[1:]], {}, {})
            return

        if line[0] == '/':
            if line.strip() == '/':
                self.prev_path = self.path[:]
                self.path = self.root_path[:]
                return
            else:
                self.start_from_root = True
                line = line[1:]

        if line == '-':
            prev = self.prev_path[:]
            self.prev_path = self.path[:]
            self.path = prev
            return

        try:
            i = parse(line)
            self.format_output(self.eval(i))
        except SyntaxError as e:
            output_msg(_('Syntax error: {0}'.format(str(e))))
        except CommandException as e:
            output_msg(_('Error: {0}'.format(str(e))))
            self.context.logger.error(e.stacktrace)
            if self.context.variables.get('debug'):
                output_msg(e.stacktrace)
        except RpcException as e:
            self.context.logger.error(str(e))
            output_msg(_('RpcException Error: {0}'.format(str(e))))
        except SystemExit:
            # We do not want to catch a user entered `exit` so...
            raise
        except Exception as e:
            output_msg(_('Unexpected Error: {0}'.format(str(e))))
            error_trace = traceback.format_exc()
            self.context.logger.error(error_trace)
            if self.context.variables.get('debug'):
                output_msg(error_trace)

    def get_relative_object(self, ns, tokens):
        ptr = ns
        while len(tokens) > 0:
            token = tokens.pop(0)

            if token == '..' and len(self.path) > 1:
                self.prev_path = self.path[:]
                ptr = self.path[-2]

            if issubclass(type(ptr), Namespace):
                if (
                    self.cached_values['rel_ptr'] == ptr and
                    self.cached_values['rel_ptr_namespaces'] is not None
                   ):
                    nss = self.cached_values['rel_ptr_namespaces']
                else:
                    # Try to somehow make the below work as it saves us one .namespace()
                    # lookup. BUt for now it does work and results in stale autocorrect
                    # options hence commenting
                    # if (
                    #     ptr == self.cached_values['obj'] and
                    #     self.cached_values['obj_namespaces'] is not None
                    #    ):
                    #     nss = self.cached_values['obj_namespaces']
                    # else:
                    nss = ptr.namespaces()
                    self.cached_values.update({
                        'rel_ptr': ptr,
                        'rel_ptr_namespaces': nss
                        })
                for ns in nss:
                    if ns.get_name() == token:
                        ptr = ns
                        break

                cmds = ptr.commands()
                if token in cmds:
                    return cmds[token]

                if token in self.builtin_commands:
                    return self.builtin_commands[token]

        return ptr

    def complete(self, text, state):
        readline_buffer = readline.get_line_buffer()
        tokens = shlex.split(readline_buffer.split('|')[-1].strip(), posix=False)

        if "|" in readline_buffer:
            choices = [x + ' ' for x in list(self.pipe_commands.keys())]
            options = [i for i in choices if i.startswith(text)]
            if state < len(options):
                return options[state]
            else:
                return None
        cwd = self.cwd

        if tokens:
            if tokens[0][0] == '/':
                cwd = self.root_path[0]

        obj = self.cached_values['obj']
        if (
            cwd != self.cached_values['rel_cwd'] or
            tokens != self.cached_values['rel_tokens'] or
            self.cached_values['obj'] is None
           ):
            obj = self.get_relative_object(cwd, tokens[:])
            self.cached_values.update({
                'rel_cwd': cwd,
                'rel_tokens': tokens,
                })

        if issubclass(type(obj), Namespace):
            if self.cached_values['obj'] != obj:
                obj_namespaces = obj.namespaces()
                new_choices = [x.get_name() for x in obj_namespaces] + list(obj.commands().keys())
                self.cached_values.update({
                    'obj': obj,
                    'choices': new_choices,
                    'obj_namespaces': obj_namespaces,
                })
            choices = self.cached_values['choices'][:]
            if (
                len(tokens) == 0 or
                (len(tokens) <= 1 and text not in ['', None])
               ):
                choices += list(self.base_builtin_commands.keys()) + ['..', '/', '-']
            elif 'help' not in choices:
                choices += ['help']
            choices = [i + ' ' for i in choices]

        elif issubclass(type(obj), Command):
            if (
                self.cached_values['obj'] != obj or
                self.cached_values['choices'] is None
               ):
                new_choices = obj.complete(self.context, tokens)
                self.cached_values.update({
                    'obj': obj,
                    'choices': new_choices,
                    'obj_namespaces': None,
                })
            choices = self.cached_values['choices'][:]
        else:
            choices = []

        options = [i for i in choices if i.startswith(text)]
        if state < len(options):
            return options[state]
        else:
            return None

    def sigint(self):
        pass

    def blank_readline(self):
        cols = get_terminal_size((80, 20)).columns
        text_len = len(readline.get_line_buffer()) + 2
        sys.stdout.write('\x1b[2K')
        sys.stdout.write('\x1b[1A\x1b[2K' * int(text_len / cols))
        sys.stdout.write('\x1b[0G')

    def restore_readline(self):
        if not self.skip_prompt_print:
            sys.stdout.write(self.__get_prompt() + readline.get_line_buffer().rstrip())
            sys.stdout.flush()


def main():
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
    parser = argparse.ArgumentParser()
    parser.add_argument('uri', metavar='URI', nargs='?',
                        default='unix:')
    parser.add_argument('-m', metavar='MIDDLEWARECONFIG',
                        default=DEFAULT_MIDDLEWARE_CONFIGFILE)
    parser.add_argument('-c', metavar='CONFIG', default=DEFAULT_CLI_CONFIGFILE)
    parser.add_argument('-e', metavar='COMMANDS')
    parser.add_argument('-f', metavar='INPUT')
    parser.add_argument('-p', metavar='PASSWORD')
    parser.add_argument('-D', metavar='DEFINE', action='append')
    args = parser.parse_args()

    if os.environ.get('FREENAS_SYSTEM') != 'YES' and args.uri == 'unix:':
        args.uri = six.moves.input('Please provide FreeNAS IP: ')

    context = Context()
    context.argparse_parser = parser
    context.uri = args.uri
    context.parsed_uri = urlparse(args.uri)
    if context.parsed_uri.scheme == '':
        context.parsed_uri = urlparse("ws://" + args.uri)
    if context.parsed_uri.scheme == 'ws':
        context.uri = context.parsed_uri.hostname
    username = None
    if context.parsed_uri.hostname == None:
        context.hostname = 'localhost'
    else:
        context.hostname = context.parsed_uri.hostname
    if context.parsed_uri.scheme != 'unix' \
            and context.parsed_uri.netloc not in (
                    'localhost', '127.0.0.1', None):
        if context.parsed_uri.username is None:
            username = six.moves.input('Please provide a username: ')
            if context.parsed_uri.scheme == 'ssh':
                context.uri = 'ssh://{0}@{1}'.format(
                        username,
                        context.parsed_uri.hostname)
                if context.parsed_uri.port is not None:
                    context.uri = "{0}:{1}".format(
                            context.uri,
                            context.parsed_uri.port)
                context.parsed_uri = urlparse(context.uri)
        else:
            username = context.parsed_uri.username
        if args.p is None:
            args.p = getpass.getpass('Please provide a password: ')
        else:
            args.p = args.p
            
    context.read_middleware_config_file(args.m)
    context.variables.load(args.c)
    context.start(args.p)

    ml = MainLoop(context)
    context.ml = ml

    if username is not None:
        context.login(username, args.p)
    elif context.parsed_uri.netloc in ('127.0.0.1', 'localhost') \
            or context.parsed_uri.scheme == 'unix':
        context.login(getpass.getuser(), '')

    if args.D:
        for i in args.D:
            name, value = i.split('=')
            context.variables.set(name, value)

    if args.e:
        ml.process(args.e)
        return

    if args.f:
        try:
            f = sys.stdin if args.f == '-' else open(args.f)
            for line in f:
                ml.process(line.strip())

            f.close()
        except EnvironmentError as e:
            sys.stderr.write('Cannot open input file: {0}'.format(str(e)))
            sys.exit(1)

        return

    ml.repl()


if __name__ == '__main__':
    main()
