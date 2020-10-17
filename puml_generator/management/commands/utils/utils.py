import colorsys
from hashlib import md5
from typing import Optional, Tuple

from django.db.models import ForeignKey, ManyToManyField
from model_utils import Choices

CHOICES_COLOR = '#EEE'
AUTO_FIELDS = {"AutoField", "AutoLastModifiedField", "AutoCreatedField"}

LEGEND = """
    class "Explanation of the symbols used" as DESCRIPTION #FFF { 
    - AutoField (identifiers)
    ..
    + Regular field (anything)
    ..
    # ForeignKey (ManyToMany)
    ..
    ~ ForeignKey (OneToOne, OneToMany)
    --
}\n\n
"""


def app_name_to_colour(name: str) -> str:
    def _h(v: float):
        return str(hex(int(v * 255)))[2:].ljust(2).replace(' ', '0')

    hue = int(md5(name.encode()).hexdigest(), 16) % 360 / 360.0
    r, g, b = colorsys.hls_to_rgb(hue, 0.90, 0.60)
    r, g, b = _h(r), _h(g), _h(b)
    return f'#{r}{g}{b}'


class PlantUml:
    uml = None

    def __init__(
            self,
            models=None,
            title=None,
            with_legend=False,
            with_help=True,
            with_choices=True,
            include=None,
            omit=None,
            with_omitted_headers=False,
            generate_headers_only=False,
    ):
        self.models = models
        self.title = title
        self.with_legend = with_legend
        self.with_help = with_help
        self.with_choices = with_choices
        self.include = include
        self.omit = omit
        self.with_omitted_headers = with_omitted_headers
        self.generate_headers_only = generate_headers_only
        self.legend = LEGEND

    @staticmethod
    def is_app_member(model, app_name: str) -> bool:
        return str(model._meta.label).startswith(app_name + '.')

    def is_allowed_related(self, related):
        if not self.omit and not self.include:
            return True
        omit = self.omit or []
        include = self.include or []
        is_omitted = any([
            self.is_app_member(self.retrieve_field_related_model(related), app_name) for app_name in omit
        ])
        is_included = any([
            self.is_app_member(self.retrieve_field_related_model(related), app_name) for app_name in include
        ])
        if include and not is_included:
            return False
        return not is_omitted

    def field_repr(self, field) -> str:
        uml = ''
        sign = '+'
        if field.__class__.__name__ in AUTO_FIELDS:
            sign = '-'
        elif field.__class__.__name__ == "ForeignKey":
            sign = '~'
        elif field.__class__.__name__ == "OneToOneField":
            sign = '~'
        elif field.__class__.__name__ == "ManyToManyField":
            sign = '#'
        uml += f'    {sign} {field.name} ({field.__class__.__name__})'
        if self.with_help:
            # TODO force 80/120 columns
            uml += f' - {field.help_text}' if field.help_text else ''
        uml += '\n'
        return uml

    @staticmethod
    def choice_repr(name, items) -> str:
        uml = ''
        if items:
            uml += f'enum "{name} <choices>" as {name} {CHOICES_COLOR}'
            uml += f'{{\n'
            for choice, description in items.items():
                uml += f'    + {choice} - {description}\n'
            uml += f'}}\n\n'
        return uml

    @staticmethod
    def collect_choices(field) -> Optional:
        if field.choices:
            choices = field.choices
            if isinstance(choices, Choices):
                return choices._display_map
            elif isinstance(choices, tuple):
                return {k: (k, v) for k, v in choices}

    def model_repr(self, model) -> Tuple[str, dict]:
        uml = ''
        meta = model._meta
        model_choices = dict()
        uml += f'class "{meta.label} <{meta.app_config.verbose_name}>" as {meta.label}'
        app, name = str(meta.label).split('.')
        app_colour = app_name_to_colour(app)
        uml += f' {app_colour} '
        uml += f'{{\n'
        uml += f'    {meta.verbose_name}\n'

        if self.with_help:
            uml += f'    ..\n'
            doc = str(model.__doc__).strip().replace("\n\n", "\n")
            uml += f'    {doc}\n'
        uml += f'    --\n'

        fields = list(meta.fields)
        fields.extend(meta.many_to_many)

        for field in fields:
            if not self.generate_headers_only:
                uml += self.field_repr(field)

            if self.with_choices:
                choices = self.collect_choices(field)
                if choices:
                    model_choices[field.name] = choices

        uml += f'    --\n'
        uml += f'}}\n'

        uml += self.model_relations_repr(meta)

        if self.with_choices:
            for choice_field_name, choices in model_choices.items():
                uml += f'{meta.label} .- {choice_field_name}\n'

        uml += f'\n\n'
        return uml, model_choices

    @staticmethod
    def retrieve_field_related_model(field) -> Optional:
        if isinstance(field, ForeignKey):
            return field.foreign_related_fields[0].model
        elif isinstance(field, ManyToManyField):
            return field.target_field.model

    def model_relations_repr(self, meta) -> str:
        uml = ''
        fields = list(meta.fields)
        fields.extend(meta.many_to_many)
        for related in list(filter(lambda x: isinstance(x, ForeignKey), fields)):
            if self.with_omitted_headers or self.is_allowed_related(related):
                uml += f'{meta.label} *-- {related.foreign_related_fields[0].model._meta.label}\n'
        for related in list(filter(lambda x: isinstance(x, ManyToManyField), fields)):
            if self.with_omitted_headers or self.is_allowed_related(related):
                uml += f'{meta.label} *--* {related.target_field.model._meta.label}\n'
        return uml

    def generate_puml_class_diagram(self) -> str:
        global_choices = dict()

        uml = "@startuml\n"

        if self.title:
            uml += f"""
            skinparam titleFontSize 72
    
            title
            {self.title}
            end title\n
            """
        if self.with_legend:
            uml += self.legend

        for model in self.models:
            if self.omit and any([self.is_app_member(model, to_omit) for to_omit in self.omit]):
                continue
            if self.include and all([not self.is_app_member(model, to_include) for to_include in self.include]):
                continue
            model_uml, model_choices = self.model_repr(model)
            uml += model_uml
            global_choices = {**global_choices, **model_choices}

        if self.with_choices:
            for key, values in global_choices.items():
                uml += self.choice_repr(key, values)

        uml += "@enduml\n"
        return uml
