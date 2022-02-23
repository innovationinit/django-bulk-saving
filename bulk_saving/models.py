import threading
from collections import defaultdict
from contextlib import contextmanager

from django.db import connection, models
from django.db.models import (
    Case,
    Func,
    Value,
    When,
)


class ThreadLocal(threading.local):
    def __init__(self, enabled, registry, chunk_size):
        """
        :param registry: list of 2-tuples containing instance and its save kwargs
        """
        super(ThreadLocal, self).__init__()
        self.enabled = enabled
        self.registry = registry
        self.chunk_size = chunk_size


class Cast(Func):
    """A custom transform for calling the CAST database function."""
    template = '%(function)s((%(expressions)s) AS %(result_type)s)'
    function = 'CAST'


class BulkSavableModel(models.Model):
    bulk_save = ThreadLocal(enabled=False, registry=None, chunk_size=None)

    class Meta:
        abstract = True

    def save_later(self, update_fields=None, fallback_to_now=False):
        """
        Register the current instance in the bulk save registry.
        If fallback_to_now is set to True and a save_later is called outside a bulk_saving context, an ordinary save
        method will be called.
        """
        save_kwargs = {}  # save kwargs values have to be hashable in order to be used as groupers for objects
        if update_fields is not None:
            save_kwargs['update_fields'] = frozenset(update_fields)  # the order of update fields is irrelevant

        if self.bulk_save.enabled:
            if not self.pk and save_kwargs:
                raise RuntimeError('Bulk commit does not support save kwargs for creation.')
            self.__class__.bulk_save.registry.append((self, save_kwargs))
        else:
            if fallback_to_now:
                self.save(**save_kwargs)
            else:
                raise Exception('Not in bulk saving mode')

    @classmethod
    @contextmanager
    def bulk_saving(cls, chunk_size=100):
        if cls.bulk_save.enabled:
            yield  # already in bulk saving mode, committing changes handled in an outer scope
        else:
            cls.bulk_save = ThreadLocal(enabled=False, registry=None, chunk_size=None)
            cls.bulk_save.registry = []
            cls.bulk_save.enabled = True
            cls.bulk_save.chunk_size = chunk_size
            try:
                yield
            finally:
                cls.bulk_commit()
                cls.bulk_save.enabled = False
                cls.bulk_save.chunk_size = None

    @classmethod
    def bulk_commit(cls):
        if not cls.bulk_save.registry:
            return
        new_objects = list(filter(lambda instance_tuple: not instance_tuple[0].pk, cls.bulk_save.registry))
        existing_objects = list(filter(lambda instance_tuple: instance_tuple[0].pk, cls.bulk_save.registry))
        if new_objects:
            cls.process_new_objects(new_objects)
        if existing_objects:
            cls.bulk_update(existing_objects)
        cls.bulk_save.registry = None

    @classmethod
    def process_new_objects(cls, new_objects):
        cls.objects.bulk_create(
            [instance for instance, save_kwargs in new_objects], batch_size=cls.bulk_save.chunk_size)

    @classmethod
    def bulk_update(cls, object_tuples):
        # instances are saved in groups, each group having common save method kwargs
        objects_by_save_kwargs = defaultdict(list)
        for instance, save_kwargs in object_tuples:
            objects_by_save_kwargs[frozenset(save_kwargs.items())].append(instance)

        for save_kwargs, objects in objects_by_save_kwargs.items():
            # for each group prepare db fields to be updated
            update_fields = dict(save_kwargs).get('update_fields') or \
                [field.name for field in cls._meta.fields if not isinstance(field, models.AutoField)]
            get_db_field = lambda field: cls._meta.get_field(field).attname
            update_db_fields = [get_db_field(field) for field in update_fields]
            db_field_types = {
                get_db_field(field): cls._meta.get_field(field).db_type(connection).split('(')[0]
                for field in update_fields
            }

            # perform one update for all instances using hackish case when values
            for object_chunk in cls._make_chunks(objects):
                cls.objects.filter(pk__in=[instance.pk for instance in object_chunk]).update(**{
                    field: Cast(Case(*[
                        When(pk=instance.pk, then=Value(getattr(instance, field))) for instance in object_chunk
                    ]), result_type=db_field_types[field])
                    for field in update_db_fields
                })

    @classmethod
    def _make_chunks(cls, sequence):
        for begin in range(0, len(sequence), cls.bulk_save.chunk_size):
            yield sequence[begin:begin + cls.bulk_save.chunk_size]
