import copy
from pathlib import Path

import pytest

import pricing

SEED = Path(__file__).resolve().parent.parent / "site" / "data" / "prices.json"
SHEET = pricing.load_sheet_file(SEED)
AREA = "台北市（萬華、中正、大安、信義、大同、中山、松山）"


def test_seed_data_is_valid():
    assert pricing.validate_sheet(SHEET) == []


def test_quote_send_and_pickup():
    assert pricing.quote(SHEET, "tpe", "sedan", AREA, "send") == 1000
    assert pricing.quote(SHEET, "tpe", "sedan", AREA, "pickup") == 1100


@pytest.mark.parametrize("args", [
    ("zzz", "sedan", AREA, "send"),
    ("tpe", "zzz", AREA, "send"),
    ("tpe", "sedan", "不存在的地區", "send"),
    ("tpe", "sedan", AREA, "bad"),
])
def test_quote_rejects_unknown_input(args):
    with pytest.raises(pricing.PriceError):
        pricing.quote(SHEET, *args)


def mutated(fn):
    sheet = copy.deepcopy(SHEET)
    fn(sheet)
    return sheet


@pytest.mark.parametrize("fn", [
    lambda s: s["airports"][0]["groups"][0]["areas"][0]["prices"].pop("benz"),
    lambda s: s["airports"][0]["groups"][0]["areas"][0]["prices"].update(sedan=[1000]),
    lambda s: s["airports"][0]["groups"][0]["areas"][0]["prices"].update(sedan=[1000, "1100"]),
    lambda s: s["airports"][0]["groups"][0]["areas"][0]["prices"].update(sedan=[1000, True]),
    lambda s: s["airports"][0]["groups"][0]["areas"][0]["prices"].update(sedan=[0, 1100]),
    lambda s: s["airports"][0]["groups"][0]["areas"][0]["prices"].update(sedan=[-5, 1100]),
    lambda s: s["airports"][0]["groups"][0]["areas"][0]["prices"].update(sedan=[1000, 9_999_999]),
    lambda s: s["airports"][0]["groups"][0]["areas"].append(copy.deepcopy(s["airports"][0]["groups"][0]["areas"][0])),
    lambda s: s["airports"].append(copy.deepcopy(s["airports"][0])),
    lambda s: s.update(vehicles=[]),
])
def test_validate_catches_broken_sheets(fn):
    assert pricing.validate_sheet(mutated(fn)) != []


def test_apply_prices_does_not_touch_original():
    new, = [pricing.apply_prices(SHEET, "tpe", "sedan", {0: (1200, 1300)})]
    assert pricing.quote(new, "tpe", "sedan", AREA, "send") == 1200
    assert pricing.quote(SHEET, "tpe", "sedan", AREA, "send") == 1000


def test_apply_prices_rejects_bad_index_and_value():
    with pytest.raises(pricing.PriceError):
        pricing.apply_prices(SHEET, "tpe", "sedan", {9999: (1000, 1100)})
    with pytest.raises(pricing.PriceError):
        pricing.apply_prices(SHEET, "tpe", "sedan", {0: (0, 1100)})


def test_diff_changes():
    new = pricing.apply_prices(SHEET, "tpe", "sedan", {0: (1200, 1100)})
    changes = pricing.diff_changes(SHEET, new)
    assert changes == [{"airport": "桃園機場", "vehicle": "國產五人座轎車", "area": AREA,
                        "field": "送機", "old": 1000, "new": 1200}]
    assert pricing.diff_changes(SHEET, SHEET) == []


def test_soft_warnings():
    big = pricing.apply_prices(SHEET, "tpe", "sedan", {0: (10000, 10100)})
    assert any("變動超過" in w for w in pricing.soft_warnings(SHEET, big))
    inverted = pricing.apply_prices(SHEET, "tpe", "sedan", {0: (1100, 1000)})
    assert any("比送機價" in w for w in pricing.soft_warnings(SHEET, inverted))
    normal = pricing.apply_prices(SHEET, "tpe", "sedan", {0: (1100, 1200)})
    assert pricing.soft_warnings(SHEET, normal) == []


@pytest.mark.parametrize("text,expected", [("1000", 1000), (" 1,200 ", 1200), ("900", 900), ("１２００", 1200)])
def test_parse_price_ok(text, expected):
    assert pricing.parse_price(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "10.5", "-100", "0", "99999999", "１２３４５６７８９", None])
def test_parse_price_rejects(text):
    with pytest.raises(pricing.PriceError):
        pricing.parse_price(text)
