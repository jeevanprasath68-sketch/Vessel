class Task:
    def __init__(self, task_id: int, title: str, priority: int = 1):
        self.task_id = task_id
        self.title = title
        self.priority = priority
        self.completed = False

class TaskManager:
    def __init__(self):
        self.tasks = {}

    def add_task(self, title: str, priority: int = 1) -> Task:
        task_id = len(self.tasks) + 1
        task = Task(task_id, title, priority)
        self.tasks[task_id] = task
        return task

    def complete_task(self, task_id: int) -> bool:
        if task_id in self.tasks:
            self.tasks[task_id].completed = True
            return True
        return False

    def get_pending_tasks(self):
        # Fixed: now correctly sorts highest priority first
        pending = [t for t in self.tasks.values() if not t.completed]
        return sorted(pending, key=lambda x: x.priority, reverse=True)


# --- Streamlit Interactive User Interface ---
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

def render_ui():
    if not HAS_STREAMLIT:
        return
    st.set_page_config(page_title='Task Manager', page_icon='📋', layout='wide')
    st.title('📋 Prioritized Task Manager')
    st.caption('Organize and prioritize your daily tasks with status tracking.')

    if 'task_manager' not in st.session_state:
        st.session_state.task_manager = TaskManager()
        st.session_state.task_manager.add_task('Initial project setup', priority=3)
        st.session_state.task_manager.add_task('Review pull request', priority=5)

    tm = st.session_state.task_manager

    with st.sidebar:
        st.header('➕ Add New Task')
        with st.form('new_task_form', clear_on_submit=True):
            new_title = st.text_input('Task Title', placeholder='e.g., Fix database indexing')
            new_priority = st.slider('Priority Level', min_value=1, max_value=5, value=3, help='5 = Highest, 1 = Lowest')
            submitted = st.form_submit_button('Add Task', use_container_width=True)
            if submitted and new_title.strip():
                tm.add_task(new_title.strip(), new_priority)
                st.success('Task added successfully!')
                st.rerun()

    total = len(tm.tasks)
    pending_tasks = tm.get_pending_tasks()
    completed_count = total - len(pending_tasks)

    m1, m2, m3 = st.columns(3)
    m1.metric('Total Tasks', total)
    m2.metric('Pending Tasks', len(pending_tasks))
    m3.metric('Completed Tasks', completed_count)

    st.subheader('📌 Pending Tasks (Prioritized)')
    if not pending_tasks:
        st.info('No pending tasks! All caught up 🎉')
    else:
        for t in pending_tasks:
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f'**#{t.task_id}**: {t.title} &nbsp;*(Priority: {t.priority}/5)*')
            with c2:
                if st.button('Mark Complete', key=f'complete_{t.task_id}'):
                    tm.complete_task(t.task_id)
                    st.rerun()

if __name__ == '__main__':
    render_ui()