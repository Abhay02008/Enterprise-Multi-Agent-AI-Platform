"""A2A-to-MCP execution bridge for the HR and Business agent."""

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, Task, TaskState, TaskStatus

from backend.agents.hr_business.mcp_agent import HRBusinessMCPAgent


class HRBusinessAgentExecutor(AgentExecutor):
    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        if not context.message or not context.task_id or not context.context_id:
            raise ValueError("A2A request is missing message, task, or context data.")

        task = context.current_task
        if not task:
            task = Task(
                id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                history=[context.message],
            )
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()
        agent = HRBusinessMCPAgent()
        try:
            await agent.connect()
            result = await agent.invoke(
                context.get_user_input(), task.context_id
            )
            await updater.add_artifact(
                [Part(text=result["content"])],
                name="hr_business_result",
            )
            await updater.complete()
        except Exception as exc:
            await updater.add_artifact(
                [Part(text=f"HR and business service error: {exc}")],
                name="hr_business_error",
            )
            await updater.complete()
        finally:
            await agent.close()

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        updater = TaskUpdater(
            event_queue, context.task_id or "", context.context_id or ""
        )
        await updater.cancel()
