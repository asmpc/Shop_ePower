


def assert_inventory_structure(test_case, inventory):
    test_case.assertIn("own_stock", inventory)
    test_case.assertIn("supplier_stock", inventory)
    test_case.assertIn("total_available", inventory)
    test_case.assertIn("min_lead_time", inventory)
    test_case.assertIn("in_stock", inventory)