import sys
import six

from freenas.cli.output.ascii import *
from freenas.cli.output import get_terminal_size


class AsciiStreamOutputFormatter(AsciiOutputFormatter):
    @staticmethod
    def output_table(tab, file=sys.stdout, **kwargs):
        AsciiStreamOutputFormatter._print_table(tab, file, end=('\n' if kwargs.get('newline', True) else ' '))

    @staticmethod
    def _print_table(tab, file, end):
        def _print_header(columns, file, end, printer=None):
            printer.print_header(columns, file, end) if printer else six.print_([col.label for col in columns], file=file, end=end)

        def _print_rows(rows, columns, file, end, printer=None):
            for row in rows:
                printer.print_row(row, file, end) if printer else six.print_([row[col.accessor] for col in columns], file=file, end=end)

        printer = AsciiStreamTablePrinter()
        _print_header(tab.columns, file, end, printer=printer)
        _print_rows(tab.data, tab.columns, file, end, printer=printer)


def _formatter():
    return AsciiStreamOutputFormatter


class AsciiStreamTablePrinter(object):
    def __init__(self):
        self.display_size = get_terminal_size()[1]
        self.print_line_length = self.display_size
        self._cleanup_all()

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
        self._print_lines(file, end)

    def _compute_cols_widths(self, columns):
        default_col_width_percentage = int(100 / len(columns))
        self.borders_space = len(columns) * 2
        for col in columns:
            if not col.display_width_percentage:
                col.display_width_percentage = default_col_width_percentage
        self.cols_widths = [int((self.display_size-self.borders_space)*(col.display_width_percentage/100)) for col in columns]
        self.print_line_length = sum(self.cols_widths) + self.borders_space

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
                all_words = curr_line[elem_index].split()
                words_to_curr_line = ""
                words_to_next_line = ""
                for i, word in enumerate(all_words):
                    if len(words_to_curr_line + " " +word) < self.cols_widths[elem_index]:
                        words_to_curr_line += " " + word if words_to_curr_line else word
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
            line = ""
            for e in ordered_line_elements_with_spaces:
                line += "|"+e+"|"
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
            return "="*self.print_line_length
        self.ordered_lines.append(get_vertical_separator())

    def _print_lines(self, file, end):
        for line in self.ordered_lines:
            six.print_(line, file=file, end=end)
        self._cleanup_lines()
