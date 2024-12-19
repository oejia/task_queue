# -*- coding: utf-8 -*-

import logging
import json

from odoo import _, models, fields, api


class TaskResult(models.Model):

    _name = 'oe.task.result'
    _description = u'Task Result'
    _inherit = ['oe.task.abstract']
    _rec_name = 'task_name'

    result = fields.Text(_('result'), default=None)
    date_done = fields.Datetime('done at')
    traceback = fields.Text(_('traceback'))
    execution_time = fields.Float('执行时长(秒)', digits=(16,3), readonly=True, help="任务执行耗时(秒)")
    display_args = fields.Char('参数信息', compute='_compute_display_args', store=False)

    @api.depends('task_args')
    def _compute_display_args(self):
        for record in self:
            if not record.task_args:
                record.display_args = ''
                continue
                
            try:
                args = json.loads(record.task_args)
                if len(args) < 4:  # 参数不完整
                    record.display_args = ''
                    continue
                    
                # 解析参数
                dbname = args[0]  # 数据库名
                uid = args[1]     # 用户ID
                model_name = args[2]  # 模型名
                method = args[3]   # 方法名
                ids = args[4]      # 记录IDs
                other_args = args[5:-1]  # 其他参数(排除token)
                
                # 获取记录名称
                records_name = ''
                if ids and isinstance(ids, list):
                    try:
                        records = self.env[model_name].sudo().browse(ids).exists()
                        if records:
                            records_name = ','.join(records.mapped('display_name'))
                    except Exception as e:
                        _logger.warning('Failed to get record names: %s', e)
                
                # 组装显示内容
                parts = []
                if records_name:
                    parts.append(records_name)
                elif ids:
                    parts.append(f"IDs: {ids}")
                    
                # 添加其他参数
                if other_args:
                    args_str = ', '.join(str(arg) for arg in other_args)
                    if args_str:
                        parts.append(f"参数: {args_str}")
                
                record.display_args = ' | '.join(parts) or '无参数'
                
            except Exception as e:
                record.display_args = '参数解析失败'
                _logger.error('Failed to compute display_args: %s', e)

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

    @api.multi
    def name_get(self):
        result = []
        for record in self:
            # 组合显示名称: 任务说明 - 任务名称 [状态]
            name = "%s - %s [%s]" % (
                record.task_doc or '',
                record.task_name or '',
                dict(self._fields['status'].selection).get(record.status, '')
            )
            result.append((record.id, name))
        return result
