# coding=utf-8
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


import textwrap
import inspect
import re
import copy

from freenas.utils.query import wrap
from freenas.cli.namespace import SingleItemNamespace, EntityNamespace


class CliDocGen(object):
    def __init__(self):
        self.namespaces_doc_gen = NamespacesDocGen()
        self.global_commands_doc_gen = GlobalCommandsDocGen()

    def load_root_namespace(self, namespace):
        self.namespaces_doc_gen.load_root_namespace(namespace)

    def load_root_namespaces(self, namespaces):
        self.namespaces_doc_gen.load_root_namespaces(namespaces)

    def load_global_base_commands(self, commands):
        self.global_commands_doc_gen.load_base_commands(commands)

    def load_global_filtering_commands(self, commands):
        self.global_commands_doc_gen.load_filtering_commands(commands)

    def write_docs(self):
        self.global_commands_doc_gen.generate_doc_files()
        self.namespaces_doc_gen.generate_doc_files()
        self._generate_index_files()

    def _generate_index_files(self):
        pass


class NamespacesDocGen(object):
    def __init__(self):
        self.root_namespaces = []
        self.namespaces_filenames = []
        self.output_file_path = '/var/tmp/'
        self.index_file_name = 'tmp_index'
        self.output_file_ext = '.rst'
        self.curr_output_file_name = ""
        self.processor = _CliEntitiesProcessor()
        self.generator = _RestructuredTextFormatter(namespace_title_heading_size='h2',
                                                    commands_section_title_heading_size='h3',
                                                    properties_section_title_heading_size='h3',
                                                    command_name_heading_size='h4',
                                                    property_name_heading_size='h4')

    def load_root_namespace(self, namespace):
        self.root_namespaces.append(namespace)

    def load_root_namespaces(self, namespaces):
        self.root_namespaces.extend(namespaces)

    def generate_doc_files(self):
        for ns in self.root_namespaces:
            self.curr_output_file_name = ns.name
            self.namespaces_filenames.append(self.curr_output_file_name)
            contents = self._recursive_get_namespace_file_contents(ns)
            self._write_output_file(contents)
        self._generate_index_file()

    def _generate_index_file(self):
        'TODO finish that'
        contents = ""
        self.curr_output_file_name = self.index_file_name
        for fn in self.namespaces_filenames:
            print(fn)
        self._write_output_file(contents)

    def _recursive_get_namespace_file_contents(self, namespace, name_qualifiers=list()):
        ret = ""
        name, description, commands, properties = self.processor.extract_namespace_self_data(namespace)
        ret += self.generator.get_namespace_section(name=name,
                                                    description=description,
                                                    commands=commands,
                                                    properties=properties,
                                                    name_qualifiers=name_qualifiers)
        nested_namespaces, entity_commands, entity_namespaces = self.processor.extract_namespace_child_data(namespace)
        if entity_commands:
            qualifiers = name_qualifiers[:]
            qualifiers.append(name)
            ret += self.generator.get_namespace_section(name='<entity>',
                                                        description="",
                                                        commands=entity_commands,
                                                        properties=None,
                                                        name_qualifiers=qualifiers)
        if entity_namespaces:
            qualifiers = name_qualifiers[:]
            qualifiers.extend([name, '<entity>'])
            for n in entity_namespaces:
                ret += self._recursive_get_namespace_file_contents(n, name_qualifiers=qualifiers)
        if nested_namespaces:
            qualifiers = name_qualifiers[:]
            qualifiers.append(name)
            for n in nested_namespaces:
                ret += self._recursive_get_namespace_file_contents(n, name_qualifiers=qualifiers)
        return ret

    def _write_output_file(self, contents):
        print("PGLOG_write_output_file:")
        with open(self.output_file_path+self.curr_output_file_name+self.output_file_ext, 'w') as f:
            f.write(contents)


class GlobalCommandsDocGen(object):
    def __init__(self):
        self.base_commands = []
        self.filtering_commands = []
        self.output_file_path = '/var/tmp/'
        self.output_file_ext = '.rst'
        self.curr_output_file_name = ""
        self.processor = _CliEntitiesProcessor()
        self.generator = _RestructuredTextFormatter()

    def load_base_commands(self, commands):
        self.base_commands.extend(commands)

    def load_filtering_commands(self, commands):
        self.filtering_commands.extend(commands)

    def generate_doc_files(self):
        type = 'base'
        self.curr_output_file_name = "cmds_" + type
        contents = self._get_commands_file_contents(commands=self.base_commands,
                                                    type=type)
        self._write_output_file(contents)

        type = 'filtering'
        self.curr_output_file_name = "cmds_" + type
        contents = self._get_commands_file_contents(commands=self.filtering_commands,
                                                    type=type)
        self._write_output_file(contents)

    def _get_commands_file_contents(self, commands=[], type='base'):
        ret = ""
        ret += self.generator.get_global_commands_file_top_title(commands_type=type)
        for name, instance in commands:
            description = self.processor.extract_command_data(instance)
            ret += self.generator.get_global_command_section(name=name,
                                                             text=description)
        return ret

    def _write_output_file(self, contents):
        print("PGLOG_write_output_file:")
        with open(self.output_file_path+self.curr_output_file_name+self.output_file_ext, 'w') as f:
            f.write(contents)


class _RestructuredTextFormatter(object):
    def __init__(self,
                 namespace_title_heading_size='h2',
                 commands_section_title_heading_size='h3',
                 properties_section_title_heading_size='h3',
                 command_name_heading_size='h4',
                 property_name_heading_size='h4',
                 global_commands_file_top_title_size='h2',
                 global_command_name_heading_size='h3'):
        self.heading_markup_chars = {
            'h1': '#',
            'h2': '*',
            'h3': '=',
            'h4': '-',
            'h5': '^',
            'h6': '"',
        }
        self.namespace_section_title_markup_char = self.heading_markup_chars[namespace_title_heading_size]
        self.namespace_commands_section_title_markup_char = self.heading_markup_chars[
            commands_section_title_heading_size]
        self.namespace_properties_section_title_markup_char = self.heading_markup_chars[
            properties_section_title_heading_size]
        self.command_name_markup_char = self.heading_markup_chars[command_name_heading_size]
        self.property_name_markup_char = self.heading_markup_chars[property_name_heading_size]
        self.namespace_commands_section_title = "Commands"
        self.namespace_properties_section_title = "Properties"
        self.global_commands_files_top_titles = {
            'base': 'Base Commands',
            'filtering': 'Filtering Commands'
        }
        self.global_commands_file_top_title_markup_char = self.heading_markup_chars[global_commands_file_top_title_size]
        self.global_command_name_markup_char = self.heading_markup_chars[global_command_name_heading_size]
        self.single_indent = "    "
        self.double_indent = 2 * self.single_indent
        self.missing_description = "^^^^^^_____DESCRIPTION_MISSING_____^^^^^^"
        self.missing_usage = "^^^^^^_____USAGE_MISSING_____^^^^^^"
        self.missing_examples = "^^^^^^_____EXAMPLES_MISSING_____^^^^^^"

    def get_namespace_section(self, name, description="", commands=None, properties=None, name_qualifiers=list()):
        def _get_namespace_section_label(n, q=list()):
            return ".. _{0}:".format(self._get_qualified_name(n, q)) + "\n\n"

        def _get_namespace_section_title(n, q=list()):
            contents = "**" + self._get_qualified_name(n, q) + "**"
            markup = self.namespace_section_title_markup_char * len(contents)
            return markup + "\n" + contents + "\n" + markup + "\n\n"

        def _get_namespace_section_description(d=""):
            ret = self.missing_description if not d else ""
            for line in d.split("\n"):
                ret += self.single_indent + textwrap.dedent(line) + "\n"
            return ret + "\n"

        def _get_namespace_commands_subsection_title():
            contents = "*" + self.namespace_commands_section_title + "*"
            markup = self.namespace_commands_section_title_markup_char * len(contents)
            return contents + "\n" + markup + "\n\n"

        def _get_namespace_commands_subsection_contents(commands):
            def _extract_command_data(text=None):
                def preserve_blank_lines_in_docstring():
                    return "\n\n" if description else ""

                description = usage = examples = ""
                if not text:
                    return description, usage, examples
                for lines in text.split("\n\n"):
                    if 'Usage' not in lines and 'Example' not in lines:
                        description += preserve_blank_lines_in_docstring() + lines
                    if not usage:
                        usage = lines.split("Usage:")[1] if 'Usage' in lines else None
                    if not examples:
                        examples = re.split("Examples?:", lines)[1] if 'Example' in lines else None
                return description, usage, examples

            def _get_command_name(name):
                content = "**" + name + "**"
                markup = self.command_name_markup_char * len(content)
                return content + "\n" + markup + "\n\n"

            def _get_command_description(content):
                content = self.missing_description if not content else content
                ret = ""
                for l in content.split("\n"):
                    ret += self.single_indent + textwrap.dedent(l) + "\n"
                return ret + "\n"

            def _get_command_usage(content):
                def _get_title():
                    content = "**Usage:**"
                    markup = "::"
                    return self.single_indent + content + "\n" + self.single_indent + markup + "\n\n"

                def _get_usage(content):
                    content = self.missing_usage if not content else content
                    ret = ""
                    for l in content.split("\n"):
                        ret += self.double_indent + textwrap.dedent(l) + "\n"
                    return ret + "\n"

                return _get_title() + _get_usage(content)

            def _get_command_examples(content):
                def _get_title():
                    content = "**Examples:**"
                    markup = "::"
                    return self.single_indent + content + "\n" + self.single_indent + markup + "\n\n"

                def _get_examples(content):
                    content = self.missing_examples if not content else content
                    ret = ""
                    for l in content.split("\n"):
                        if l :
                            ret += self.double_indent + textwrap.dedent(l) + "\n"
                    return ret + "\n"

                return _get_title() + _get_examples(content)

            def _get_command_related_properties():
                return ""

            ret = ""
            for name, text in commands:
                description, usage, examples = _extract_command_data(text)
                ret += _get_command_name(name)
                ret += _get_command_description(description)
                ret += _get_command_usage(usage)
                ret += _get_command_examples(examples)
                ret += _get_command_related_properties()
            return ret

        def _get_namespace_properties_subsection_tile():
            content = "*" + self.namespace_properties_section_title + "*"
            markup = self.namespace_properties_section_title_markup_char * len(content)
            return content + "\n" + markup + "\n\n"

        def _get_namespace_properties_subsection_contents(namespace_name, properties):
            def _get_property_label(namespace_name, property_name):
                return ".. _{0}_{1}_property:".format(namespace_name, property_name) + "\n\n"

            def _get_property_name(name):
                content = "**" + name + "**"
                markup = self.command_name_markup_char * len(content)
                return content + "\n" + markup + "\n\n"

            def _get_property_description(descr):
                content = self.missing_description if not descr else descr
                ret = ""
                for l in content.split("\n"):
                    ret += self.single_indent + textwrap.dedent(l) + "\n"
                return ret + "\n"

            ret = ""
            for pname, ptext in properties:
                ret += _get_property_label(namespace_name, pname)
                ret += _get_property_name(pname)
                ret += _get_property_description(ptext)
            return ret

        section = ""
        section += _get_namespace_section_label(name, name_qualifiers)
        section += _get_namespace_section_title(name, name_qualifiers)
        section += _get_namespace_section_description(description)
        section += _get_namespace_commands_subsection_title() if commands else ""
        section += _get_namespace_commands_subsection_contents(commands) if commands else ""
        section += _get_namespace_properties_subsection_tile() if properties else ""
        section += _get_namespace_properties_subsection_contents(self._get_qualified_name(name, name_qualifiers),
                                                                 properties) if properties else ""
        return section

    def get_global_commands_file_top_title(self, commands_type=None):
        contents = self.global_commands_files_top_titles[commands_type]
        markup = self.global_commands_file_top_title_markup_char * len(contents)
        return markup + '\n' + contents + '\n' + markup + '\n\n'

    def get_global_command_section(self, name, text):
        def _get_command_section_title(name):
            contents = "**" + name + "**"
            markup = self.global_command_name_markup_char * len(contents)
            return contents + '\n' + markup + '\n\n'

        def _get_command_section_contents(text):
            def _extract_command_data(text=None):
                def preserve_blank_lines_in_docstring():
                    return "\n\n" if description else ""

                description = usage = examples = ""
                if not text:
                    return description, usage, examples
                for lines in text.split("\n\n"):
                    if 'Usage' not in lines and 'Example' not in lines:
                        description += preserve_blank_lines_in_docstring() + lines
                    if not usage:
                        usage = lines.split("Usage:")[1] if 'Usage' in lines else None
                    if not examples:
                        examples = re.split("Examples?:", lines)[1] if 'Example' in lines else None
                return description, usage, examples


            def _get_command_description(content):
                content = self.missing_description if not content else content
                ret = ""
                for l in content.split("\n"):
                    ret += self.single_indent + textwrap.dedent(l) + "\n"
                return ret + "\n"

            def _get_command_usage(content):
                def _get_title():
                    content = "**Usage:**"
                    markup = "::"
                    return self.single_indent + content + "\n" + self.single_indent + markup + "\n\n"

                def _get_usage(content):
                    content = self.missing_usage if not content else content
                    ret = ""
                    for l in content.split("\n"):
                        ret += self.double_indent + textwrap.dedent(l) + "\n"
                    return ret + "\n"

                return _get_title() + _get_usage(content)

            def _get_command_examples(content):
                def _get_title():
                    content = "**Examples:**"
                    markup = "::"
                    return self.single_indent + content + "\n" + self.single_indent + markup + "\n\n"

                def _get_examples(content):
                    content = self.missing_examples if not content else content
                    ret = ""
                    for l in content.split("\n"):
                        if l :
                            ret += self.double_indent + textwrap.dedent(l) + "\n"
                    return ret + "\n"

                return _get_title() + _get_examples(content)

            def _get_command_related_properties():
                return ""

            ret = ""
            description, usage, examples = _extract_command_data(text)
            ret += _get_command_description(description)
            ret += _get_command_usage(usage)
            ret += _get_command_examples(examples)
            ret += _get_command_related_properties()
            return ret

        ret = ""
        ret += _get_command_section_title(name)
        ret += _get_command_section_contents(text)

        return ret

    @staticmethod
    def _get_qualified_name(name, qualifiers):
        return ".".join([".".join(qualifiers), name]) if qualifiers else name


class _CliEntitiesProcessor(object):
    def __init__(self):
        pass

    def extract_namespace_self_data(self, namespace):
        def _get_namespace_description(ns):
            if ns.__class__.__doc__:
                ret = inspect.getdoc(ns)
            elif hasattr(ns, 'description'):
                ret = ns.description
            else:
                ret = ""
            return ret

        def _get_namespace_commands(ns):
            ret = []
            for name, instance in ns.commands().items():
                ret.append([name, self._get_command_doctext(instance)])
            return ret

        def _get_namespace_properties(ns):
            ret = []
            for p in ns.property_mappings:
                ret.append([p.name, p.usage])
            return ret

        namespace.is_docgen_instance = True
        name = namespace.name
        description = _get_namespace_description(namespace)
        commands = _get_namespace_commands(namespace)
        properties = _get_namespace_properties(namespace)
        return name, description, commands, properties

    def extract_namespace_child_data(self, namespace):
        def _get_nested_namespaces(ns):
            return [n for n in ns.namespaces() if not isinstance(n, SingleItemNamespace)]

        def _get_entity_commands(ns):
            ret = []
            if not isinstance(ns, EntityNamespace):
                return ret
            entity_ns = self._instantiate_entity_namespace(ns)
            for name, instance in entity_ns.commands().items():
                ret.append([name, self._get_command_doctext(instance)])
            return ret

        def _get_entity_namespaces(ns):
            ret = []
            if not isinstance(ns, EntityNamespace):
                return ret
            entity_ns = self._instantiate_entity_namespace(ns)
            return [n for n in entity_ns.namespaces()]

        namespace.is_docgen_instance = True
        nested_namespaces = _get_nested_namespaces(namespace)
        entity_commands = _get_entity_commands(namespace)
        entity_namespaces = _get_entity_namespaces(namespace)
        return nested_namespaces, entity_commands, entity_namespaces

    def extract_command_data(self, instance):
        return self._get_command_doctext(instance)

    def _get_command_doctext(self, instance):
        def _parent_has_localdoc(cmd):
            if not hasattr(cmd, 'parent') or not hasattr(cmd.parent, 'localdoc'):
                return False
            return cmd.__class__.__name__ in cmd.parent.localdoc.keys()

        def _get_localdoc(cmd):
            return textwrap.dedent(cmd.parent.localdoc[cmd.__class__.__name__])

        def _get_docstring(cmd):
            return inspect.getdoc(cmd)

        return _get_localdoc(instance) if _parent_has_localdoc(instance) else _get_docstring(instance)

    def _instantiate_entity_namespace(self, parent_ns):
        entity = SingleItemNamespace(None, parent_ns)
        entity.orig_entity = wrap(copy.deepcopy(parent_ns.skeleton_entity))
        entity.entity = wrap(copy.deepcopy(parent_ns.skeleton_entity))
        return entity
