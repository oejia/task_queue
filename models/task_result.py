# -*- coding: utf-8 -*-

import logging

from odoo import _, models, fields, api


class TaskResult(models.Model):

    _name = 'oe.task.result'
    _description = u'Task Result'
    _inherit = ['oe.task.abstract']

    result = fields.Html(_('result'), default=None)
    date_done = fields.Datetime('done at', default=fields.Datetime.now)
    traceback = fields.Html(_('traceback'))
