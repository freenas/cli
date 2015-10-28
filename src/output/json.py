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



import json
from texttable import Texttable
from output import ValueType, get_terminal_size, resolve_cell


class JsonOutputFormatter(object):
    @staticmethod
    def format_value(value, vt):
        if value is None:
            return "none"

        if vt == ValueType.BOOLEAN:
            value = bool(value)

        if vt == ValueType.STRING:
            return str(value)

        return json.dumps(value)

    @staticmethod
    def output_list(data, label):
        print(json.dumps(list(data), indent=4))

    @staticmethod
    def output_dict(data, key_label, value_label):
        print(json.dumps(dict(data), indent=4))

    @staticmethod
    def output_table(table):
        output = []
        for row in table.data:
            rowdata = {}
            for col in table.columns:
                rowdata.update({col.label:
                    JsonOutputFormatter.format_value(resolve_cell(row, col.accessor), col.vt)})
            output.append(rowdata)

        print(json.dumps(output, indent=4))

    @staticmethod
    def output_table_list(tables):
        output = []
        for table in tables:
            output.append(JsonOutputFormatter.output_table(table))
        print(output)

    @staticmethod
    def output_tree(data, children, label):
        print(json.dumps(list(data), indent=4))

    @staticmethod
    def output_msg(data, **kwargs):
        print(json.dumps(data, indent=4))

    @staticmethod
    def output_object(obj):
        output = {}
        for item in obj:
            output[item.name] = JsonOutputFormatter.format_value(item.value, item.vt)
        print(json.dumps(output, indent=4))


def _formatter():
    return JsonOutputFormatter
