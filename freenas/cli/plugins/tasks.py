# +
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

import gettext
from freenas.cli.output import ValueType
from freenas.cli.descriptions import tasks
from freenas.cli.namespace import EntityNamespace, EntitySubscriberBasedLoadMixin, Command, BaseListCommand, description
from freenas.cli.complete import NullComplete
from freenas.cli.utils import describe_task_state


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Submits new task")
class SubmitCommand(Command):
    """
    Usage: submit <task>

    Submits a task to the dispatcher for execution

    Examples:
        submit update.check
    """
    def run(self, context, args, kwargs, opargs):
        name = args.pop(0)
        context.submit_task(name, *args)


@description("Aborts running task")
class AbortCommand(Command):
    """
    Usage: abort

    Submits a task to the dispatcher for execution

    Examples:
        submit update.check
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.call_sync('task.abort', self.parent.entity['id'])


class TaskListCommand(BaseListCommand):
    RUNNING_STATES = ['CREATED', 'WAITING', 'EXECUTING', 'ROLLBACK']

    def run(self, context, args, kwargs, opargs, filtering=None):
        states = []

        if not args:
            states = self.RUNNING_STATES

        if 'all' in args:
            return super(TaskListCommand, self).run(context, args, kwargs, opargs, filtering)

        if 'aborted' in args:
            states.append('ABORTED')

        if 'finished' in args:
            states.append('FINISHED')

        if 'failed' in args:
            states.append('FAILED')

        if 'running' in args:
            states += self.RUNNING_STATES

        return super(TaskListCommand, self).run(context, args, kwargs, opargs, {
            'filter': [('state', 'in', states)],
            'params': {}
        })

    def complete(self, context):
        return [
            NullComplete('all'),
            NullComplete('aborted'),
            NullComplete('finished'),
            NullComplete('failed'),
            NullComplete('running')
        ]


@description("Browse and abort running tasks")
class TasksNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The task namespace provides commands for browsing task history
    and for aborting running tasks.
    """
    def __init__(self, name, context):
        super(TasksNamespace, self).__init__(name, context)

        self.allow_create = False
        self.allow_edit = False
        self.entity_subscriber_name = 'task'

        self.add_property(
            descr='ID',
            name='id',
            usage=_("""
            Task ID. Read-only value assigned by the operating
            system."""),
            get='id',
            list=True,
        )

        self.add_property(
            descr='Description',
            name='description',
            usage=_("""
            Task description. Read-only value assigned by the operating
            system."""),
            get=self.describe_task,
        )

        self.add_property(
            descr='Started at',
            name='started_at',
            usage=_("""
            When the task started. Read-only value assigned by the
            operating system."""),
            get='started_at',
            list=True,
            type=ValueType.TIME
        )

        self.add_property(
            descr='Finished at',
            name='finished_at',
            usage=_("""
            When the task finished. Read-only value assigned by the
            operating system."""),
            get='finished_at',
            list=True,
            type=ValueType.TIME
        )

        self.add_property(
            descr='State',
            name='state',
            usage=_("""
            Current state of the task. Read-only value assigned by the
            operating system."""),
            get='state',
            set=None
        )

        self.add_property(
            descr='Status',
            name='status',
            usage=_("""
            Current task status. Read-only value assigned by the
            operating system."""),
            get=describe_task_state,
            set=None
        )

        self.add_property(
            descr='Validation errors',
            name='validation',
            get=self.describe_validation_errors,
            type=ValueType.SET,
            set=None,
            list=False,
            condition=lambda t: t.get('error.type') == 'ValidationException'
        )

        self.primary_key = self.get_mapping('id')
        self.entity_commands = lambda this: {
            'abort': AbortCommand(this)
        }

        self.extra_commands = {
            'submit': SubmitCommand(),
            'show': TaskListCommand(self)
        }

    def serialize(self):
        raise NotImplementedError()

    def describe_validation_errors(self, task):
        return ('{0}: {1}'.format(p, m) for p, __, m in self.context.get_validation_errors(task))

    def describe_task(self, task):
        return tasks.translate(self.context, task['name'], task['args'])


def _init(context):
    context.attach_namespace('/', TasksNamespace('task', context))
