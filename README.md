# task_queue
Odoo async task module with celery

# 安装
- pip install celery==4.1.0
- pip install sqlalchemy (如果需要存储任务执行结果的话)
- pip install redis (如果使用redis作为消息存储后端)

# 配置
在 odoo 的 conf 配置文件中可用的配置项:
```shell
# 消息存储后端
celery_broker_url = redis://localhost

# 是否存储任务执行结果
celery_result_backend_db = postgresql://openerp:openerp@localhost/srm_sunwoda_180108

# 默认的队列
celery_default_queue = odoo

# 可选队列
celery_queues = queue1, queue2, queue3
```

# 使用
```python
from odoo.addons.task_queue.api import Async

@Aysnc()
@api.model
def func(self, a, b):
  pass
  
@Aysnc(queue='queue1')
@api.multi
def func1(self, a, b):
  pass
  
@Aysnc(queue='queue2')
@api.one
def func2(self, a, b):
  pass
```
注意：确保方法的参数均为可序列化的python内置类型

# Worker的运行
参考如下task_worker.py 代码：
```python
# coding=utf-8

__import__('pkg_resources').declare_namespace('odoo.addons')


import odoo
from odoo.cli.shell import Shell


args = ['-c', 'xxx.conf']
Shell().init(args)

from odoo.addons.task_queue.tasks import *
```
启动: `celery -A task_worker worker --loglevel=info`
