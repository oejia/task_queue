# -*- coding: utf-8 -*-

from hashlib import sha1
from inspect import getargspec
from odoo.tools import config
import logging
from .tasks import execute

_logger = logging.getLogger('Celery Queue')
celery_default_queue = config.get('celery_default_queue', 'odoo10')

enqueue_fail_then_exec = False

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
                    print exc
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


class Async(object):

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
            _logger.info('>>>> call %s %s'%(str(args), str(kwargs)))
            if len(args) == 1 or args[-1] != token:
                # 加入任务队列
                args += (token,) # 普通参数尾部增加一个标志参数
                osv_object = args[0]._name # 第一个参数为 self
                argspecargs = tuple(getargspec(f).args) + (None,) * 4
                arglist = list(args)

                obj_ids = None
                if argspecargs[1] not in ('cr', 'cursor') and \
                        hasattr(f, '_api'):
                    # 当为新API时
                    cr, uid, context = args[0].env.cr, args[0].env.uid, \
                        dict(args[0].env.context)
                    obj = arglist.pop(0)
                    try:
                        api_name = f._api.__name__
                    except:
                        api_name = f._api
                    if api_name == 'multi':
                        obj_ids = obj.ids
                    elif api_name == 'one':
                        obj_ids = [obj.id]
                    #kwargs['context'] = context
                    #dbname = cr.dbname
                else:
                    # 当为老API时
                    cr, uid, context = args[0].env.cr, args[0].env.uid, \
                        dict(args[0].env.context)
                    #arglist.pop(0)  # Remove self
                    #cr = arglist.pop(0)
                    #uid = arglist.pop(0)
                kwargs['context'] = context

                dbname = cr.dbname
                fname = f.__name__
                # Pass OpenERP server config to the worker
                conf_attrs = dict(
                    [(attr, value) for attr, value in config.options.items()]
                )
                # 拼接任务参数
                task_args = (conf_attrs, dbname, uid, osv_object, fname)
                #if obj_ids:
                task_args += (obj_ids,)
                if arglist:
                    task_args += tuple(arglist)

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
                    # 入队失败时
                    import traceback;traceback.print_exc()
                    if enqueue_fail_then_exec:
                        kwargs.pop('context')
                        if args[-1] == token:
                            args = args[:-1]
                        _logger.error(
                            'Celery enqueue task failed %s.%s '
                            'executing task now '
                            'Exception: %s' % (osv_object, fname, exc))
                        return f(*args, **kwargs)
                    else:
                        raise exc
            else:
                # 工作进程时直接执行
                args = args[:-1]
                return f(*args, **kwargs)
        return f_job
