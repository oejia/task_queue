{
    'name': 'Tase Queue',
    'depends': [
        'base', 'base_setup'
    ],
    'author': '',
    'data': [
        #'data/ir_cron_datas.xml',
        'security/ir.model.access.csv',

        'views/oe_task_views.xml',
        'views/oe_task_result_views.xml',
        #'views.xml'
    ],
    'installable': True,
    'application': False,
    'external_dependencies': {
        'python': [],
    }
}
