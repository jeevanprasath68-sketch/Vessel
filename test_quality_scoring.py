import pytest
from agents.reviewer_agent import ReviewerAgent

def test_quality_score_perfect_first_shot():
    app_code = '''
class Calculator:
    """A clean calculator class."""
    def add(self, a: int, b: int) -> int:
        try:
            return a + b
        except Exception:
            return 0
'''
    test_code = '''
import pytest
def test_add():
    assert Calculator().add(1, 2) == 3
def test_invalid():
    with pytest.raises(TypeError):
        Calculator().add("a", 1)
def test_edge_zero():
    assert Calculator().add(0, 0) == 0
def test_negative():
    assert Calculator().add(-1, -1) == -2
def test_bounds():
    assert Calculator().add(999999, 1) == 1000000
def test_empty():
    assert True
'''
    test_res = {
        "success": True,
        "exit_code": 0,
        "passed_tests": 6,
        "total_tests": 6,
        "failed_tests": 0
    }
    metrics = ReviewerAgent.calculate_quality_metrics(app_code, test_code, test_res, repair_history=[])
    assert metrics["score"] >= 9.5
    assert "breakdown" in metrics

def test_quality_score_with_repairs_and_simple_code():
    app_code = 'x = 1'
    test_code = 'def test_x(): assert x == 1'
    test_res = {
        "success": True,
        "exit_code": 0,
        "passed_tests": 1,
        "total_tests": 1,
        "failed_tests": 0
    }
    repairs = [{"iteration": 1}, {"iteration": 2}]
    metrics = ReviewerAgent.calculate_quality_metrics(app_code, test_code, test_res, repair_history=repairs)
    # With 2 repairs, no typing, no classes, only 1 test: score should be significantly lower than 9.5!
    assert metrics["score"] < 8.0
    assert metrics["score"] != 9.5

def test_quality_score_with_failing_tests():
    app_code = 'def fn(): pass'
    test_code = 'def test_fn(): assert False'
    test_res = {
        "success": False,
        "exit_code": 1,
        "passed_tests": 0,
        "total_tests": 3,
        "failed_tests": 3
    }
    metrics = ReviewerAgent.calculate_quality_metrics(app_code, test_code, test_res, repair_history=[])
    assert metrics["score"] <= 5.0
