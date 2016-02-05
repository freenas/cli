#
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
import operator
from builtins import input
from freenas.cli.namespace import Command
from freenas.cli.output import format_output, output_msg, Table
from freenas.cli.parser import unparse, FunctionDefinition
from freenas.cli import config

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
        format_output(i, newline=False)

    output_msg('')


def printf(fmt, *args):
    output_msg(fmt % args)


def sprintf(fmt, *args):
    return fmt % args


def map_(fn, array):
    return list(map(fn, array))


def mapf(fmt, array):
    return list(map(lambda s: fmt % s, array))


def apply(fn, *args):
    return fn(*args)


def sum_(array):
    return sum(array)


def readline(prompt):
    return input(prompt)


def unparse_(fn):
    output_msg(unparse(FunctionDefinition(
        fn.name,
        fn.param_names,
        fn.exp
    )))


def rpc(name, *args):
    return config.instance.call_sync(name, *args)


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
    fhandle.write(fmt % args)
    fhandle.flush()


def table(data, columns):
    return Table(data, [Table.Column(l, a) for l, a in columns])


# Add functions to help script things

def factorial(n):
    "Computes the factorial of positive integers and zero"
    if n <= 1:
        return 1
    return n*factorial(n-1)

functions = {
    'print': print_,
    'printf': printf,
    'sprintf': sprintf,
    'map': map_,
    'mapf': mapf,
    'apply': apply,
    'sum': sum_,
    'readline': readline,
    'unparse': unparse_,
    'rpc': rpc,
    'call_task': call_task,
    'cwd': cwd,
    'register_command': register_command,
    'unregister_command': unregister_command,
    'range': range,
    'str': str,
    'length': len,
    'append': lambda a, i: a.append(i),
    'remove': lambda a, i: a.remove(i),
    'resize': array_resize,
    'copy': copy.deepcopy,
    'fopen': fopen,
    'freadline': freadline,
    'fprintf': fprintf,
    'fclose': fclose,
    'table': table,
    'factorial': factorial
}
