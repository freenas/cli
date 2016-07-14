import sys


class AsciiStreamOutputFormatter(object):

    @staticmethod
    def output_table(tab, file=sys.stdout):
        AsciiStreamOutputFormatter._print_table(tab, file)

    @staticmethod
    def output_object(tab, file=sys.stdout):
        pass

    @staticmethod
    def _print_table(tab, file):
        def _print_header(columns, printer=None):
            printer.print_header(columns) if printer else print([col.label for col in columns])

        def _print_rows(rows, columns, printer=None):
            for row in rows:
                printer.print_row(row) if printer else print([row[col.accessor] for col in columns])

        printer = AsciiStreamTablePrinter()
        _print_header(tab.columns, printer=printer)
        _print_rows(tab.data, tab.columns, printer=printer)


def _formatter():
    return AsciiStreamOutputFormatter


class AsciiStreamTablePrinter(object):
    def __init__(self):
        self.display_width = 120
        self.cols_widths = []
        self.ordered_line_elements = []
        self.ordered_lines_elements = [self.ordered_line_elements]
        self.ordered_lines = []

    def print_header(self, columns):
        self._compute_cols_widths(columns)
        self._load_cols_accessors(columns)
        self._load_header_elements(columns)
        self._trim_elements()
        self._render_lines()
        self._print_lines()

    def print_row(self, row):
        self._load_row_elements(row)
        self._trim_elements()
        self._render_lines()
        self._print_lines()

    def _compute_cols_widths(self, columns):
        self.cols_widths = [int(self.display_width*(col.display_width_percentage/100)) for col in columns]

    def _load_cols_accessors(self, columns):
        self.cols_accessors = [col.accessor for col in columns]

    def _load_header_elements(self, columns):
        self.ordered_line_elements = [col.label for col in columns]
        self.ordered_lines_elements = [self.ordered_line_elements]

    def _load_row_elements(self, row):
        self.ordered_line_elements = [row[accessor] for accessor in self.cols_accessors]
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
                next_line = ["" for i in range(0, len(curr_line))]
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
            ordered_line_elements_with_spaces = [surround_with_spaces(e, i) for i, e in enumerate(ordered_line_elements)]
            line = ""
            for e in ordered_line_elements_with_spaces:
                line += "|"+e+"|"
            self.ordered_lines.append(line)

        def surround_with_spaces(element, index):
            num_of_spaces = self.cols_widths[index] - len(element)
            if num_of_spaces < 1:
                return element
            return " "*int(num_of_spaces/2)+element+" "*int(num_of_spaces/2)+" "*int(num_of_spaces%2)

        for ordered_line_elements in self.ordered_lines_elements:
            render_line(ordered_line_elements)

    def _print_lines(self):
        def cleanup_lines():
            self.ordered_line_elements = []
            self.ordered_lines_elements = [self.ordered_line_elements]
            self.ordered_lines = []

        for line in self.ordered_lines:
            print(line)
        cleanup_lines()
