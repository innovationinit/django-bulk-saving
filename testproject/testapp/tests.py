
from itertools import cycle
from threading import Thread
import queue

from django.test import TestCase

from bulk_saving.models import BulkSavableModel
from testapp.models import (
    Bulky,
    Foreign
)


class BulkSavableModelTestCase(TestCase):

    def test_bulk_create_and_update(self):
        foreign1 = Foreign.objects.create(name='John')
        foreign2 = Foreign.objects.create(name='Steve')
        foreigns = cycle([foreign1, foreign2])

        bulky_count = 1000
        bulk_chunk_size = 100

        with self.assertNumQueries(bulky_count / bulk_chunk_size):
            with Bulky.bulk_saving(chunk_size=bulk_chunk_size):
                for _ in range(bulky_count):
                    Bulky(field='a', foreign=next(foreigns)).save_later()
        bulkies = list(Bulky.objects.all())
        self.assertEqual(len(bulkies), bulky_count)

        with self.assertNumQueries(bulky_count / bulk_chunk_size):
            with Bulky.bulk_saving(chunk_size=bulk_chunk_size):
                for bulky in bulkies:
                    bulky.field = 'b'
                    bulky.save_later(update_fields=['field'])
        self.assertEqual(Bulky.objects.count(), bulky_count)  # no new bulkies should be created
        self.assertEqual(Bulky.objects.filter(field='b').count(), bulky_count)  # all bulkies should be updated

    def test_bulk_updating_foreign_key(self):
        foreign1 = Foreign.objects.create(name='John')
        foreign2 = Foreign.objects.create(name='Steve')

        bulky_count = 10
        with Bulky.bulk_saving():
            for _ in range(bulky_count):
                Bulky(field='a', foreign=foreign1).save_later()

        bulkies = Bulky.objects.all()
        with Bulky.bulk_saving():
            for bulky in bulkies:
                bulky.foreign = foreign2
                bulky.save_later()
        self.assertEqual(Bulky.objects.filter(foreign=foreign2).count(), bulky_count)  # all bulkies should be updated

    def test_updating_foreign_key_to_none(self):
        foreign = Foreign.objects.create(name='John')
        bulky = Bulky.objects.create(field='a', foreign=foreign)
        with Bulky.bulk_saving():
            bulky.foreign = None
            bulky.save_later()
        self.assertEqual(Bulky.objects.get(pk=bulky.pk).foreign, None)

    def test_thread_local(self):
        q = queue.Queue()

        def test_thread():
            instance = BulkSavableModel()
            q.put(hasattr(instance.bulk_save, 'enabled'))

        thread = Thread(target=test_thread)
        thread.start()

        self.assertTrue(q.get())

        thread = Thread(target=test_thread)
        thread.start()

        self.assertTrue(q.get())
