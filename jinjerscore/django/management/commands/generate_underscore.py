from django.conf import settings
from django.core.management.base import NoArgsCommand
from jinjerscore.environment import JinjerscoreEnvironment


class Command(NoArgsCommand):
    requires_model_validation = False

    def handle_noargs(self, **options):
        params = {
            'extensions': [],
            'loader': None
        }
        j_settings = settings.JINJERSCORE.copy()
        base_path = j_settings.pop('underscore_base_path')
        params.update(j_settings)
        jenv = JinjerscoreEnvironment(**params)
        jenv.underscore_base_path = base_path
        for path in jenv.list_templates():
            jenv.get_template(path).render()
