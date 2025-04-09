from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from pathlib import Path
import yaml
import json

@CrewBase
class Vgen():
    """Vgen crew with dynamic Verilog tasks"""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def planner(self) -> Agent:
        return Agent(
            config=self.agents_config['planner'],
            verbose=True,
            human_input=False,
        )

    @agent
    def verilog_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['verilog_agent'],
            verbose=True,
            human_input=False,
        )

    @task
    def high_level_planning_task(self) -> Task:
        return Task(
            config=self.tasks_config['high_level_planning_task'],
            output_file='high_level_planning_task.md',
        )

    def _load_subtasks(self):
        with open("verilog_task.json") as f:
            data = json.load(f)
        return data["Sub-Task"]

    def _load_task_template(self):
        # Correct path construction
        config_dir = Path(__file__).parent / "config"
        tasks_path = config_dir / "tasks.yaml"  # Explicit path to YAML file

        with open(tasks_path) as f:
            return yaml.safe_load(f)['verilog_conversion']  # Access 'verilog_conversion' directly

    # Updated method to clean and save results
    def _save_results(self, results):
        # Clean and combine all Verilog snippets
        cleaned_verilog = []
        
        for result in results:
            # Remove markdown code blocks and whitespace
            cleaned = result.replace('```verilog', '').replace('```', '').strip()
            cleaned_verilog.append(cleaned)
        
        # Combine all snippets with proper formatting
        final_code = "\n\n".join(cleaned_verilog)
        
        # Write to a single file
        with open("four_bit_adder.v", "w") as f:
            f.write(final_code)

    # Modified task creation (remove individual output files)
    def verilog_subtasks(self) -> list[Task]:
        subtasks = self._load_subtasks()
        task_template = self._load_task_template()
        agent = self.verilog_agent()

        return [
            Task(
                description=task_template['description'].format(content=sub['content']),
                expected_output=task_template['expected_output'],
                agent=agent,
                # Removed output_file parameter
            )
            for sub in subtasks
        ]

    @crew
    def crew1(self) -> Crew:
        """High-level planner only"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            memory=True,
            embedder={
                "provider": "ollama",
                "config": {"model": "all-minilm"}
            }
        )

    @crew
    def verilog_crew(self) -> Crew:
        """Dynamically runs Verilog conversion subtasks"""
        return Crew(
            agents=[self.verilog_agent()],
            tasks=self.verilog_subtasks(),
            process=Process.sequential,
            verbose=True,
            memory=True,
            embedder={
                "provider": "ollama",
                "config": {"model": "all-minilm"}
            }
        )
