# -*- coding: utf-8 -*-

from celery.backends import database
from celery.backends.database import DatabaseBackend, retry, session_cleanup
from celery.backends.database.models import Task, ResultModelBase

import sqlalchemy as sa
from datetime import datetime
from sqlalchemy.types import PickleType
from celery import states
from celery.five import python_2_unicode_compatible

from odoo.tools import config

@python_2_unicode_compatible
class Task(ResultModelBase):
    """Task result/status."""

    __tablename__ = 'celery_taskmeta_ext'
    __table_args__ = {'sqlite_autoincrement': True}

    id = sa.Column(sa.Integer, sa.Sequence('task_id_sequence'),
                   primary_key=True, autoincrement=True)
    task_id = sa.Column(sa.String(155), unique=True)
    status = sa.Column(sa.String(50), default=states.PENDING)
    result = sa.Column(PickleType, nullable=True)
    date_done = sa.Column(sa.DateTime, default=datetime.utcnow,
                          onupdate=datetime.utcnow, nullable=True)
    traceback = sa.Column(sa.Text, nullable=True)

    task_name = sa.Column(sa.String(255), nullable=True)
    task_args = sa.Column(sa.Text, nullable=True)
    task_kwargs = sa.Column(sa.Text, nullable=True)

    def __init__(self, task_id):
        self.task_id = task_id

    def to_dict(self):
        return {
            'task_id': self.task_id,
            'status': self.status,
            'result': self.result,
            'traceback': self.traceback,
            'date_done': self.date_done,
        }

    def __repr__(self):
        return '<Task {0.task_id} state: {0.status}>'.format(self)

database.Task  = Task

class ExtDatabaseBackend(DatabaseBackend):

    def __init__(self, dburi=None, engine_options=None, url=None, **kwargs):
        url = config.get('celery_result_backend_db')
        super(ExtDatabaseBackend, self).__init__(dburi=dburi, engine_options=engine_options, url=url, **kwargs)

    @retry
    def _store_result(self, task_id, result, state,
                      traceback=None, max_retries=3, **kwargs):
        request = kwargs.get('request',{})
        session = self.ResultSession()
        with session_cleanup(session):
            task = list(session.query(Task).filter(Task.task_id == task_id))
            task = task and task[0]
            if not task:
                task = Task(task_id)
                session.add(task)
                session.flush()
            task.result = result
            task.status = state
            task.traceback = traceback
            task.task_name = repr(getattr(request, 'task', None))
            _args = self.get_args(getattr(request, 'args', []))
            task.task_args = repr(_args)
            task.task_kwargs = repr(getattr(request, 'kwargs', None))
            session.commit()
            return result

    def get_args(self,data):
        if len(data)>=5:
            if type(data[0])==dict:
                if 'xmlrpc_port' in data[0]:
                    return data[1:]
        return data

