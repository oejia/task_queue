# -*- coding: utf-8 -*-

import json
import datetime
from hashlib import sha1
from inspect import getargspec
from odoo.tools import config
import logging

_logger = logging.getLogger(__name__)
celery_default_queue = config.get('celery_default_queue', 'odoo')

enqueue_fail_then_exec = False

class DateEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj,datetime.datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(obj, datetime.date):
            return obj.strftime("%Y-%m-%d")
        else:
            try:
                return json.JSONEncoder.default(self,obj)
            except:
                import traceback;traceback.print_exc()
                return str(obj)

class _CeleryTask(object):

    def __init__(self, *args, **kwargs):
        self.countdown = 0
        self.eta = None
        self.expires = None
        self.priority = 5
        self.queue = celery_default_queue
        for arg, value in kwargs.items():
            setattr(self, arg, value)

    def __call__(self, f, *args, **kwargs):
        token = sha1(f.__name__).hexdigest()

        def f_job(*args, **kwargs):
            _logger.info(str(args))
            if len(args) == 1 or args[-1] != token:
                args += (token,)
                osv_object = args[0]._name
                arglist = list(args)
                arglist.pop(0)  # Remove self
                cr = arglist.pop(0)
                uid = arglist.pop(0)
                dbname = cr.dbname
                fname = f.__name__
                # Pass OpenERP server config to the worker
                conf_attrs = dict(
                    [(attr, value) for attr, value in config.options.items()]
                )
                task_args = (conf_attrs, dbname, uid, osv_object, fname)
                if arglist:
                    task_args += tuple(arglist)
                pprint(task_args)
                try:
                    celery_task = execute.apply_async(
                        args=task_args, kwargs=kwargs,
                        countdown=self.countdown, eta=self.eta,
                        expires=self.expires, priority=self.priority,
                        queue=getattr(self, "queue", celery_default_queue))

                    _logger.info('Enqueued task %s.%s(%s) on celery with id %s'
                                 % (osv_object, fname, str(args[3:]),
                                    celery_task and celery_task.id))
                    return celery_task.id
                except Exception as exc:
                    if args[-1] == token:
                        args = args[:-1]
                    _logger.error(
                        'Celery enqueue task failed %s.%s '
                        'executing task now '
                        'Exception: %s' % (osv_object, fname, exc))
                    return f(*args, **kwargs)
            else:
                args = args[:-1]
                return f(*args, **kwargs)
        return f_job


class Base(object):

    def __init__(self, *args, **kwargs):
        self.countdown = 0
        self.eta = None
        self.expires = None
        self.priority = 5
        self.queue = celery_default_queue
        for arg, value in kwargs.items():
            setattr(self, arg, value)
        self.env = None

    def __call__(self, f, *args, **kwargs):
        token = sha1(f.__name__.encode('utf-8')).hexdigest()

        def f_job(*args, **kwargs):
            _logger.info('>>>> user %s call %s.%s %s %s'%(args[0].env.uid, args[0], f.__name__, str(args[1:]), str(kwargs)))
            if len(args) == 1 or args[-1] != token:
                # 加入任务队列
                args += (token,) # 普通参数尾部增加一个标志参数
                _self = args[0]
                self.env = _self.env
                model_name = _self._name # 第一个参数为 self
                argspecargs = tuple(getargspec(f).args) + (None,) * 4
                arglist = list(args)

                obj_ids = None
                _logger.info('>>> argspecargs: %s hasattr api: %s', argspecargs, hasattr(f, '_api'))
                if argspecargs[1] not in ('cr', 'cursor'):
                    # 当为新API时
                    cr, uid, context = _self.env.cr, _self.env.uid, dict(_self.env.context)
                    obj = arglist.pop(0)
                    obj_ids = obj.ids
                else:
                    # 当为老API时
                    cr, uid, context = args[0].env.cr, args[0].env.uid, \
                        dict(args[0].env.context)
                    #arglist.pop(0)  # Remove self
                    #cr = arglist.pop(0)
                    #uid = arglist.pop(0)
                kwargs['context'] = { k: v for k,v in context.items() if not hasattr(v, '_name') }

                dbname = cr.dbname
                fname = f.__name__
                # Pass OpenERP server config to the worker
                odoo_conf_attrs = dict(
                    [(attr, value) for attr, value in config.options.items()]
                )
                # 拼接任务参数
                task_args = (odoo_conf_attrs, dbname, uid, model_name, fname)
                #if obj_ids:
                task_args += (obj_ids,)
                if arglist:
                    task_args += tuple(arglist)

                try:
                    #cr.commit()
                    task = self.gen_task(task_args, kwargs)

                    _logger.info('Enqueued task %s.%s%s on celery with id %s' % (model_name, fname, str(args[1:-1]), task and task.id))
                    return task and task.id or None
                except Exception as exc:
                    # 入队失败时
                    import traceback;traceback.print_exc()
                    if enqueue_fail_then_exec:
                        kwargs.pop('context')
                        if args[-1] == token:
                            args = args[:-1]
                        _logger.error('Enqueue task failed %s.%s executing task now Exception: %s' % (model_name, fname, exc))
                        return f(*args, **kwargs)
                    else:
                        raise exc
            else:
                # 工作进程时直接执行
                args = args[:-1]
                return f(*args, **kwargs)
        return f_job

class Async(Base):

    def gen_task(self, task_args, kwargs):
        from .tasks import execute
        task = execute.apply_async(
            args=task_args, kwargs=kwargs,
            countdown=self.countdown, eta=self.eta,
            expires=self.expires, priority=self.priority,
            queue=getattr(self, "queue", celery_default_queue))
        return task

class AsyncDB(Base):

    def gen_task(self, task_args, kwargs):
        #_logger.info('>>> gen task %s %s', task_args, kwargs)
        odoo_conf_attrs = task_args[0]
        dbname = task_args[1]
        uid = task_args[2]
        model_name = task_args[3]
        method = task_args[4]
        ids = task_args[5]
        task = self.env['oe.task'].sudo().create({
            'task_id': '',
            'task_name': '%s.%s()'%(model_name, method),
            'task_args': json.dumps(task_args[1:], cls=DateEncoder),
            'task_kwargs': json.dumps(kwargs, cls=DateEncoder),
            'countdown': self.countdown,
        })
        return task
