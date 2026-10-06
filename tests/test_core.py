"""Unit tests for hashmap.core."""

import random
import unittest

from hashmap.core import EMPTY, MIN_CAPACITY, TOMBSTONE, HashMap, hash_key


class HashMapTest(unittest.TestCase):
    """Behaviour and structural invariants of the open addressing table."""

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def payload(key):
        return "v:%s" % (key,)

    def build(self, keys):
        table = HashMap()
        for key in keys:
            table.put(key, self.payload(key))
        return table

    def live_entries(self, table):
        """The (key, value) pairs sitting in the slots, in slot order."""
        return [entry for entry in table.slots if isinstance(entry, tuple)]

    def occupied_slots(self, table):
        """The slots that are neither empty nor a tombstone."""
        return [entry for entry in table.slots if entry is not None]

    def colliding_keys(self, table, count):
        """Pick `count` distinct keys that share one home slot."""
        buckets = {}
        key = 0
        while True:
            bucket = buckets.setdefault(hash_key(key) % table.capacity, [])
            bucket.append(key)
            if len(bucket) == count:
                return bucket
            key += 1

    def check_table(self, table, expected):
        """Every expected key is reachable, counted once, and the table stays sparse."""
        live = self.live_entries(table)
        self.assertEqual(len(table.slots), table.capacity, "slots must cover the whole table")
        self.assertEqual(len(dict(live)), len(live), "a live key must not be stored twice")
        self.assertEqual(set(dict(live)), set(expected), "the live slots must hold every stored key")
        self.assertEqual(dict(live), dict(expected), "every live slot must hold the last value written")
        self.assertEqual(len(table), len(expected), "len(table) must equal the number of stored keys")
        self.assertEqual(table.used, len(self.occupied_slots(table)), "used must count every non-empty slot")
        self.assertLessEqual(table.used * 2, table.capacity, "at least half of the table must stay free")
        self.assertEqual(table.capacity % 2, 1, "capacity must stay odd")
        for key, value in expected.items():
            self.assertEqual(table.get(key), value)
            self.assertIn(key, table)
        self.assertEqual(sorted(table.keys(), key=repr), sorted(expected, key=repr))

    # ------------------------------------------------------------------
    # cases
    # ------------------------------------------------------------------
    def test_01_empty_table_and_rejected_keys(self):
        table = HashMap()
        self.assertEqual(table.capacity, MIN_CAPACITY)
        self.assertEqual(len(table), 0)
        self.assertEqual(table.used, 0)
        self.assertEqual(table.slots, [EMPTY] * MIN_CAPACITY)
        self.assertIsNone(table.get("missing"))
        self.assertEqual(table.get("missing", "fallback"), "fallback")
        self.assertNotIn("missing", table)
        self.assertFalse(table.delete("missing"))
        self.assertEqual(list(table), [])
        self.assertEqual(table.keys(), [])
        self.assertEqual(table.values(), [])
        self.assertEqual(table.items(), [])
        for bad in (2.5, None, True, (1, 2), b"k"):
            with self.assertRaises(TypeError):
                table.put(bad, 1)
            with self.assertRaises(TypeError):
                table.get(bad)
            with self.assertRaises(TypeError):
                table.delete(bad)
            with self.assertRaises(TypeError):
                bad in table
        with self.assertRaises(ValueError):
            HashMap(capacity=0)
        with self.assertRaises(TypeError):
            HashMap(capacity="8")
        small = HashMap(capacity=5)
        small.put(3, "three")
        self.assertEqual(small.capacity, 5)
        self.assertEqual(len(small), 1)
        self.assertEqual(small.get(3), "three")
        self.assertIsNone(small.get(4))

    def test_02_put_and_get_mixed_keys(self):
        keys = list(range(0, 60)) + ["key-%d" % index for index in range(20)]
        table = HashMap()
        for key in keys:
            table.put(key, self.payload(key))
        self.assertEqual(len(table), len(keys))
        for key in keys:
            self.assertEqual(table.get(key), self.payload(key))
            self.assertIn(key, table)
        self.assertIsNone(table.get("absent"))
        self.assertNotIn("absent", table)
        table.put("none-valued", None)
        self.assertIn("none-valued", table)
        self.assertIsNone(table.get("none-valued"))
        self.assertEqual(len(table), len(keys) + 1)
        expected = {key: self.payload(key) for key in keys}
        expected["none-valued"] = None
        self.check_table(table, expected)

    def test_03_repeated_put_overwrites_the_value(self):
        keys = [5, 12, 5, 27, 5, 12, 31, 27, 5, 40]
        table = HashMap()
        for round_index in range(4):
            for key in keys:
                table.put(key, "round%d:%d" % (round_index, key))
        distinct = sorted(set(keys))
        self.assertEqual(len(table), len(distinct))
        for key in distinct:
            self.assertEqual(table.get(key), "round3:%d" % key)
        self.check_table(table, {key: "round3:%d" % key for key in distinct})

    def test_04_delete_keeps_the_following_keys_reachable(self):
        table = HashMap()
        chain = self.colliding_keys(table, 4)
        for key in chain:
            table.put(key, self.payload(key))
        self.check_table(table, {key: self.payload(key) for key in chain})
        self.assertTrue(table.delete(chain[1]), "delete of a stored key must report success")
        self.assertEqual(len(table), 3)
        for key in (chain[2], chain[3]):
            self.assertIn(key, table)
            self.assertEqual(table.get(key), self.payload(key))
        self.assertNotIn(chain[1], table)
        self.assertIsNone(table.get(chain[1]))
        self.assertFalse(table.delete(chain[1]))
        table.put(chain[1], self.payload(chain[1]))
        self.check_table(table, {key: self.payload(key) for key in chain})

    def test_05_delete_then_reinsert_keeps_len_and_values(self):
        keys = list(range(1, 46))
        table = self.build(keys)
        self.assertEqual(len(table), len(keys))
        victims = [key for key in keys if key % 3 == 0]
        for key in victims:
            self.assertTrue(table.delete(key), "delete of a stored key must report success")
        self.assertEqual(len(table), len(keys) - len(victims))
        for key in victims:
            table.put(key, "again:%d" % key)
        self.assertEqual(len(table), len(keys), "len must count the keys written back")
        expected = {}
        for key in keys:
            expected[key] = "again:%d" % key if key in set(victims) else self.payload(key)
        self.check_table(table, expected)

    def test_06_iteration_follows_the_slot_order(self):
        keys = list(range(0, 90, 3))
        table = self.build(keys)
        live = self.live_entries(table)
        self.assertEqual(list(table), live, "iteration must visit the slots in order")
        self.assertEqual(table.items(), live)
        self.assertEqual(table.keys(), [key for key, _ in live])
        self.assertEqual(table.values(), [value for _, value in live])
        self.assertEqual(len(list(table)), len(table))
        for key in keys:
            self.assertIn((key, self.payload(key)), live)

    def test_07_growth_keeps_half_the_table_free(self):
        table = HashMap()
        keys = list(range(200))
        for key in keys:
            table.put(key, self.payload(key))
            self.assertLessEqual(table.used * 2, table.capacity)
        self.assertEqual(len(table), len(keys))
        self.assertGreater(table.capacity, MIN_CAPACITY)
        self.assertEqual(table.capacity % 2, 1)
        for key in keys:
            self.assertEqual(table.get(key), self.payload(key))
        self.check_table(table, {key: self.payload(key) for key in keys})

    def test_08_mixed_workload_stays_consistent(self):
        keys = list(range(1, 121))
        random.Random(20241006).shuffle(keys)
        table = self.build(keys)
        self.check_table(table, {key: self.payload(key) for key in keys})
        order = list(range(1, 121))
        random.Random(99).shuffle(order)
        for key in order[:60]:
            self.assertTrue(table.delete(key), "delete of a stored key must report success")
        survivors = sorted(set(range(1, 121)) - set(order[:60]))
        self.check_table(table, {key: self.payload(key) for key in survivors})
        for key in order[60:]:
            self.assertTrue(table.delete(key), "delete of a stored key must report success")
        self.assertEqual(len(table), 0)
        self.assertEqual(list(table), [])
        fresh = list(range(1000, 1060))
        for key in fresh:
            table.put(key, self.payload(key))
        self.check_table(table, {key: self.payload(key) for key in fresh})

    def test_09_slots_and_lookups_stay_in_agreement(self):
        table = self.build([2 * key for key in range(60)])
        removed = list(range(0, 120, 4))
        for key in removed:
            self.assertTrue(table.delete(key), "delete of a stored key must report success")
        live = self.live_entries(table)
        self.assertEqual(len(table), len(live))
        self.assertEqual(len(dict(live)), len(live))
        self.assertEqual(table.used, len(self.occupied_slots(table)))
        self.assertLessEqual(table.used * 2, table.capacity)
        self.assertEqual(len(table.slots), table.capacity)
        for entry in table.slots:
            if entry is not None:
                self.assertTrue(entry is TOMBSTONE or isinstance(entry, tuple))
        self.assertEqual(sorted(table.keys()), sorted(key for key, _ in live))
        for key, value in live:
            self.assertEqual(table.get(key), value)
            self.assertIn(key, table)
        for key in removed:
            self.assertNotIn(key, table)
            self.assertIsNone(table.get(key))


if __name__ == "__main__":
    unittest.main()
