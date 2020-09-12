from django.apps import apps
from django.core.management import BaseCommand

from puml_generator.management.commands.utils.utils import generate_puml_class_diagram


def add_bool_arg(parser, name, help_yes, help_no, default=False):
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--' + name, dest=name, help=help_yes, action='store_true')
    group.add_argument('--no-' + name, dest=name, help=help_no, action='store_false')
    parser.set_defaults(**{name: default})


class Command(BaseCommand):
    help = 'Generate PlantUML diagram of project'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='output file',
            default='models_diagram.puml',
        )
        parser.add_argument(
            '--omit',
            type=str,
            nargs='+',
            help='omit applications',
        )
        parser.add_argument(
            '--include',
            type=str,
            nargs='+',
            help='include applications',
        )
        add_bool_arg(
            parser, 'add-help',
            'docstrings should be included to diagram',
            'docstrings should not be included to diagram'
        )
        add_bool_arg(
            parser, 'add-choices',
            'models Choices fields should be described',
            'models Choices fields should not be described'
        )

    def handle(self, *args, **options):
        output = options['file']
        generate_with_help = options['add-help']
        generate_with_choices = options['add-choices']
        include = options['include']
        omit = options['omit']

        models = apps.get_models()
        uml = generate_puml_class_diagram(
            models,
            with_help=generate_with_help,
            with_choices=generate_with_choices,
            include=include,
            omit=omit,
        )

        with open(output, 'w') as file:
            file.write(uml)
