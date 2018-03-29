# -*- coding: utf-8 -*-

import logging

from odoo import _, models, fields, api
from odoo import tools
from odoo.tools import config
from celery import states


ALL_STATES = sorted(states.ALL_STATES)
TASK_STATE_CHOICES = sorted(zip(ALL_STATES, ALL_STATES))
TASK_STATE_CHOICES.append(('re_executed', u'已处理'))


class TaskResult(models.Model):

    _name = 'task.result'
    _description = u'Task'
    _auto = False

    task_id = fields.Char(_('task id'))

    task_name = fields.Char(_('task name'))
    task_args = fields.Char(_('task arguments'))
    task_kwargs = fields.Char(_('task kwargs'))

    status = fields.Selection(TASK_STATE_CHOICES, string=_('state'), default=states.PENDING)
    # content_type = fields.Char(_('content type'))
    # content_encoding = fields.Char(_('content encoding'))
    result = fields.Html(_('result'), default=None)
    date_done = fields.Datetime('done at', default=fields.Datetime.now)
    traceback = fields.Html(_('traceback'))
    # hidden = fields.Boolean(_('hidden'), default=False, index=True)
    # meta = fields.Html(_('meta'), default=None)

    @api.model_cr
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (
            select * from celery_taskmeta order by id desc
            )""" % self._table)

    @api.multi
    def name_get(self):
        return [(e.id, '<Task: {0.task_id} ({0.status})>'.format(e)) for e in self]

    @api.multi
    def re_execute(self):
        from .tasks import execute
        countdown = 0
        eta = None
        expires = None
        priority = 5
        queue = config.get('celery_default_queue', 'odoo10')

        for obj in self:
            celery_task = execute.apply_async(
                args=[''] + eval(obj.task_args), kwargs=eval(obj.task_kwargs),
                countdown=countdown, eta=eta,
                expires=expires, priority=priority,
                queue=queue)
            obj.write({'status': 're_executed'})
