import io
import six
import sys
import datetime
import time
import gettext
import natural.date

from dateutil.parser import parse
from freenas.cli import config
from freenas.cli.output import ValueType, get_terminal_size, resolve_cell, get_humanized_size, Table
from freenas.cli.utils import get_localtime_offset
from freenas.utils.permissions import int_to_string


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


class AsciiStreamOutputFormatter(object):

    @staticmethod
    def format_value(value, vt):
        if vt == ValueType.BOOLEAN:
            return _("yes") if value else _("no")

        if value is None:
            return _("none")

        if vt == ValueType.SET:
            value = set(value)
            if len(value) == 0:
                return _("empty")

            return '\n'.join(value)

        if vt == ValueType.ARRAY:
            value = list(value)
            if len(value) == 0:
                return _("empty")

            return '\n'.join(value)

        if vt == ValueType.DICT:
            if not bool(value):
                return _("empty")

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

    @staticmethod
    def output_msg(message, **kwargs):
        six.print_(
            format_literal(message, **kwargs),
            end=('\n' if kwargs.get('newline', True) else ' '),
            file=kwargs.pop('file', sys.stdout)
        )

    @staticmethod
    def output_table(tab, file=sys.stdout):
        AsciiStreamOutputFormatter._print_table(tab, file)

    @staticmethod
    def output_object(tab, file=sys.stdout):
        pass

    @staticmethod
    def _print_table(tab, file):
        def _print_header(columns, printer=None):
            printer.print_header(columns) if printer else six.print_([col.label for col in columns])

        def _print_rows(rows, columns, printer=None):
            for row in rows:
                printer.print_row(row) if printer else six.print_([row[col.accessor] for col in columns])

        printer = AsciiStreamTablePrinter()
        _print_header(tab.columns, printer=printer)
        _print_rows(tab.data, tab.columns, printer=printer)


def _formatter():
    return AsciiStreamOutputFormatter


class AsciiStreamTablePrinter(object):
    def __init__(self):
        self.display_width = 120
        self._cleanup_all()

    def _cleanup_all(self):
        self.cols_widths = []
        self._cleanup_lines()

    def _cleanup_lines(self):
        self.ordered_line_elements = []
        self.ordered_lines_elements = []
        self.ordered_lines = []

    def print_header(self, columns):
        self._compute_cols_widths(columns)
        self._load_accessors(columns)
        self._load_value_types(columns)
        self._load_header_elements(columns)
        self._trim_elements()
        self._render_lines()
        self._add_vertical_separator_line()
        self._print_lines()

    def print_row(self, row):
        self._load_row_elements(row)
        self._trim_elements()
        self._render_lines()
        self._print_lines()

    def _compute_cols_widths(self, columns):
        default_col_width_percentage = int(100 / len(columns))  #-borders
        for col in columns:
            if not col.display_width_percentage:
                col.display_width_percentage = default_col_width_percentage
        self.cols_widths = [int(self.display_width*(col.display_width_percentage/100)) for col in columns]

    def _load_accessors(self, columns):
        self.accessors = [col.accessor for col in columns]

    def _load_value_types(self, columns):
        self.value_types = [col.vt for col in columns]

    def _load_header_elements(self, columns):
        self.ordered_line_elements = [col.label for col in columns]
        self.ordered_lines_elements = [self.ordered_line_elements]

    def _load_row_elements(self, row):
        for i, acc in enumerate(self.accessors):
            if callable(acc):
                elem = acc(row)
            else:
                elem = row[acc]

            self.ordered_line_elements.append(AsciiStreamOutputFormatter.format_value(elem, self.value_types[i]))
        self.ordered_lines_elements = [self.ordered_line_elements]

    def _trim_elements(self):
        def split_line_element(line_index, elem_index, element):
            def has_2ormore_words(element):
                return len(element.split()) > 1

            def try_pretty_split(element, index):
                return len(element.split()[0]) < self.cols_widths[index]

            def do_pretty_split(curr_line, next_line, elem_index):
                splitted = curr_line[elem_index].split()
                curr_line[elem_index] = splitted[0]
                next_line[elem_index] = " ".join(splitted[1:])
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
                surround_with_spaces(e, i) for i, e in enumerate(ordered_line_elements)
            ]
            line = ""
            for e in ordered_line_elements_with_spaces:
                line += "|"+e+"|"
            self.ordered_lines.append(line)

        def surround_with_spaces(element, index):
            num_of_spaces = self.cols_widths[index] - len(element)
            if num_of_spaces < 1:
                return element
            return " "*int(num_of_spaces/2)+element+" "*int(num_of_spaces/2)+" "*int(num_of_spaces % 2)

        for ordered_line_elements in self.ordered_lines_elements:
            render_line(ordered_line_elements)

    def _add_vertical_separator_line(self):
        def get_vertical_separator():
            return "="*self.display_width
        self.ordered_lines.append(get_vertical_separator())

    def _print_lines(self):
        for line in self.ordered_lines:
            six.print_(line)
        self._cleanup_lines()
