import pytest
from app import TaskManager

def test_add_task():
    tm = TaskManager()
    task = tm.add_task('Write tests', priority=2)
    assert task.task_id == 1
    assert task.title == 'Write tests'
    assert not task.completed

def test_complete_task():
    tm = TaskManager()
    task = tm.add_task('Fix bug')
    assert tm.complete_task(task.task_id) is True
    assert tm.complete_task(999) is False

def test_pending_tasks_priority():
    tm = TaskManager()
    tm.add_task('Low', priority=1)
    tm.add_task('High', priority=5)
    tm.add_task('Medium', priority=3)
    pending = tm.get_pending_tasks()
    # Test expects highest priority first (5, 3, 1)
    priorities = [t.priority for t in pending]
    assert priorities == [5, 3, 1]