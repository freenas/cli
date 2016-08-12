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
from freenas.cli.namespace import SingleItemNamespace, EntityNamespace


class CliDocGen(object):
    def __init__(self):
        self.namespaces_doc_gen = NamespacesDocGen()
        self.global_commands_doc_gen = GlobalCommandsDocGen()

    def load_root_namespace(self, namespace):
        self.namespaces_doc_gen.load_root_namespace(namespace)

    def load_root_namespaces(self, namespaces):
        self.namespaces_doc_gen.load_root_namespaces(namespaces)

    def load_global_base_commands(self, command_name_and_instance_pairs):
        self.global_commands_doc_gen.load_base_commands(command_name_and_instance_pairs)

    def load_global_filtering_commands(self, command_name_and_instance_pairs):
        self.global_commands_doc_gen.load_filtering_commands(command_name_and_instance_pairs)

    def write_docs(self):
        print("Generating Global Commands documentation")
        self.global_commands_doc_gen.generate_doc_files()
        print("Generating Namespaces documentation")
        self.namespaces_doc_gen.generate_doc_files()
        self._generate_index_files()
        print("Finished")

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
        self.processor = _NamespaceProcessor()
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
            self.curr_output_file_name = "ns_" + ns.name
            self.namespaces_filenames.append(self.curr_output_file_name)
            contents = self._recursive_get_namespace_file_contents(ns)
            self._write_output_file(contents)
        self._generate_index_file()

    def _generate_index_file(self):
        'TODO finish that'
        contents = ""
        self.curr_output_file_name = self.index_file_name
        self._write_output_file(contents)

    def _recursive_get_namespace_file_contents(self, namespace, name_qualifiers=list()):
        ret = ""
        nsname, nsdescription, nscommand_name_and_docstrings_pairs, nsproperties = self.processor.extract_namespace_self_data(namespace)
        ret += self.generator.get_namespace_section(name=nsname,
                                                    description=nsdescription,
                                                    cmd_name_and_docstrings_pairs=nscommand_name_and_docstrings_pairs,
                                                    properties=nsproperties,
                                                    name_qualifiers=name_qualifiers)
        nested_namespaces, entity_commands, entity_namespaces = self.processor.extract_namespace_child_data(namespace)
        if entity_commands:
            qualifiers = name_qualifiers[:]
            qualifiers.append(nsname)
            ret += self.generator.get_namespace_section(name='<entity>',
                                                        description="",
                                                        cmd_name_and_docstrings_pairs=entity_commands,
                                                        properties=None,
                                                        name_qualifiers=qualifiers)
        if entity_namespaces:
            qualifiers = name_qualifiers[:]
            qualifiers.extend([nsname, '<entity>'])
            for n in entity_namespaces:
                ret += self._recursive_get_namespace_file_contents(n, name_qualifiers=qualifiers)
        if nested_namespaces:
            qualifiers = name_qualifiers[:]
            qualifiers.append(nsname)
            for n in nested_namespaces:
                ret += self._recursive_get_namespace_file_contents(n, name_qualifiers=qualifiers)
        return ret

    def _write_output_file(self, contents):
        with open(self.output_file_path+self.curr_output_file_name+self.output_file_ext, 'w') as f:
            f.write(contents)


class GlobalCommandsDocGen(object):
    def __init__(self):
        self.commands_type_and_list_pairs = {'base': [],
                                             'filtering': []}
        self.output_file_path = '/var/tmp/'
        self.output_file_ext = '.rst'
        self.curr_output_file_name = ""
        self.generator = _RestructuredTextFormatter()

    def load_base_commands(self, command_name_and_instance_pairs):
        self.commands_type_and_list_pairs['base'].extend(command_name_and_instance_pairs)

    def load_filtering_commands(self, command_name_and_instance_pairs):
        self.commands_type_and_list_pairs['filtering'].extend(command_name_and_instance_pairs)

    def generate_doc_files(self):
        for type, name_and_instance_pairs in self.commands_type_and_list_pairs.items():
            self.curr_output_file_name = "cmds_" + type
            contents = self._get_commands_file_contents(cmd_name_and_instance_pairs=name_and_instance_pairs,
                                                        cmds_type=type)
            self._write_output_file(contents) if contents else None

    def _get_commands_file_contents(self, cmd_name_and_instance_pairs=None, cmds_type='base'):
        contents = ""
        if not cmd_name_and_instance_pairs:
            return contents
        contents += self.generator.get_global_commands_file_top_title(commands_type=cmds_type)
        for name, instance in cmd_name_and_instance_pairs:
            docstrings = instance.get_docstrings()
            contents += self.generator.get_global_command_section(name=name,
                                                             docstrings=docstrings)
        return contents

    def _write_output_file(self, contents):
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
        self.namespace_command_name_markup_char = self.heading_markup_chars[command_name_heading_size]
        self.namespace_property_name_markup_char = self.heading_markup_chars[property_name_heading_size]
        self.namespace_commands_section_title = "Commands"
        self.namespace_properties_section_title = "Properties"
        self.global_commands_files_top_titles = {
            'base': 'Base Commands',
            'filtering': 'Filtering Commands'
        }
        self.global_commands_file_top_title_markup_char = self.heading_markup_chars[global_commands_file_top_title_size]
        self.global_command_name_markup_char = self.heading_markup_chars[global_command_name_heading_size]
        self.missing_description = "^^^^^^_____DESCRIPTION_MISSING_____^^^^^^"
        self.single_indent = "    "
        self.double_indent = 2 * self.single_indent
        self.global_command_section_formatter = _CommandSectionFormatter(
            command_name_markup_char=self.namespace_command_name_markup_char)
        self.namespace_command_section_formatter = _CommandSectionFormatter(
            command_name_markup_char=self.global_command_name_markup_char)

    def get_namespace_section(self, name, description="", cmd_name_and_docstrings_pairs=None, properties=None, name_qualifiers=list()):
        def _get_section_label(n, q=list()):
            return ".. _{0}:".format(self._get_qualified_name(n, q)) + "\n\n"

        def _get_section_title(n, q=list()):
            contents = "**" + self._get_qualified_name(n, q) + "**"
            markup = self.namespace_section_title_markup_char * len(contents)
            return markup + "\n" + contents + "\n" + markup + "\n\n"

        def _get_section_description(d=""):
            ret = self.missing_description if not d else ""
            for line in d.split("\n"):
                ret += self.single_indent + textwrap.dedent(line) + "\n"
            return ret + "\n"

        def _get_commands_subsection_title():
            contents = "*" + self.namespace_commands_section_title + "*"
            markup = self.namespace_commands_section_title_markup_char * len(contents)
            return contents + "\n" + markup + "\n\n"

        def _get_commands_subsection_contents(name_and_docstrings_pairs):
            subsection = ""
            for name, docstrings in name_and_docstrings_pairs:
                subsection += self.namespace_command_section_formatter.get_command_section(name, docstrings)
            return subsection

        def _get_properties_subsection_tile():
            content = "*" + self.namespace_properties_section_title + "*"
            markup = self.namespace_properties_section_title_markup_char * len(content)
            return content + "\n" + markup + "\n\n"

        def _get_properties_subsection_contents(namespace_name, properties):
            def _get_property_label(namespace_name, property_name):
                return ".. _{0}_{1}_property:".format(namespace_name, property_name) + "\n\n"

            def _get_property_name(name):
                content = "**" + name + "**"
                markup = self.namespace_property_name_markup_char * len(content)
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
        section += _get_section_label(name, name_qualifiers)
        section += _get_section_title(name, name_qualifiers)
        section += _get_section_description(description)
        section += _get_commands_subsection_title() if cmd_name_and_docstrings_pairs else ""
        section += _get_commands_subsection_contents(cmd_name_and_docstrings_pairs) if cmd_name_and_docstrings_pairs else ""
        section += _get_properties_subsection_tile() if properties else ""
        section += _get_properties_subsection_contents(self._get_qualified_name(name, name_qualifiers),
                                                                 properties) if properties else ""
        return section

    def get_global_commands_file_top_title(self, commands_type=None):
        contents = self.global_commands_files_top_titles[commands_type]
        markup = self.global_commands_file_top_title_markup_char * len(contents)
        return markup + '\n' + contents + '\n' + markup + '\n\n'

    def get_global_command_section(self, name, docstrings):
        return self.global_command_section_formatter.get_command_section(name, docstrings)

    @staticmethod
    def _get_qualified_name(name, qualifiers):
        return ".".join([".".join(qualifiers), name]) if qualifiers else name


class _CommandSectionFormatter(object):
    def __init__(self, command_name_markup_char=""):
        self.command_name_markup_char = command_name_markup_char
        self.missing_description = "^^^^^^_____DESCRIPTION_MISSING_____^^^^^^"
        self.missing_usage = "^^^^^^_____USAGE_MISSING_____^^^^^^"
        self.missing_examples = "^^^^^^_____EXAMPLES_MISSING_____^^^^^^"
        self.single_indent = "    "
        self.double_indent = 2 * self.single_indent

    def get_command_section(self, name, docstrings):
        ret = ""
        description, usage, examples = docstrings['description'], docstrings['usage'], docstrings['examples']
        ret += self._get_formatted_name(name)
        ret += self._get_formatted_description(description)
        ret += self._get_formatted_usage(usage)
        ret += self._get_formatted_examples(examples)
        ret += self._get_formatted_related_properties()
        return ret

    def _get_formatted_name(self, name):
        content = "**" + name + "**"
        markup = self.command_name_markup_char * len(content)
        return content + "\n" + markup + "\n\n"

    def _get_formatted_description(self, content):
        content = self.missing_description if not content else content
        ret = ""
        for l in content.split("\n"):
            ret += self.single_indent + textwrap.dedent(l) + "\n"
        return ret + "\n"

    def _get_formatted_usage(self, content):
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

    def _get_formatted_examples(self, content):
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

    def _get_formatted_related_properties(self):
        return ""

class _NamespaceProcessor(object):
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

        def _get_namespace_commands_name_docstrings_pairs(ns):
            ret = []
            for name, instance in ns.commands().items():
                ret.append([name, instance.get_docstrings()])
            return ret

        def _get_namespace_properties(ns):
            ret = []
            for p in ns.property_mappings:
                ret.append([p.name, p.usage])
            return ret

        namespace.is_docgen_instance = True
        name = namespace.name
        description = _get_namespace_description(namespace)
        command_name_and_docstrings_pairs = _get_namespace_commands_name_docstrings_pairs(namespace)
        properties = _get_namespace_properties(namespace)
        return name, description, command_name_and_docstrings_pairs, properties

    def extract_namespace_child_data(self, namespace):
        def _get_nested_namespaces(ns):
            return [n for n in ns.namespaces() if not isinstance(n, SingleItemNamespace)]

        def _get_entity_commands(ns):
            ret = []
            if not isinstance(ns, EntityNamespace):
                return ret
            entity_ns = self._instantiate_entity_namespace(ns)
            for name, instance in entity_ns.commands().items():
                ret.append([name, instance.get_docstrings()])
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

    def _instantiate_entity_namespace(self, parent_ns):
        entity = SingleItemNamespace(None, parent_ns)
        entity.orig_entity = copy.deepcopy(parent_ns.skeleton_entity)
        entity.entity = copy.deepcopy(parent_ns.skeleton_entity)
        return entity
