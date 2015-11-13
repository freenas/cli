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


import sys
import time
import config
import icu
import natural.date
import natural.size
from texttable import Texttable
from columnize import columnize
from termcolor import cprint
from output import ValueType, get_terminal_size, resolve_cell


t = icu.Transliterator.createInstance("Any-Accents", icu.UTransDirection.FORWARD)
_ = t.transliterate


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

        if vt == ValueType.STRING:
            return value

        if vt == ValueType.NUMBER:
            return str(value)

        if vt == ValueType.HEXNUMBER:
            return hex(value)

        if vt == ValueType.SIZE:
            return natural.size.binarysize(value)

        if vt == ValueType.TIME:
            fmt = config.instance.variables.get('datetime_format')
            if fmt == 'natural':
                return natural.date.duration(value)

            return time.strftime(fmt, time.localtime(value))

    @staticmethod
    def output_list(data, label, vt=ValueType.STRING):
        sys.stdout.write(columnize(data))
        sys.stdout.flush()

    @staticmethod
    def output_dict(data, key_label, value_label, value_vt=ValueType.STRING):
        sys.stdout.write(columnize(['{0}={1}'.format(row[0], AsciiOutputFormatter.format_value(row[1], value_vt)) for row in list(data.items())]))
        sys.stdout.flush()

    @staticmethod
    def output_table(tab):
        max_width = get_terminal_size()[1]
        table = Texttable(max_width=max_width)
        table.set_deco(0)
        table.header([i.label for i in tab.columns])
        widths = []
        number_columns = len(tab.columns)
        remaining_space = max_width
        # set maximum column width based on the amount of terminal space minus the 3 pixel borders
        max_col_width = (remaining_space - number_columns * 3) / number_columns
        for i in range(0, number_columns):
            current_width = len(tab.columns[i].label)
            tab_cols_acc = tab.columns[i].accessor
            max_row_width = max(
                    [len(str(resolve_cell(row, tab_cols_acc))) for row in tab.data ]
                    )
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
        table.set_cols_width(widths)

        table.add_rows([[AsciiOutputFormatter.format_value(resolve_cell(row, i.accessor), i.vt) for i in tab.columns] for row in tab.data], False)
        print(table.draw())

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
            print(table.draw() + "\n")

    @staticmethod
    def output_object(obj):
        table = Texttable(max_width=get_terminal_size()[1])
        table.set_deco(0)
        for item in obj:
            table.add_row(['{0} ({1})'.format(item.descr, item.name), AsciiOutputFormatter.format_value(item.value, item.vt)])

        print(table.draw())

    @staticmethod
    def output_tree(tree, children, label, label_vt=ValueType.STRING):
        def branch(obj, indent):
            for idx, i in enumerate(obj):
                subtree = resolve_cell(i, children)
                char = '+' if subtree else ('`' if idx == len(obj) - 1 else '|')
                print('{0} {1}-- {2}'.format('    ' * indent, char, resolve_cell(i, label)))
                if subtree:
                    branch(subtree, indent + 1)

        branch(tree, 0)

    @staticmethod
    def output_msg(message, **kwargs):
        cprint(str(message), attrs=kwargs.pop('attrs', None))


def _formatter():
    return AsciiOutputFormatter
