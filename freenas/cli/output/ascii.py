#+
# Copyright 2015 iXsystems, Inc.
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

import io
import six
import sys
import datetime
import dateutil.tz
import time
import gettext
import natural.date
from dateutil.parser import parse
from texttable import Texttable
from columnize import columnize
from freenas.cli import config
from freenas.cli.output import ValueType, get_terminal_size, resolve_cell, get_humanized_size, Table


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


def format_literal(value, **kwargs):
    if isinstance(value, six.string_types):
        if kwargs.get('quoted'):
            return '"{0}"'.format(value)
        else:
            return value

    if isinstance(value, bool):
        return 'true' if value else 'false'

    if isinstance(value, six.integer_types):
        return str(value)

    if isinstance(value, io.TextIOWrapper):
        return '<open file "{0}">'.format(value.name)

    if isinstance(value, list):
        return '[' + ', '.join(format_literal(i, quoted=True) for i in value) + ']'

    if isinstance(value, dict):
        return '{' + ', '.join('{0}: {1}'.format(
            format_literal(k, quoted=True),
            format_literal(v, quoted=True)
        ) for k, v in value.items()) + '}'

    if value is None:
        return 'none'

    return str(value)


class AsciiOutputFormatter(object):
    @staticmethod
    def format_value(value, vt):
        if vt == ValueType.BOOLEAN:
            return _("yes") if value else _("no")

        if value is None:
            return _("none")

        if vt == ValueType.SET:
            value = list(value)
            if len(value) == 0:
                return _("empty")

            return '\n'.join(value)

        if vt == ValueType.DICT:
            if not bool(value):
                return _("empty")

            return AsciiOutputFormatter.format_dict_value(value)

        if vt == ValueType.STRING:
            return value

        if vt == ValueType.NUMBER:
            return str(value)

        if vt == ValueType.HEXNUMBER:
            return hex(value)

        if vt == ValueType.SIZE:
            return get_humanized_size(value)

        if vt == ValueType.TIME:
            fmt = config.instance.variables.get('datetime_format')
            localtz = dateutil.tz.tzlocal()
            localoffset = localtz.utcoffset(datetime.datetime.now(localtz))
            offset = localoffset.total_seconds()

            if isinstance(value, str):
                offset = localoffset
                value = parse(value)
            if fmt == 'natural':
                return natural.date.duration(value + datetime.timedelta(seconds=offset))

            return time.strftime(fmt, time.localtime(value))

    def format_dict_value(value):
        output = ""
        for k,v in value.items():
            if isinstance(v, dict):
                output+=str(k) + '={' + format_dict_value(v) + '}'
            else:
                output+="{0}={1} ".format(k, format_literal(v))

        return output

    @staticmethod
    def output_list(data, label, vt=ValueType.STRING):
        sys.stdout.write(columnize(data))
        sys.stdout.flush()

    @staticmethod
    def output_dict(data, key_label, value_label, value_vt=ValueType.STRING):
        sys.stdout.write(columnize(['{0}={1}'.format(row[0], AsciiOutputFormatter.format_value(row[1], value_vt)) for row in list(data.items())]))
        sys.stdout.flush()

    @staticmethod
    def output_table(tab, file=sys.stdout, **kwargs):
        hidden_indexes = []
        for i in range(0, len(tab.columns)):
            if tab.columns[i].label is None:
                hidden_indexes.append(i)
        hidden_indexes.reverse()
        for i in hidden_indexes:
            del tab.columns[i]

        table=AsciiOutputFormatter.format_table(tab)
        six.print_(table.draw(), file=file, end=('\n' if kwargs.get('newline', True) else ' '))

    @staticmethod
    def output_table_list(tables):
        terminal_size = get_terminal_size()[1]
        widths = []
        for tab in tables:
            for i in range(0, len(tab.columns)):
                current_width = len(tab.columns[i].label)
                if len(widths) < i + 1:
                    widths.insert(i, current_width)
                elif widths[i] < current_width:
                    widths[i] = current_width
                for row in tab.data:
                    current_width = len(resolve_cell(row, tab.columns[i].accessor))
                    if current_width > widths[i]:
                        widths[i] = current_width

        if sum(widths) != terminal_size:
            widths[-1] = terminal_size - sum(widths[:-1]) - len(widths) * 3

        for tab in tables:
            table = Texttable(max_width=terminal_size)
            table.set_cols_width(widths)
            table.set_deco(0)
            table.header([i.label for i in tab.columns])
            table.add_rows([[AsciiOutputFormatter.format_value(resolve_cell(row, i.accessor), i.vt) for i in tab.columns] for row in tab.data], False)
            six.print_(table.draw() + "\n")

    @staticmethod
    def output_object(obj, file=sys.stdout, **kwargs):

        values = []
        editable_column = False
        for item in obj:
            value ={'name': item.name,
                    'descr': item.descr,
                    'value': AsciiOutputFormatter.format_value(item.value, item.vt)}

            if item.editable is not None:
                value['editable'] = AsciiOutputFormatter.format_value(item.editable, ValueType.BOOLEAN)
                editable_column = True

            values.append(value)

        cols = []
        cols.append(Table.Column("Property", 'name'))
        cols.append(Table.Column("Description", 'descr'))
        cols.append(Table.Column("Value", 'value'))
        if editable_column: 
            cols.append(Table.Column("Editable", 'editable'))

        table = AsciiOutputFormatter.format_table(Table(values, cols))
        six.print_(table.draw(), file=file, end=('\n' if kwargs.get('newline', True) else ' '))

    @staticmethod
    def output_tree(tree, children, label, label_vt=ValueType.STRING, file=sys.stdout):
        def branch(obj, indent):
            for idx, i in enumerate(obj):
                subtree = resolve_cell(i, children)
                char = '+' if subtree else ('`' if idx == len(obj) - 1 else '|')
                six.print_('{0} {1}-- {2}'.format('    ' * indent, char, resolve_cell(i, label)), file=file)
                if subtree:
                    branch(subtree, indent + 1)

        branch(tree, 0)

    @staticmethod
    def output_msg(message, **kwargs):
        six.print_(
            format_literal(message, **kwargs),
            end=('\n' if kwargs.get('newline', True) else ' '),
            file=kwargs.pop('file', sys.stdout)
        )

    def format_table(tab):
        max_width = get_terminal_size()[1]
        table = Texttable(max_width=max_width)
        table.set_deco(0)
        table.header([i.label for i in tab.columns])
        widths = []
        ideal_widths = []
        number_columns = len(tab.columns)
        remaining_space = max_width
        # set maximum column width based on the amount of terminal space minus the 3 pixel borders
        max_col_width = (remaining_space - number_columns * 3) / number_columns
        for i in range(0, number_columns):
            current_width = len(tab.columns[i].label)
            tab_cols_acc = tab.columns[i].accessor
            if len(tab.data) > 0:
                max_row_width = max(
                        [len(str(resolve_cell(row, tab_cols_acc))) for row in tab.data ]
                        )
                ideal_widths.insert(i, max_row_width)
                current_width = max_row_width if max_row_width > current_width else current_width
            if current_width < max_col_width:
                widths.insert(i, current_width)
                # reclaim space not used
                remaining_columns = number_columns - i - 1
                remaining_space = remaining_space - current_width - 3
                if remaining_columns != 0:
                    max_col_width = (remaining_space - remaining_columns * 3)/ remaining_columns
            else:
                widths.insert(i, max_col_width)
                remaining_space = remaining_space - max_col_width - 3
        if remaining_space > 0 and len(ideal_widths) > 0:
            for i in range(0, number_columns):
                if remaining_space == 0:
                    break
                if ideal_widths[i] > widths[i]:
                    needed_space = ideal_widths[i] - widths[i]
                    if needed_space <= remaining_space:
                        widths[i] = ideal_widths[i]
                        remaining_space = remaining_space - needed_space
                    elif needed_space > remaining_space:
                        widths[i] = widths[i] + remaining_space
                        remaining_space = 0
        table.set_cols_width(widths)
        table.set_cols_dtype(['t'] * len(tab.columns))
        table.add_rows([[AsciiOutputFormatter.format_value(resolve_cell(row, i.accessor), i.vt) for i in tab.columns] for row in tab.data], False)
        return table


def _formatter():
    return AsciiOutputFormatter
