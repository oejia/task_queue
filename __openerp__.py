{
    'name': 'Tase Queue',
    'depends': [
        'base'
    ],
    'author': '',
    'data': [
        'views.xml'
    ],
    'installable': True,
    'application': False,
    'external_dependencies': {
        'python': ['celery'],
    }
}
