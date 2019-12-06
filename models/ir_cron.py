# -*- coding: utf-8 -*-

import logging

from odoo import _, models, fields, api


_logger = logging.getLogger(__name__)

class IrCron(models.Model):

    _inherit = 'ir.cron'

    @classmethod
    def _process_job(cls, job_cr, job, cron_cr):
        if job['cron_name']=='task_queue_worker':
            job['interval_number'] = 0.1
        return super(IrCron, cls)._process_job(job_cr, job, cron_cr)
