# -*- coding: utf-8 -*-

import json
import logging
import traceback

import odoo
from odoo import _, models, fields, api
from odoo.api import Environment

from ..api import AsyncDB

_logger = logging.getLogger(__name__)

class TaskAbstract(models.AbstractModel):

    _name = "oe.task.abstract"

    task_id = fields.Char(_('task id'))
    task_name = fields.Char(_('task name'))
    task_args = fields.Char(_('task arguments'))
    task_kwargs = fields.Char(_('task kwargs'))

    status = fields.Selection([
        ('PENDING', '待执行'),
        ('STARTED', '执行中'),
        ('SUCCESS', '完成'),
        ('FAILURE','执行失败'),
        ('REVOKED','已撤销'),
        ('RETRY','已重执行'), # RECEIVED
    ], string=_('state'), default='PENDING')

    priority = fields.Integer('priority')
    queue = fields.Char('queue')


class TaskTask(models.Model):

    _name = 'oe.task'
    _description = u'Task'
    _inherit = ['oe.task.abstract']


    #@api.multi
    def run(self, tasks):
        for task in tasks:
            task_args = json.loads(task['task_args'])
            task_kwargs = json.loads(task['task_kwargs'])
            dbname = task_args.pop(0)
            uid = task_args.pop(0)
            model_name = task_args.pop(0)
            method = task_args.pop(0)
            ids = task_args.pop(0)

            _context = 'context' in task_kwargs and task_kwargs.pop('context') or {}
            env = Environment(self.env.cr, uid, _context)
            #env = self.with_context().env
            Model = env[model_name]

            try:
                objs = Model.search([('id', 'in', ids)])
                getattr(env.registry[model_name], method)(objs, *task_args, **task_kwargs)
                env.cr.commit()
            except Exception as exc:
                env.cr.rollback()
                trace = traceback.print_exc()
                self.env['oe.task.result'].sudo().create({
                    'task_id': task['id'],
                    'task_name': task['task_name'],
                    'task_args': task['task_args'],
                    'task_kwargs': task['task_kwargs'],
                    'status': 'FAILURE',
                    'traceback': trace,
                })
            finally:
                #task.unlink()
                self.delete(task)
                self.env.cr.commit()

    def delete(self,task):
        self.env.cr.execute('delete from oe_task where id=%s'%task['id'])

    def _process(self):
        while True:
            import time;time.sleep(2)
            db = odoo.sql_db.db_connect(self.env.cr.dbname)
            tasks = []
            with db.cursor() as cr:
                _logger.info('>>> _process tasks')
                cr.execute("select * from oe_task where status='PENDING'")
                tasks = cr.dictfetchall()
            self.run(tasks)
                #self.search([('status', '=', 'PENDING')]).run()

    @AsyncDB()
    @api.model
    def get_count(self):
        _logger.info('>>> get_task_count result %s', self.search_count([]))
