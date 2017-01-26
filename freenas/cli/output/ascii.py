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
import time
import gettext
import natural.date
import math
from dateutil.parser import parse
from texttable import Texttable
from freenas.cli import config
from freenas.cli.output import ValueType, get_terminal_size, resolve_cell, get_humanized_size, Table
from freenas.cli.utils import get_localtime_offset
from freenas.utils.permissions import int_to_string


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


def _is_ascii(s):
    return all(ord(char) < 128 for char in s)


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
        if kwargs.get('quoted'):
            return '[' + ', '.join(format_literal(i, quoted=True) for i in value) + ']'

        return ','.join(format_literal(i, quoted=True) for i in value)

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
        if value is None:
            return _("none")

        if vt == ValueType.BOOLEAN:
            return _("yes") if value else _("no")

        if vt == ValueType.SET:
            value = set(value)
            if len(value) == 0:
                return _("<empty>")

            return ','.join(format_literal(i) for i in value)

        if vt == ValueType.ARRAY:
            value = list(value)
            if len(value) == 0:
                return _("<empty>")

            return ','.join(format_literal(i) for i in value)

        if vt == ValueType.DICT:
            if not bool(value):
                return _("<empty>")

            return value

        if vt == ValueType.STRING:
            return format_literal(value)

        if vt == ValueType.TEXT_FILE:
            return format_literal(value[:10] + '(...)')

        if vt == ValueType.NUMBER:
            return str(value)

        if vt == ValueType.HEXNUMBER:
            return hex(value)

        if vt == ValueType.OCTNUMBER:
            return oct(value)

        if vt == ValueType.PERMISSIONS:
            return '{0} ({1})'.format(oct(value['value']).zfill(3), int_to_string(value['value']))

        if vt == ValueType.SIZE:
            return get_humanized_size(value)

        if vt == ValueType.TIME:
            fmt = config.instance.variables.get('datetime_format')

            delta = datetime.timedelta(seconds=get_localtime_offset())
            if isinstance(value, str):
                value = parse(value)
            if isinstance(value, float):
                delta = delta.total_seconds()
            if fmt == 'natural':
                return natural.date.duration(value + delta)

            return time.strftime(fmt, time.localtime(value))

        if vt == ValueType.DATE:
            return '{:%Y-%m-%d %H:%M:%S}'.format(value)

        if vt == ValueType.PASSWORD:
            return "*****"

    @staticmethod
    def columnize(data):
        columnizer = Columnizer()
        return columnizer.columnize(data)

    @staticmethod
    def output_list(data, label, vt=ValueType.STRING, **kwargs):
        ret = data
        for d in data:
            if isinstance(d, Table):
                ret = [str(type(dd)) for dd in data]
        sys.stdout.write(AsciiOutputFormatter.columnize([str(r) for r in ret]))
        sys.stdout.flush()

    @staticmethod
    def output_dict(data, key_label, value_label, value_vt=ValueType.STRING):
        sys.stdout.write(AsciiOutputFormatter.columnize(
            ['{0}={1}'.format(row[0], AsciiOutputFormatter.format_value(row[1], value_vt)) for row in list(data.items())]
        ))
        sys.stdout.flush()

    @staticmethod
    def output_table(tab, file=sys.stdout, **kwargs):
        AsciiOutputFormatter._print_stream_table(tab, file, end=('\n' if kwargs.get('newline', True) else ' '))

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
        try:
            six.print_(table.draw(), file=file, end=('\n' if kwargs.get('newline', True) else ' '))
        except UnicodeEncodeError:
            table = AsciiOutputFormatter.format_table(Table(values, cols), conv2ascii=True)
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

    @staticmethod
    def _print_stream_table(tab, file, end):
        def _print_header(columns, file, end, printer=None):
            printer.print_header(columns, file, end) if printer else six.print_([col.label for col in columns], file=file, end=end)

        def _print_rows(rows, columns, file, end, printer=None):
            for row in rows:
                printer.print_row(row, file, end) if printer else six.print_([row[col.accessor] for col in columns], file=file, end=end)

        printer = AsciiStreamTablePrinter()
        _print_header(tab.columns, file, end, printer=printer)
        _print_rows(tab.data, tab.columns, file, end, printer=printer)

    def format_table(tab, conv2ascii=False):
        def _try_conv2ascii(s):
            return ascii(s) if not _is_ascii(s) and isinstance(s, str) else s

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
        if conv2ascii:
            table.add_rows([[AsciiOutputFormatter.format_value(
                _try_conv2ascii(resolve_cell(row, i.accessor)), i.vt) for i in tab.columns] for row in tab.data], False)
        else:
            table.add_rows([[AsciiOutputFormatter.format_value(
                resolve_cell(row, i.accessor), i.vt) for i in tab.columns] for row in tab.data], False)
        return table


def _formatter():
    return AsciiOutputFormatter


class AsciiStreamTablePrinter(object):
    def __init__(self):
        self.display_size = get_terminal_size()[1]
        self.usable_display_width = self.display_size
        self._cleanup_all()
        self.visible_separators = False

    def _cleanup_all(self):
        self.cols_widths = []
        self._cleanup_lines()

    def _cleanup_lines(self):
        self.ordered_line_elements = []
        self.ordered_lines_elements = []
        self.ordered_lines = []

    def print_header(self, columns, file, end):
        self._compute_cols_widths(columns)
        self._load_accessors(columns)
        self._load_value_types(columns)
        self._load_header_elements(columns)
        self._trim_elements()
        self._render_lines()
        self._add_vertical_separator_line()
        self._print_lines(file, end)

    def print_row(self, row, file, end):
        self._load_row_elements(row)
        self._trim_elements()
        self._render_lines()
        try:
            self._print_lines(file, end)
        except UnicodeEncodeError:
            self._cleanup_lines()
            self._load_row_elements(row, conv2ascii=True)
            self._trim_elements()
            self._render_lines()
            self._print_lines(file, end)

    def _compute_cols_widths(self, columns):
        def extend_cols_widths(additional_space):
            for i, col in enumerate(self.cols_widths):
                if not additional_space:
                    return
                self.cols_widths[i] += 1
                additional_space -= 1

        self.borders_space = len(columns) + 1

        default_col_width_percentage = 100
        reserved_width_percentage = 0
        reserved_cols_count = 0
        for col in columns:
            if col.width:
                reserved_width_percentage += col.width
                reserved_cols_count += 1
        if len(columns) != reserved_cols_count:
            default_col_width_percentage = int((100 - reserved_width_percentage) / (len(columns) - reserved_cols_count))
        for col in columns:
            if not col.width:
                col.width = default_col_width_percentage
        cols_widths_fracts_ints = [math.modf((self.display_size-self.borders_space)*(col.width/100))
                                  for col in columns]
        space_from_fracts = int(sum([col[0] for col in cols_widths_fracts_ints]))
        self.cols_widths = [int(col[1]) for col in cols_widths_fracts_ints]
        extend_cols_widths(space_from_fracts)
        self.usable_display_width = sum(self.cols_widths) + self.borders_space

    def _load_accessors(self, columns):
        self.accessors = [col.accessor for col in columns]

    def _load_value_types(self, columns):
        self.value_types = [col.vt for col in columns]

    def _load_header_elements(self, columns):
        self.ordered_line_elements = [col.label for col in columns]
        self.ordered_lines_elements = [self.ordered_line_elements]

    def _load_row_elements(self, row, conv2ascii=False):

        def convert_nested_dict_to_string(dict):
            return ", ".join([":".join([k, v]) for k, v in dict.items()])

        for i, acc in enumerate(self.accessors):
            if callable(acc):
                elem = acc(row)
            else:
                elem = row[acc]

            if isinstance(elem, dict):
                elem = convert_nested_dict_to_string(elem)

            if conv2ascii and isinstance(elem, str):
                elem = ascii(elem) if not _is_ascii(elem) else elem

            self.ordered_line_elements.append(AsciiOutputFormatter.format_value(elem, self.value_types[i]))

        self.ordered_lines_elements = [self.ordered_line_elements]

    def _trim_elements(self):
        def split_line_element(line_index, elem_index, element):
            def has_2ormore_words(element):
                return len(element.split()) > 1

            def try_pretty_split(element, index):
                return len(element.split()[0]) < self.cols_widths[index]

            def do_pretty_split(curr_line, next_line, elem_index):
                all_words = curr_line[elem_index].split()
                words_to_curr_line = all_words.pop(0)
                words_to_next_line = ""
                for i, word in enumerate(all_words):
                    if len(words_to_curr_line + " " + word) < self.cols_widths[elem_index]:
                        words_to_curr_line += " " + word
                    else:
                        words_to_next_line += " ".join(all_words[i:])
                        break

                curr_line[elem_index] = words_to_curr_line
                next_line[elem_index] = words_to_next_line
                return curr_line, next_line

            def do_ugly_split(curr_line, next_line, elem_index, element):
                splitted = [element[0: self.cols_widths[elem_index]], element[self.cols_widths[elem_index]:]]
                curr_line[elem_index] = splitted[0]
                next_line[elem_index] = splitted[1]
                return curr_line, next_line

            curr_line = self.ordered_lines_elements[line_index]
            try:
                next_line = self.ordered_lines_elements[line_index+1]
            except IndexError:
                next_line = ["" for _ in range(0, len(curr_line))]
            if has_2ormore_words(element) and try_pretty_split(element, elem_index):
                return do_pretty_split(curr_line, next_line, elem_index)
            else:
                return do_ugly_split(curr_line, next_line, elem_index, element)

        for line_index, ordered_line_elements in enumerate(self.ordered_lines_elements):
            for elem_index, elem in enumerate(ordered_line_elements):
                if len(elem) >= self.cols_widths[elem_index]:
                    curr_line, next_line = split_line_element(line_index, elem_index, elem)
                    self.ordered_lines_elements[line_index] = curr_line
                    try:
                        self.ordered_lines_elements[line_index+1] = next_line
                    except IndexError:
                        self.ordered_lines_elements.append(next_line)

    def _render_lines(self):
        def render_line(ordered_line_elements):
            ordered_line_elements_with_spaces = [
                surround_with_spaces(e, i, left_aligned=True) for i, e in enumerate(ordered_line_elements)
                ]
            line = " " if not self.visible_separators else "|"
            for e in ordered_line_elements_with_spaces:
                line += e+" " if not self.visible_separators else e+"|"
            self.ordered_lines.append(line)

        def surround_with_spaces(element, index, left_aligned=False, right_aligned=False):
            num_of_spaces = self.cols_widths[index] - len(element)
            if num_of_spaces < 1:
                return element
            left_spaces = right_spaces = " " * int(num_of_spaces / 2)
            odd_spaces = " " * int(num_of_spaces % 2)
            if left_aligned:
                return element + left_spaces + right_spaces + odd_spaces
            elif right_aligned:
                return left_spaces + right_spaces + odd_spaces + element
            else:
                return left_spaces + element + right_spaces + odd_spaces

        for ordered_line_elements in self.ordered_lines_elements:
            render_line(ordered_line_elements)

    def _add_vertical_separator_line(self):
        def get_vertical_separator():
            return " " * self.usable_display_width if not self.visible_separators else "=" * self.usable_display_width
        self.ordered_lines.append(get_vertical_separator())

    def _print_lines(self, file, end):
        for line in self.ordered_lines:
            six.print_(line, file=file, end=end)
        self._cleanup_lines()


class Columnizer(object):
    def __init__(self, display_width=80, col_sep="  "):
        self.display_width = display_width
        self.col_sep = col_sep
        self.tty_esc_codes_patterns = ['\x1b[1m', '\x1b[0m', '\033[1m', '\033[0m']
        self.saved_start_tty_esc_codes = []
        self.saved_end_tty_esc_codes = []
        self.saved_start_tty_esc_codes_helper = []
        self.saved_end_tty_esc_codes_helper = []

    def columnize(self, data):
        if not data:
            return ""
        data = self._strip_and_save_tty_esc_codes(data)

        for ncols in range(1, len(data) + 1):
            rows = self._split_row_data(data, ncols)
            for i, r in enumerate(rows):
                if not self._check_row_width(r):
                    break
                self.passed = True if i == len(rows) - 1 else False
            if getattr(self, 'passed', False):
                break
        cols_widths = self._get_cols_widths(rows)
        return "\n".join(self._format_rows(rows, cols_widths)) + "\n"

    def _check_row_width(self, row_data):
        line_length = sum([len(i) + len(self.col_sep) for i in row_data])
        return line_length < self.display_width

    def _get_cols_widths(self, rows):
        cols_widths = [0] * len(max(rows, key=len))
        for r in rows:
            for icol, col in enumerate(r):
                cols_widths[icol] = max([cols_widths[icol], len(col)])
        return cols_widths

    def _split_row_data(self, data, ncols):
        self.saved_start_tty_esc_codes = [self.saved_start_tty_esc_codes_helper[n::ncols] for n in range(0, ncols)]
        self.saved_end_tty_esc_codes = [self.saved_end_tty_esc_codes_helper[n::ncols] for n in range(0, ncols)]
        return [data[n::ncols] for n in range(0, ncols)]

    def _format_rows(self, rows, cols_widths=None):
        def get_rows_elements_lengths(rows_elements):
            return [[len(element) for element in row_elements] for row_elements in rows_elements]

        rows_elements_lengths = get_rows_elements_lengths(rows)
        rows = self._load_and_add_tty_esc_codes(rows)
        ret = []
        for irow, r in enumerate(rows):
            row = []
            for icol, col in enumerate(r):
                row.append(col + (" " * (cols_widths[icol] - rows_elements_lengths[irow][icol])))
            ret.append(self.col_sep.join(row))
        return ret

    def _strip_and_save_tty_esc_codes(self, data):
        self.saved_start_tty_esc_codes_helper = [""] * len(data)
        self.saved_end_tty_esc_codes_helper = [""] * len(data)
        ret = [None] * len(data)
        for i, word in enumerate(data):
            for p in self.tty_esc_codes_patterns:
                if word.startswith(p):
                    self.saved_start_tty_esc_codes_helper[i] = p
                    word = word.split(p)[1]
                if word.endswith(p):
                    self.saved_end_tty_esc_codes_helper[i] = p
                    word = word.split(p)[0]
            ret[i] = word
        return ret

    def _load_and_add_tty_esc_codes(self, rows):
        ret = []
        for ir, r in enumerate(rows):
            row = []
            for icol, col in enumerate(r):
                row.append(self.saved_start_tty_esc_codes[ir][icol] + col + self.saved_end_tty_esc_codes[ir][icol])
            ret.append(row)
        return ret
