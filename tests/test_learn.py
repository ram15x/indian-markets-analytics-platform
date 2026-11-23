"""The Learn layer must cover every measure the engines can return, and must not give advice."""
import re
from imap.answer import LABEL
from imap import learn


def test_every_measure_has_formula_and_reading():
    assert set(LABEL) <= set(learn.FORMULA) and set(LABEL) <= set(learn.READING)


def test_topics_are_well_formed_and_not_advice():
    ids = [t["id"] for t in learn.TOPICS]; assert len(ids) == len(set(ids))
    assert {t["level"] for t in learn.TOPICS} <= {"new", "mid", "expert"}
    text = " ".join(t["text"] for t in learn.TOPICS) + " ".join(learn.READING.values())
    assert not re.search(r"\byou should (buy|sell|invest)|\bwe recommend|\bbest fund\b", text, re.I)


def test_starters_are_questions_the_offline_planner_accepts():
    from imap.planners import RulePlanner
    for qs in learn.STARTERS.values():
        for q in qs:
            RulePlanner().plan(q)   # must not raise
