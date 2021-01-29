# coding=utf-8

import logging
import json
import datetime

from odoo import _, models, fields, api
from odoo import modules

from ..api import AsyncDB

_logger = logging.getLogger(__name__)


class DateEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj,datetime.datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return json.JSONEncoder.default(self,obj)

class OeEvent(models.Model):

    _name = 'oe.event'
    _description = u'事件'

    model_id = fields.Many2one('ir.model', string='模型', required=True)
    field_ids = fields.Many2many('ir.model.fields', string='监听字段')
    etype = fields.Selection([('create', '创建'), ('write',u'更新'),('unlink',u'删除')], string=u'事件类型', required=True)
    enable = fields.Boolean('启用', default=False)
    subscribe_ids = fields.One2many('oe.event.subscribe', 'event_id', string='事件订阅')

    def _register_hook(self):
        super(OeEvent, self)._register_hook()
        _logger.info('>>> _register_hook')
        if not self:
            self = self.search([('enable', '=', True)])
        return self._patch_methods()

    def _make_create(self):
        obj = self
        event_obj_id = obj.id

        @api.model_create_multi
        @api.returns('self', lambda value: value.id)
        def event_create(self, vals_list, **kwargs):
            new_records = event_create.origin(self, vals_list, **kwargs)
            for i in range(len(vals_list)):
                self.env['oe.event'].sudo().browse(event_obj_id).execute_create(new_records[i].id, json.dumps(vals_list[i], cls=DateEncoder))
            return new_records
        return event_create

    def _make_write(self):
        obj = self
        event_obj_id = obj.id

        @api.multi
        def event_write(self, vals, **kwargs):
            event_obj = self.env['oe.event'].sudo().browse(event_obj_id)
            field_list = [e.name for e in event_obj.field_ids]
            flag = False
            if field_list:
                for k in vals.keys():
                    if k in field_list:
                        flag = True
                        break
            else:
                flag = True

            if flag:
                old_vals_map = {e.id : e.read(vals.keys())[0] for e in self.sudo()}
                res = event_write.origin(self, vals, **kwargs)
                for res in self.sudo():
                    old_vals = old_vals_map.get(res.id)
                    record_flag = False
                    if field_list:
                        for _field in field_list:
                            old_val = old_vals[_field]
                            if type(old_val) in [list, tuple]:
                                old_val = old_val[0]
                            if vals[_field]!=old_val:
                                record_flag = True
                                break
                    else:
                        record_flag = True
                    if record_flag:
                        event_obj.execute_write(res.id, json.dumps(old_vals, cls=DateEncoder), json.dumps(vals, cls=DateEncoder))
                return res
            else:
                return event_write.origin(self, vals, **kwargs)

        return event_write

    def _make_unlink(self):
        obj = self
        event_obj_id = obj.id

        @api.multi
        def event_unlink(self, **kwargs):
            res = event_unlink.origin(self, **kwargs)
            for res in self.sudo():
                self.env['oe.event'].sudo().browse(event_obj_id).execute_unlink(res.id)
            return res
        return event_unlink

    @api.multi
    def _patch_methods(self):
        updated = False
        for obj in self:
            model_model = self.env[obj.model_id.model]
            if obj.etype=='create' and not hasattr(model_model, 'oe_event_create'):
                model_model._patch_method('create', obj._make_create())
                setattr(type(model_model), 'oe_event_create', True)
                updated = True
            if obj.etype=='write' and not hasattr(model_model, 'oe_event_write'):
                model_model._patch_method('write', obj._make_write())
                setattr(type(model_model), 'oe_event_write', True)
                updated = True
            if obj.etype=='unlink' and not hasattr(model_model, 'oe_event_unlink'):
                model_model._patch_method('unlink', obj._make_unlink())
                setattr(type(model_model), 'oe_event_unlink', True)
                updated = True

    @AsyncDB()
    @api.multi
    def execute_create(self, res_id, vals):
        for obj in self:
            for subscribe in obj.subscribe_ids:
                log = self.env['oe.event.log'].create({
                    'subscribe_id': subscribe.id,
                    'res_model': subscribe.event_id.model_id.model,
                    'res_id': res_id,
                    'etype': subscribe.event_id.etype,
                    'new_vals': vals,
                })
                self.exec_server_action(log, subscribe.action_server_id)

    @AsyncDB()
    @api.multi
    def execute_write(self, res_id, old_vals, new_vals):
        for obj in self:
            for subscribe in obj.subscribe_ids:
                log = self.env['oe.event.log'].create({
                    'subscribe_id': subscribe.id,
                    'res_model': subscribe.event_id.model_id.model,
                    'res_id': res_id,
                    'etype': subscribe.event_id.etype,
                    'old_vals': old_vals,
                    'new_vals': new_vals,
                })
                self.exec_server_action(log, subscribe.action_server_id)


    @AsyncDB()
    @api.multi
    def execute_unlink(self, res_id):
        for obj in self:
            for subscribe in obj.subscribe_ids:
                log = self.env['oe.event.log'].create({
                    'subscribe_id': subscribe.id,
                    'res_model': subscribe.event_id.model_id.model,
                    'res_id': res_id,
                    'etype': subscribe.event_id.etype,
                })
                self.exec_server_action(log, subscribe.action_server_id)

    def exec_server_action(self, log, action):
        _logger.info('>>> exec_server_action %s %s', log, action)
        new_context = dict(self._context) or {}
        new_context.update({
            'active_id': log.id,
            'active_ids': [log.id],
            'active_model': 'oe.event.log',
        })
        #self.env.cr.commit()
        action.sudo().with_context(new_context).run()
        #self.env.cr.commit()

    @api.multi
    def _revert_methods(self):
        updated = False
        for obj in self:
            model_model = self.env[obj.model_id.model]
            method = obj.etype
            if getattr(model_model, 'oe_event_%s' % method) and hasattr(getattr(model_model, method), 'origin'):
                model_model._revert_method(method)
                delattr(type(model_model), 'oe_event_%s' % method)
                updated = True
        if updated:
            modules.registry.Registry(self.env.cr.dbname).signal_changes()

    @api.multi
    def subscribe(self):
        self.write({'enable': True})
        return True

    @api.multi
    def unsubscribe(self):
        self._revert_methods()
        for obj in self:
            pass
        self.write({'enable': False})
        return True

class EventSubscribe(models.Model):

    _name = 'oe.event.subscribe'
    _description = u'事件订阅'

    event_id = fields.Many2one('oe.event', string='事件', required=True)
    domain = fields.Char(string='执行条件')
    action_server_id = fields.Many2one('ir.actions.server', '执行动作')
    enable = fields.Boolean('启用', default=False)

class EventLog(models.Model):

    _name = 'oe.event.log'
    _description = u'事件记录'

    subscribe_id = fields.Many2one('oe.event.subscribe', string='所属订阅', required=True)
    res_model = fields.Char(u'记录模型')
    res_id = fields.Integer(u'记录ID')
    old_vals = fields.Text(u'旧值')
    new_vals = fields.Text(u'新值')
    etype = fields.Selection([('create', '创建'), ('write',u'更新'),('unlink',u'删除')], string=u'事件类型', required=True)

    def get_res(self):
        obj = self.env[self.res_model].browse(self.res_id)
        return obj

    def get_old(self):
        return json.loads(self.old_vals)

    def get_new(self):
        return json.loads(self.new_vals)
