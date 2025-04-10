from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from pathlib import Path
import yaml
import os
import json
from vgen.config import clean_verilog_file  # Add this import at the top

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
    
    @crew
    def crew1(self) -> Crew:
        """High-level planner only"""
        return Crew(
            agents=[self.planner()],
            tasks=[self.high_level_planning_task()],
            process=Process.sequential,
            verbose=True,
            memory=True,
            embedder={
                "provider": "ollama",
                "config": {"model": "all-minilm"}
            },
            output_log_file=os.path.join(".crew", "logs", "planner.json"),

        )

    @agent
    def verilog_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['verilog_agent'],
            verbose=True,
            human_input=False,
        )
    
    @agent
    def merger_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['verilog_merger'],
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
        # First, handle case where result might be a tuple
        if results and isinstance(results, tuple):
            results = [str(item) for item in results]
        elif not isinstance(results, list):
            results = [str(results)]
        
        # Combine all snippets with proper formatting
        final_code = "\n\n".join(results)
        
        # Write raw output to a temporary file
        temp_file = "design_raw.sv"
        with open(temp_file, "w") as f:
            f.write(final_code)
        
        # Use the clean_verilog_file function to clean the output
        output_file = "design.sv"
        clean_verilog_file(temp_file, output_file)

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
            )
            for sub in subtasks
        ]


    @task
    def merging_task(self) -> Task:
        return Task(
            name="verilog_merging",  # Add name parameter
            config=self.tasks_config['verilog_merging'],
            agent=self.merger_agent(),
            output_file='design.sv'
        )
    
        
    @crew
    def verilog_crew(self) -> Crew:
        """Complete Verilog generation pipeline"""
        return Crew(
            agents=[self.verilog_agent(), self.merger_agent()],
            tasks=[*self.verilog_subtasks(), self.merging_task()],
            process=Process.sequential,
            verbose=True,  # Changed from 2 to True
            memory=True,
            embedder={
                "provider": "ollama",
                "config": {"model": "all-minilm"}
            },
            output_log_file=os.path.join(".crew", "logs", "verilog_pipeline.json"),
        )

    @crew
    def testbench_crew(self) -> Crew:
        """Testbench generation crew"""
        return Crew(
            agents=[self.testbench_agent()],
            tasks=[self.testbench_task()],
            process=Process.sequential,
            verbose=True,
            memory=True,
            embedder={
                "provider": "ollama",
                "config": {"model": "all-minilm"}
            },
            output_log_file=os.path.join(".crew", "logs", "testbench.json"),
        )

    @agent
    def testbench_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['testbench_agent'],
            verbose=True,
            human_input=False,
        )

    @task
    def testbench_task(self) -> Task:
        # Load the first subtask from verilog_task.json
        try:
            with open("verilog_task.json") as f:
                data = json.load(f)
                first_subtask = data["Sub-Task"][0]["source"] if data["Sub-Task"] else ""
        except Exception as e:
            print(f"Error loading verilog_task.json: {e}")
            first_subtask = ""

        # Get the Target_Problem from the same hardcoded value as in main.py
        target_problem = """Please act as a professional verilog designer.

Implement a module of an 8-bit adder with multiple bit-level adders in combinational logic. 

Module name:  
    adder_8bit               
Input ports:
    a[7:0]: 8-bit input operand A.
    b[7:0]: 8-bit input operand B.
    cin: Carry-in input.
Output ports:
    sum[7:0]: 8-bit output representing the sum of A and B.
    cout: Carry-out output.

Implementation:
The module utilizes a series of bit-level adders (full adders) to perform the addition operation.

Give me the complete code."""
 
        # Get the testbench task configuration
        task_config = self.tasks_config['testbench_generation'].copy()
        
        # Create a Task with necessary configuration
        task = Task(
            name="testbench_generation",
            config=task_config,
            agent=self.testbench_agent(),
            output_file="testbench.sv",
            context=[]  # Empty list as context should be a list
        )
        
        # Interpolate the inputs into the task
        task.interpolate_inputs_and_add_conversation_history({
            "first_subtask": first_subtask,
            "Target_Problem": target_problem
        })
        
        return task
