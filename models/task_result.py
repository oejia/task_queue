# -*- coding: utf-8 -*-

import logging
import json

from odoo import _, models, fields, api


class TaskResult(models.Model):

    _name = 'oe.task.result'
    _description = u'Task Result'
    _inherit = ['oe.task.abstract']

    result = fields.Text(_('result'), default=None)
    date_done = fields.Datetime('done at')
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

    @api.multi
    def view_result(self):
        self.ensure_one()
        if not self.result:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('提示'),
                    'message': _('没有可查看的执行结果'),
                    'type': 'warning',
                }
            }
        
        try:
            result = json.loads(self.result)
            # 判断是否是Odoo action
            if isinstance(result, dict) and result.get('type') in ['ir.actions.act_window', 'ir.actions.client']:
                return result
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('提示'),
                        'message': _('执行结果不是可打开的操作'),
                        'type': 'warning',
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('错误'),
                    'message': _('解析执行结果失败: %s') % str(e),
                    'type': 'danger',
                }
            }
