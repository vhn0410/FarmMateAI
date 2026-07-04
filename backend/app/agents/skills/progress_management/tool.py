import json

from app.agents.skills.base import BaseSkill, SkillResult
from app.infrastructure.api.ppm_client import PPMClient


class ProgressManagementSkill(BaseSkill):
    name = "Get_Current_Growth_Stage"
    description = (
        "Get current growth stage / active tasks for the farm. "
        "The 'status' parameter defaults to 'ALL', but can be 'OPEN', 'IN_PROGRESS', 'DONE', or 'ALL' (or a combination separated by commas). "
        "The 'project_name' parameter is optional. If the user asks for a specific project, provide its exact name here to filter the results natively."
    )

    def __init__(self):
        """Initialize the Progress Management Tool."""
        pass

    def run(self, query: str, **kwargs) -> SkillResult:
        """
        Execute growth stage data retrieval.
        'query' can be used as status or handled explicitly through kwargs.
        We expect 'token', 'status', and 'project_name' in kwargs.
        """
        token = kwargs.get("token")
        status = kwargs.get("status", "ALL")
        project_name = kwargs.get("project_name")
        
        agent_actions = [f"Started fetching growth stage data (status: {status}, project: {project_name or 'ALL'})..."]

        if not token:
            error_msg = "Error: No access token. Please log in again."
            agent_actions.append(error_msg)
            return SkillResult(
                answer=error_msg,
                skill_name=self.name,
                metadata={},
                agent_actions=agent_actions,
            )

        try:
            ppm_client = PPMClient()

            # Parse comma-separated statuses
            status_list = [s.strip().upper() for s in status.split(",") if s.strip()]

            if "ALL" in status_list:
                status_list = ["OPEN", "IN_PROGRESS", "DONE"]

            if not status_list:
                status_list = ["IN_PROGRESS"]

            active_tasks = ppm_client.get_tasks_by_statuses(token, statuses=status_list)

            status_str = ", ".join(status_list)
            if not active_tasks:
                answer = f"There are currently no tasks with status ({status_str}) for your projects."
                agent_actions.append(answer)
                return SkillResult(answer=answer, skill_name=self.name, metadata={}, agent_actions=agent_actions)

            if project_name:
                active_tasks = [
                    t for t in active_tasks 
                    if project_name.lower() in t.get("projectName", "").lower()
                ]
                if not active_tasks:
                    answer = f"There are currently no tasks matching project '{project_name}' with status ({status_str})."
                    agent_actions.append(answer)
                    return SkillResult(answer=answer, skill_name=self.name, metadata={}, agent_actions=agent_actions)

            # Remove templates (projects where all tasks lack startDate and startDateActual)
            project_has_dates = {}
            for t in active_tasks:
                pid = t.get("projectId")
                if t.get("startDateActual") or t.get("startDate"):
                    project_has_dates[pid] = True

            # Filter out tasks belonging to templates
            active_tasks = [t for t in active_tasks if project_has_dates.get(t.get("projectId"))]

            # Sort tasks by project name, then by index
            active_tasks.sort(
                key=lambda t: (t.get("projectName", "").strip().lower(), t.get("index", 9999))
            )

            # Identify Current Task and Next Task for each project
            project_stages = {}
            for t in active_tasks:
                proj = t.get("projectName", "Unnamed Project").replace('\n', ' ').strip()
                if proj not in project_stages:
                    project_stages[proj] = {"current": None, "next": None, "open_tasks": []}

                status_val = t.get("status", "UNKNOWN")
                task_name = t.get("name", "Unknown").replace('\n', ' ').strip()

                if status_val == "IN_PROGRESS":
                    project_stages[proj]["current"] = task_name
                elif status_val == "OPEN":
                    project_stages[proj]["open_tasks"].append(task_name)

            summary_header = "**Current Growth Stage:**\n"
            for proj, data in project_stages.items():
                current = data["current"]
                if not current and data["open_tasks"]:
                    # If no IN_PROGRESS task, use the first OPEN task as current
                    current = data["open_tasks"][0]
                    next_task = data["open_tasks"][1] if len(data["open_tasks"]) > 1 else "None"
                else:
                    next_task = data["open_tasks"][0] if data["open_tasks"] else "None"

                summary_header += f"- Project '{proj}': Currently executing [{current or 'None'}]. Next: [{next_task}].\n"

            summary_header += "\n**Detailed Task List:**\n"

            result_list = ["| Task Name | Project Name | Status | Start Date |", "|---|---|---|---|"]

            # Initialize status counters for chart rendering
            status_counts = {"OPEN": 0, "IN_PROGRESS": 0, "DONE": 0}

            for t in active_tasks:
                task_name = t.get("name", "Unknown").replace('\n', ' ').strip()
                proj_name = t.get("projectName", "Unnamed Project").replace('\n', ' ').strip()
                start_date = t.get("startDateActual", t.get("startDate", ""))
                status_val = t.get("status", "UNKNOWN")

                # Increment counters
                if status_val in status_counts:
                    status_counts[status_val] += 1
                else:
                    status_counts[status_val] = 1

                if start_date:
                    try:
                        start_date = start_date.split('T')[0]
                    except:
                        pass
                else:
                    start_date = "None"

                result_list.append(f"| {task_name} | {proj_name} | {status_val} | {start_date} |")

            final_output = summary_header + "\n".join(result_list)

            # Add precise statistics for LLM to render charts correctly
            summary = "\n\n**Task Status Statistics (Use these numbers to draw charts):**\n"
            for k, v in status_counts.items():
                if v > 0:
                    summary += f"- {k}: {v}\n"

            answer = final_output + summary
            agent_actions.append(f"Success: Retrieved {len(active_tasks)} tasks.")

            return SkillResult(
                answer=answer,
                skill_name=self.name,
                metadata={"total_tasks": len(active_tasks), "status_counts": status_counts},
                agent_actions=agent_actions,
            )

        except Exception as e:
            error_msg = f"System error while fetching growth stage data: {str(e)}"
            agent_actions.append(error_msg)
            return SkillResult(
                answer=error_msg,
                skill_name=self.name,
                metadata={},
                agent_actions=agent_actions,
            )
