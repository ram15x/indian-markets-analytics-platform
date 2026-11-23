import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import pytest
from imap import explain_experimental as X
from imap import explain as G
from imap import execute
from imap.planners import RulePlanner
from imap.app import App


class Fixed:
    def __init__(self, text): self.text = text
    def write(self, q, metrics, compare): return self.text


@pytest.fixture(scope="module")
def two():
    a = App(RulePlanner()); q = "Compare 5 year cagr of parag parikh flexi cap vs hdfc flexi cap"
    return q, execute.run(a.planner.plan(q), a.resolver, a.engine, q), a.resolver.amc_words


GOOD = ("CAGR is the steady yearly rate that would carry an investment from its starting value to its ending value. "
        "Real years go up and down; CAGR smooths them into one average, so it says nothing about how bumpy the ride was.")


def test_good_text_is_used(two):
    q, o, amc = two; r = X.explain(q, o, Fixed(GOOD), amc)
    assert r["explained"] and GOOD in r["text"] and "122639" in r["text"] and "not advice" in r["text"]


@pytest.mark.parametrize("bad,why", [
    (GOOD + " Over three years that came to 17.86%.", "digit"),
    (GOOD + " A typical figure is ten percent.", "unit"),
    (GOOD + " HDFC tends to be steady.", "fund house"),
    (GOOD + " You should look for a steady CAGR.", "advice"),
    (GOOD + " This will likely continue.", "advice"),
    (GOOD + " The first fund grew faster.", "particular funds"),
    (GOOD + " Both funds rose over the period.", "particular funds"),
    (GOOD + " This fund had a smooth ride.", "particular funds"),
    ("CAGR of {f1.value}.", "placeholders"),
    ("", "empty"),
])
def test_bad_text_replaced_by_glossary(two, bad, why):
    q, o, amc = two; r = X.explain(q, o, Fixed(bad), amc)
    assert not r["explained"] and why in r["reason"], r["reason"]
    assert "standard glossary" in r["text"] and X.GLOSSARY["cagr"] in r["text"] and "not advice" in r["text"]


def test_no_key_shows_glossary(two):
    q, o, amc = two; r = X.explain(q, o, None, amc)
    assert not r["explained"] and "standard glossary" in r["text"]


def test_clarify_is_not_explained():
    a = App(RulePlanner()); q = "3 year return of gold fund"; o = execute.run(a.planner.plan(q), a.resolver, a.engine, q)
    r = X.explain(q, o, Fixed(GOOD)); assert not r["explained"] and r["text"].startswith("I could not pin down")


def test_glossary_covers_every_metric():
    from imap.plan import METRICS
    assert set(METRICS) <= set(G.GLOSSARY)


def test_app_answer_ends_with_glossary():
    a = App(RulePlanner()); txt, _ = a.ask("What is the 3 year CAGR of sbi small cap?")
    assert "10,000" in txt and "glossary v" in txt and G.GLOSSARY["cagr"] in txt


def test_glossary_has_no_digits_outside_the_252_convention():
    import re
    for m, text in G.GLOSSARY.items():
        assert not re.search(r"\d", text.replace("252", "")), m
