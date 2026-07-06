from stats import total_quantity


def test_total_quantity_all_items():
    items = [{"qty": 1}, {"qty": 2}, {"qty": 3}]
    assert total_quantity(items) == 6


def test_total_quantity_empty():
    assert total_quantity([]) == 0


def test_total_quantity_single_item():
    assert total_quantity([{"qty": 5}]) == 5
