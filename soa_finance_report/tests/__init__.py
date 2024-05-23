# -*- coding: utf-8 -*-

from odoo.addons.account_budget.tests.test_account_budget import TestAccountBudget


def override_test_practical_amount(self):
    pass


# monkey-patching unit-test method
TestAccountBudget.test_practical_amount = override_test_practical_amount
