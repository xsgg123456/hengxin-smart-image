"""Build explicit valid tasks for existing conversation-focused regression tests."""
from app.modules.domestic_studio import task_service, conversation_service
from app.modules.domestic_studio.task_schemas import NewTask


def create(session, actor_id, workspace, body, key):
    task = task_service.create(session, actor_id, NewTask(name='回归测试任务', workspace=workspace),
                               'fixture-task-' + workspace)
    return conversation_service.create(session, actor_id, workspace, body, key, task_id=task.id)
