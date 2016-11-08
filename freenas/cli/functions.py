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
import termios
import copy
import operator
import time
import random
import json
import re
from threading import Timer
from builtins import input
from freenas.cli.namespace import Command
from freenas.cli.output import format_output, output_msg, Table, Sequence
from freenas.cli.parser import Quote, parse, unparse, read_ast as parser_read_ast, FunctionDefinition
from freenas.cli.utils import pass_env
from freenas.cli import config
from freenas.utils import decode_escapes


operators = {
    '+': operator.add,
    '-': operator.sub,
    '*': operator.mul,
    '/': operator.floordiv,
    '==': operator.eq,
    '!=': operator.ne,
    '>': operator.gt,
    '<': operator.lt,
    '>=': operator.ge,
    '<=': operator.le,
    '%': operator.mod,
    'and': operator.and_,
    'or': operator.or_,
    'not': operator.not_
}


def array_resize(array, length):
    if length > len(array):
        array.extend([None] * (length - len(array)))
    else:
        del array[:len(array) - length]


def print_(*items):
    for i in items:
        format_output(i)


def printf(fmt, *args):
    print(decode_escapes(fmt) % args, end='', flush=True)


def sprintf(fmt, *args):
    return decode_escapes(fmt) % args


def map_(data, fn):
    if isinstance(data, dict):
        array = [{"key": k, "value": v} for k, v in data.items()]
    else:
        array = data
    return list(map(fn, array))


def mapf(array, fmt):
    return list(map(lambda s: fmt % s, array))


def apply(fn, *args):
    return fn(*args)


def strjoin(array, sep=' '):
    return sep.join(array)


def sum_(array):
    return sum(array)


def avg_(array):
    return sum(array) / len(array)


def range_(*args):
    return list(range(*args))


def typeof(val):
    return type(val).__name__


def readline(prompt):
    return input(prompt)


def rand(a, b):
    return random.randint(a, b)


def setinterval(interval, fn):
    Timer(interval / 1000, fn).start()


def readkey():
    fd = sys.stdin.fileno()
    oldterm = termios.tcgetattr(fd)
    newattr = termios.tcgetattr(fd)
    newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSANOW, newattr)

    try:
        c = sys.stdin.read(1)
        if not c:
            return None

        return c
    except IOError:
        raise
    except KeyboardInterrupt:
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)


def unparse_(fn):
    output_msg(unparse(FunctionDefinition(
        fn.name,
        fn.param_names,
        fn.exp
    )))


def rpc(name, *args):
    return Sequence(*config.instance.call_sync(name, *args))


def call_task(name, *args):
    return config.instance.call_task_sync(name, *args)


def cwd():
    return config.instance.ml.path_string


def register_command(namespace, name, fn):
    class UserCommand(Command):
        def run(self, context, args, kwargs, opargs):
            return fn(args, kwargs, opargs)

    config.instance.user_commands.append((namespace, name, UserCommand()))


def unregister_command(namespace, name):
    pass


def fopen(filename, mode):
    return open(filename, mode)


def fclose(fhandle):
    fhandle.close()


def freadline(fhandle):
    return fhandle.readline()


def fprintf(fhandle, fmt, *args):
    fhandle.write(decode_escapes(fmt) % args)
    fhandle.flush()


def table(data, columns):
    return Table(data, [Table.Column(l, a) for l, a in columns])


def eval_(ast):
    if isinstance(ast, str):
        ast = parse(ast, '<eval>')

    if isinstance(ast, Quote):
        ast = ast.body

    return Sequence(*config.instance.eval(ast))


# Reads a json object from a file or a str and returns a parsed dict of it
def json_load(data):
    if hasattr(data, 'read'):
        return json.load(data)
    return json.loads(data)


# Accepts obj and serializes it to json, which it then returns.
# If the optional file handler is provided, it writes the serialized
# json to that file and returns nothing
def json_dump(obj, file=None):
    if file is not None:
        json.dump(obj, file)
    else:
        return json.dumps(obj)


def re_match(regex, text):
    m = re.match(regex, text)
    if m:
        return list(m.groups())

    return None


def re_search(regex, text):
    m = re.search(regex, text)
    if m:
        return list(m.groups())

    return None


def waitfor(promise):
    return promise.wait()


def dump_ast(ast):
    return ast.to_json()


def read_ast(value):
    return parser_read_ast(value)


@pass_env
def defined(env, name):
    return name in env


@pass_env
def get_by_name(env, name):
    return env.find(name)


@pass_env
def set_by_name(env, name, value):
    env[name] = value


functions = {
    'print': print_,
    'printf': printf,
    'sprintf': sprintf,
    'map': map_,
    'mapf': mapf,
    'apply': apply,
    'sum': sum_,
    'avg': avg_,
    'contains': operator.contains,
    'readkey': readkey,
    'readline': readline,
    'unparse': unparse_,
    'sleep': time.sleep,
    'rpc': rpc,
    'call_task': call_task,
    'cwd': cwd,
    'register_command': register_command,
    'unregister_command': unregister_command,
    'range': range_,
    'str': str,
    'int': int,
    'length': len,
    'typeof': typeof,
    'rand': rand,
    'setinterval': setinterval,
    'append': lambda a, i: a.append(i),
    'remove': lambda a, i: a.remove(i),
    'resize': array_resize,
    'shift': lambda a: a.pop(0),
    'copy': copy.deepcopy,
    'fopen': fopen,
    'freadline': freadline,
    'fprintf': fprintf,
    'fclose': fclose,
    'table': table,
    'json_load': json_load,
    'json_dump': json_dump,
    'eval': eval_,
    'join': strjoin,
    'enumerate': lambda a: list(enumerate(a)),
    're_match': re_match,
    're_search': re_search,
    'waitfor': waitfor,
    'dump_ast': dump_ast,
    'read_ast': read_ast,
    'defined': defined,
    'get_by_name': get_by_name,
    'set_by_name': set_by_name
}
