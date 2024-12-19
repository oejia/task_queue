# -*- coding: utf-8 -*-

import logging

from odoo import _, models, fields, api


class TaskResult(models.Model):

    _name = 'oe.task.result'
    _description = u'Task Result'
    _inherit = ['oe.task.abstract']

    result = fields.Html(_('result'), default=None)
    date_done = fields.Datetime('done at', default=fields.Datetime.now)
    traceback = fields.Text(_('traceback'))
    execution_time = fields.Float('执行时长(秒)', digits=(16,3), readonly=True, help="任务执行耗时(秒)")

    @api.multi
    def re_execute(self):
        for obj in self:
            task = self.env['oe.task'].sudo().create({
                'task_id': '',
                'task_name': obj.task_name,
                'task_doc': obj.task_doc,
                'task_args': obj.task_args,
                'task_kwargs': obj.task_kwargs,
                'countdown': 0,
            })
            obj.write({'status': 'RETRY'})
