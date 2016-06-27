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

import os
import importlib
import sys
import gettext
import enum
import time
import contextlib
import io
import six
import pydoc
import collections

from freenas.utils.permissions import get_unix_permissions, string_to_int
from freenas.cli import config
from freenas.utils import first_or_default
from threading import Lock, Thread


output_lock = Lock()
t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


class ValueType(enum.Enum):
    STRING = 1
    STRING_HEAD = 2
    NUMBER = 3
    HEXNUMBER = 4
    OCTNUMBER = 5
    BOOLEAN = 6
    SIZE = 7
    TIME = 8
    SET = 9
    DICT = 10
    PERMISSIONS = 11


class Object(list):
    class Item(object):
        def __init__(self, descr, name, value, vt=ValueType.STRING, editable=None):
            self.descr = descr
            self.name = name
            self.value = value
            self.vt = vt
            self.editable = editable

    def append(self, p_object):
        if not isinstance(p_object, self.Item):
            raise ValueError('Can only add Object.Item instances')

        super(Object, self).append(p_object)

    def __getitem__(self, item):
        i = first_or_default(lambda x: x.name == item, self)
        if i:
            return i.value

        raise KeyError(item)

    def __setitem__(self, key, value):
        if not isinstance(value, self.Item):
            raise ValueError('Can only add Object.Item instances')

        super(Object, self).__setitem__(key, value)

    def __init__(self, *args):
        for i in args:
            self.append(i)


class Table(object):
    class Column(object):
        def __init__(self, label, accessor, vt=ValueType.STRING):
            self.label = label
            self.accessor = accessor
            self.vt = vt

    def __init__(self, data, columns):
        self.data = data
        self.columns = columns

    def __len__(self):
        return len(self.data)

    def __getitem__(self, item):
        return self.data[item]

    def pop(self, pop_index):
        return self.data.pop(pop_index)


class Sequence(list):
    def __init__(self, *items):
        super(Sequence, self).__init__(items)

    def unwind(self, force=False):
        return self if len(self) > 1 or force else self[0]

    def append_flat(self, item):
        if isinstance(item, Sequence):
            self.extend(item)
            return

        self.append(item)


class ProgressBar(object):
    def __init__(self):
        self.message = None
        self.percentage = 0
        self.draw_t = Thread(target=self.draw)
        self.finished = False
        sys.stdout.write('\n')
        self.draw_t.daemon = True
        self.draw_t.start()

    def draw(self):
        progress_width = 40
        none_fill = ''.join('#' if i < 8 else '_' for i in range(progress_width))

        def get_none_fill(f):
            asc = True
            while True:
                yield f
                if asc:
                    f = f[-1] + f[:-1]
                    if f[-1] == '#':
                        asc = False
                else:
                    f = f[1:] + f[0]
                    if f[0] == '#':
                        asc = True

        generator = get_none_fill(none_fill)
        while not self.finished:
            if self.percentage is None:
                none_fill = next(generator)
                fill = none_fill
            else:
                filled_width = int(self.percentage * progress_width)
                fill = '#' * filled_width + '_' * (progress_width - filled_width)

            sys.stdout.write('\033[2K\033[A\033[2K\r')
            sys.stdout.write('Status: {}\n'.format(self.message))
            sys.stdout.write('Total task progress: [{}] '.format(fill) +
                             ('' if self.percentage is None else '{:.2%}'.format(self.percentage)))

            sys.stdout.flush()
            time.sleep(0.5)

    def update(self, percentage=None, message=None):
        self.percentage = None if percentage is None else float(percentage / 100.0)

        if message:
            self.message = message

    def finish(self):
        self.percentage = 1

    def end(self):
        self.finished = True
        self.draw_t.join()
        sys.stdout.write('\n')


def get_terminal_size(fd=1):
    """
    Returns height and width of current terminal. First tries to get
    size via termios.TIOCGWINSZ, then from environment. Defaults to 25
    lines x 80 columns if both methods fail.

    :param fd: file descriptor (default: 1=stdout)
    """
    try:
        import fcntl, termios, struct
        hw = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
    except:
        try:
            hw = (os.environ['LINES'], os.environ['COLUMNS'])
        except:
            hw = (25, 80)

    if hw[0] == 0 or hw[1] == 0:
        hw = (25, 80)

    return hw


def resolve_cell(row, spec):
    if type(spec) == str:
        return row.get(spec)

    if isinstance(spec, collections.Callable):
        return spec(row)

    return '<unknown>'


def read_value(value, tv=ValueType.STRING):
    if value is None:
        if tv == ValueType.SET:
            return []

        if tv == ValueType.DICT:
            return {}

        return value

    if tv in (ValueType.STRING, ValueType.STRING_HEAD):
        return str(value)

    if tv in (ValueType.NUMBER, ValueType.SIZE):
        return int(value)

    if tv == ValueType.BOOLEAN:
        if type(value) is bool:
            return value

        if str(value).lower() in ('true', 'yes', 'on', '1'):
            return True

        if str(value).lower() in ('false', 'no', 'off', '0'):
            return False

    if tv == ValueType.SET:
        if type(value) is list:
            return value
        else:
            return [value]

    if tv == ValueType.DICT:
        if type(value) is dict:
            return value

    if tv == ValueType.OCTNUMBER:
        return int(value)

    if tv == ValueType.PERMISSIONS:
        if isinstance(value, str):
            value = string_to_int(value)
        return get_unix_permissions(value)

    raise ValueError(_("Invalid value '{0}', expected {1} value".format(value, str(tv).split('ValueType.')[-1].lower())))


def format_value(value, vt=ValueType.STRING, fmt=None):
    fmt = fmt or config.instance.variables.get('output_format')
    return get_formatter(fmt).format_value(value, vt)


def output_value(value, fmt=None, **kwargs):
    fmt = fmt or config.instance.variables.get('output_format')
    return get_formatter(fmt).output_value(value, **kwargs)


def output_list(data, label=_("Items"), fmt=None, **kwargs):
    fmt = fmt or config.instance.variables.get('output_format')
    return get_formatter(fmt).output_list(data, label, **kwargs)


def output_dict(data, key_label=_("Key"), value_label=_("Value"), fmt=None, **kwargs):
    fmt = fmt or config.instance.variables.get('output_format')
    return get_formatter(fmt).output_dict(data, key_label, value_label)


def output_table(table, fmt=None, **kwargs):
    fmt = fmt or config.instance.variables.get('output_format')
    return get_formatter(fmt).output_table(table, **kwargs)


def output_object(item, **kwargs):
    fmt = kwargs.pop('fmt', None)
    fmt = fmt or config.instance.variables.get('output_format')
    return get_formatter(fmt).output_object(item, **kwargs)


def output_tree(tree, children, label, fmt=None, **kwargs):
    fmt = fmt or config.instance.variables.get('output_format')
    return get_formatter(fmt).output_tree(tree, children, label, **kwargs)


def get_formatter(name):
    module = importlib.import_module('freenas.cli.output.' + name)
    return module._formatter()


def output_msg(message, fmt=None, **kwargs):
    fmt = fmt or config.instance.variables.get('output_format')
    return get_formatter(fmt).output_msg(message, **kwargs)


def output_is_ascii():
    return config.instance.variables.get('output_format') == 'ascii'


# The following solution to implement `LESS(1)` style output is a combination
# of snippets taken from the following stackoverflow answers:
#   1. http://stackoverflow.com/questions/14197009/how-can-i-redirect-print-output-of-a-function-in-python#answer-14197079
#   2. http://stackoverflow.com/questions/6728661/paging-output-from-python#answer-18234081
@contextlib.contextmanager
def stdout_redirect(where):
    sys.stdout = where
    try:
        yield where
    finally:
        sys.stdout = sys.__stdout__


class StringIO(io.StringIO):
    """
    Decode inputs so we can make it work in py2 and py3.
    In py2 the print function automatically encode inputs.
    """
    def write(self, value, *args, **kwargs):
        if six.PY2 and isinstance(value, str):
            value = value.decode('utf8')
        return super(StringIO, self).write(value, *args, **kwargs)


def output_less(output_call_list):
    # First check if its either a list or a func (if not then raise TypeError)
    if hasattr(output_call_list, '__call__'):
        # It is a single func so just wrap it in a list and the below code
        # will DTRT
        output_call_list = [output_call_list]
    elif type(output_call_list) is list:
        for x in output_call_list:
            if not hasattr(x, '__call__'):
                raise TypeError('One of the items provided in the ' +
                                'output_call_list was not a function')
    else:
        raise TypeError('Input to `output_less` must either be a function or' +
                        ' a list of functions. Instead the following type ' +
                        'was received: {0}'.format(type(output_call_list)))

    with stdout_redirect(StringIO()) as new_stdout:
        for output_func_call in output_call_list:
            output_func_call(new_stdout)

    new_stdout.seek(0)
    pydoc.pager(new_stdout.read())


def format_output(object, **kwargs):
    if isinstance(object, Object):
        output_object(object, **kwargs)

    elif isinstance(object, Table):
        output_table(object, **kwargs)

    elif isinstance(object, dict):
        output_dict(object, **kwargs)

    elif isinstance(object, Sequence):
        for i in object:
            format_output(i, **kwargs)
    elif isinstance(object, list):
        output_list(object, **kwargs)
    else:
        output_msg(object, **kwargs)


def refresh_prompt():
    if not config.instance.variables.get('tasks_blocking'):
        config.instance.ml.blank_readline()
        config.instance.ml.restore_readline()


def output_msg_locked(msg):
    output_lock.acquire()
    config.instance.ml.blank_readline()
    output_msg(msg)
    sys.stdout.flush()
    config.instance.ml.restore_readline()
    output_lock.release()


def get_humanized_size(value):
    value = int(value)
    suffixes = [
        'iB',
        'KiB',
        'MiB',
        'GiB'
    ]

    for suffix in suffixes:
        next_step = value / 1024
        if not int(next_step):
            return str(round(value, 2)) + ' ' + suffix
        value = next_step

    return str(round(value, 2)) + ' ' + 'TiB'
