# task_queue
Odoo async task with db store or celery

# 基于Odoo db的使用
1. 安装此模块 task_queue
2. 将需要异步执行的方法加上装饰器
```python
from odoo.addons.task_queue.api import AysncDB

@AysncDB()
@api.model
def func(self, a, b):
    pass
    
@AysncDB()
@api.multi
def func1(self, a, b):
    pass
    
@AysncDB()
@api.one
def func2(self, a, b):
    pass

@AsyncDB(countdown=10*60)
@api.model
def test_countdown(self):
    # 将延迟10分钟执行
    _logger.info('>>> It is time to do')
```
任务的执行默认在odoo的cron中，不需要额外的运行

# 基于celery的使用
详见 http://oejia.net/blog/2022/02/02/task_queue_use.html
