#!/usr/bin/env python
# coding: utf-8

from ceilometer import *

import unittest

class TestEnvironment(unittest.TestCase):

    def setUp(self):
        super(TestEnvironment, self).setUp()
        self.env = {"A": "A", "B": "B"}
        self.defaults = {"A": "1", "B": "2", "C": "3"}
        self.environment = Environment(defaults=self.defaults, **self.env)

    def test_env(self):
        self.assertEqual("A", self.environment["A"])

    def test_defaults(self):
        self.assertEqual("3", self.environment["C"])

    def test_missing(self):
        self.assertRaises(KeyError, self.environment.__getitem__, "D")

if __name__ == "__main__":
    unittest.main()        
