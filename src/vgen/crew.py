from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from pathlib import Path
import yaml
import os
import json
from vgen.config import clean_verilog_file, Target_Problem  # Add this import at the top
from vgen.tools.custom_tool import run_icarus_verilog
from langchain_community.chat_models import ChatLiteLLM
from langchain_openai import ChatOpenAI


def get_gemini_pro_crew():
    return LLM(
        api_key=os.getenv("GEMINI_API_KEY"),
        model="gemini/gemini-2.0-flash",
    )

llm = ChatLiteLLM(model="azure/o3-mini", temperature=0.7)

llm_lmstudio = ChatOpenAI(
    openai_api_base="http://localhost:1234/v1",
    openai_api_key="",
    model_name="qwen2.5-coder-0.5b-instruct"
)

# llm_groq = LLM(model="groq/llama3-70b-8192")

# llm_openrouter = LLM(
#     model="openrouter/qwen/qwen-2.5-coder-32b-instruct:free",
#     base_url="https://openrouter.ai/api/v1",
#     api_key=os.getenv("OPEN_ROUTER_API_KEY"),
# )

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
            llm=llm_lmstudio
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
            llm=llm
        )
    
    

    @task
    def high_level_planning_task(self) -> Task:
        return Task(
            config=self.tasks_config['high_level_planning_task'],
            output_file='high_level_planning_task.md',
            human_input=False
        )

    def _load_subtasks(self):
        try:
            with open("verilog_task.json") as f:
                data = json.load(f)
            return data["Sub-Task"]
        except FileNotFoundError:
            print("Warning: verilog_task.json not found. This is expected during the planning phase.")
            return []  # Return empty list if file doesn't exist

    def _load_task_template(self):
        # Correct path construction
        config_dir = Path(__file__).parent / "config"
        tasks_path = config_dir / "tasks.yaml"  # Explicit path to YAML file

        with open(tasks_path) as f:
            return yaml.safe_load(f)['verilog_conversion']  # Access 'verilog_conversion' directly

    # Updated method to clean and save results
    def _save_results(self, results):
        # Handle CrewOutput objects
        processed_results = []
        for result in results:
            if hasattr(result, 'raw_output'):
                # Extract raw_output from CrewOutput
                processed_results.append(str(result.raw_output))
            else:
                # Handle other types (strings, tuples, etc.)
                processed_results.append(str(result))
        
        # Combine all snippets with proper formatting
        final_code = "\n\n".join(processed_results)
        
        # Write raw output to a temporary file
        temp_file = "design_raw.sv"
        with open(temp_file, "w") as f:
            f.write(final_code)
        
        # Use the clean_verilog_file function to clean the output
        output_file = "design.sv"
        clean_verilog_file(temp_file, output_file)
        print(f"Saved cleaned Verilog code to {output_file}")
        
    # # Method to save testbench results
    # def _save_testbench_results(self, results):
    #     # Handle CrewOutput objects
    #     processed_results = []
    #     for result in results:
    #         if hasattr(result, 'raw_output'):
    #             # Extract raw_output from CrewOutput
    #             processed_results.append(str(result.raw_output))
    #         else:
    #             # Handle other types (strings, tuples, etc.)
    #             processed_results.append(str(result))
        
    #     # Combine all snippets with proper formatting
    #     final_code = "\n\n".join(processed_results)
        
    #     # Write raw output to a temporary file
    #     temp_file = "testbench_raw.sv"
    #     with open(temp_file, "w") as f:
    #         f.write(final_code)
        
    #     # Use the clean_verilog_file function to clean the output
    #     output_file = "testbench.sv"
    #     clean_verilog_file(temp_file, output_file)
    #     print(f"Saved cleaned testbench code to {output_file}")

    # Modified task creation to save individual output files
    def verilog_subtasks(self) -> list[Task]:
        subtasks = self._load_subtasks()
        task_template = self._load_task_template()
        agent = self.verilog_agent()

        return [
            Task(
                name=f"verilog_subtask_{i+1}",
                description=task_template['description'].format(content=sub['content'], source=sub['source']),
                expected_output=task_template['expected_output'],
                agent=agent,
                human_input=False,
                output_file=f"subtask_{i+1}.v"  # Save each subtask output to a file
            )
            for i, sub in enumerate(subtasks)
        ]

    def collect_subtask_outputs(self) -> str:
        """Collect all subtask outputs from files into a single string"""
        subtasks = self._load_subtasks()
        all_code = []
        
        # Collect all subtask output files
        for i in range(len(subtasks)):
            file_path = f"subtask_{i+1}.v"
            try:
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        code = f.read().strip()
                        all_code.append(f"// Subtask {i+1} code\n{code}")
            except Exception as e:
                print(f"Error reading subtask file {file_path}: {e}")
        
        return "\n\n".join(all_code)

    
        
    @crew
    def subtask_crew(self) -> Crew:
        """Crew for executing verilog subtasks"""
        return Crew(
            agents=[self.verilog_agent()],
            tasks=self.verilog_subtasks(),
            process=Process.sequential,
            verbose=True,
            memory=True,
            embedder={
                "provider": "ollama",
                "config": {"model": "all-minilm"}
            },
            output_log_file=os.path.join(".crew", "logs", "subtasks.json"),
        )

    # @crew
    # def testbench_crew(self) -> Crew:
    #     """Testbench generation crew"""
    #     return Crew(
    #         agents=[self.testbench_agent()],
    #         tasks=[self.testbench_task()],
    #         process=Process.sequential,
    #         verbose=True,
    #         memory=True,
    #         embedder={
    #             "provider": "ollama",
    #             "config": {"model": "all-minilm"}
    #         },
    #         output_log_file=os.path.join(".crew", "logs", "testbench.json"),
    #     )

    @agent
    def testbench_fixer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['testbench_fixer_agent'],
            verbose=True,
            llm=llm
        )

    # @task
    # def testbench_task(self) -> Task:
    #     # Load the first subtask from verilog_task.json
    #     try:
    #         with open("verilog_task.json") as f:
    #             data = json.load(f)
    #             first_subtask = data["Sub-Task"][0]["source"] if data["Sub-Task"] else ""
    #     except Exception as e:
    #         print(f"Error loading verilog_task.json: {e}")
    #         first_subtask = ""

    #     # Get the Target_Problem from the same hardcoded value as in main.py
    #     target_problem = Target_Problem
 
    #     # Get the testbench task configuration
    #     task_config = self.tasks_config['testbench_generation'].copy()
        
    #     # Create a Task with necessary configuration
    #     task = Task(
    #         name="testbench_generation",
    #         config=task_config,
    #         agent=self.testbench_agent(),
    #         output_file="testbench.sv",
    #         context=[],
    #         human_input=False
    #     )
        
    #     # Interpolate the inputs into the task
    #     task.interpolate_inputs_and_add_conversation_history({
    #         "first_subtask": first_subtask,
    #         "Target_Problem": target_problem
    #     })
        
    #     return task

    @agent
    def merger_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['verilog_merger'],
            verbose=True,
            llm=llm
        )
    
    @task
    def merging_task(self) -> Task:
        # Get the Target_Problem from the same hardcoded value as in main.py
        target_problem = Target_Problem

        # Collect all subtask outputs
        subtask_code = self.collect_subtask_outputs()
        
        # Create a Task with necessary configuration
        task = Task(
            name="verilog_merging",
            config=self.tasks_config['verilog_merging'].copy(),
            agent=self.merger_agent(),
            human_input=False,
            output_file='design.sv',
            context=[]  # Empty list since we'll pass code directly via interpolation
        )
        
        # Interpolate the Target_Problem and subtask code into the task
        task.interpolate_inputs_and_add_conversation_history({
            "Target_Problem": target_problem,
            "context": subtask_code  # Pass collected code as context
        })
        
        return task
    
    @crew
    def merging_crew(self) -> Crew:
        """Dedicated crew for just the merging task"""
        return Crew(
            agents=[self.merger_agent()],
            tasks=[self.merging_task()],
            process=Process.sequential,
            verbose=True,
            memory=True,
            embedder={
                "provider": "ollama",
                "config": {"model": "all-minilm"}
            },
            output_log_file=os.path.join(".crew", "logs", "merging.json"),
        )
    
    @task
    def iverilog_task(self) -> Task:
        return Task(
            name="iverilog_task",
            config=self.tasks_config['iverilog_task'],
            agent=self.iverilog_agent(),
            output_file="iverilog_report.md"
        )
    @agent
    def iverilog_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['iverilog_agent'],
            tools=[run_icarus_verilog],
            verbose=True,
            llm=get_gemini_pro_crew()
        )
        
    @crew
    def icarus_crew(self) -> Crew:
        """Icarus simulation crew"""
        return Crew(
            agents=[self.iverilog_agent()],
            tasks=[self.iverilog_task()],
            process=Process.sequential,
            verbose=True,
            memory=True,
            embedder={
                "provider": "ollama",
                "config": {"model": "all-minilm"}
            },
            output_log_file=os.path.join(".crew", "logs", "iverilog_simulation.json"),
        )
        
    # @task
    # def fix_testbench_task(self) -> Task:
    #     try:
    #         with open("iverilog_report.json", "r") as f:
    #             data = json.load(f)
    #         testbench_file = data.get("files", {}).get("testbench", {}).get("content", "")
    #         suggestions = data.get("files", {}).get("testbench", {}).get("suggestions", "")
    #     except Exception as e:
    #         print(f"Error loading iverilog_report.json: {e}")
    #         testbench_file = ""
    #         suggestions = ""
        
    #     task_config = self.tasks_config['fix_testbench_task'].copy()

    #     task= Task(
    #         name="fix_testbench_task",
    #         config=task_config,
    #         agent=self.testbench_fixer_agent(),
    #         output_file="fixed_testbench.sv",
    #         context=[]
    #     )
        
    #     task.interpolate_inputs_and_add_conversation_history({
    #         "testbench_file": testbench_file,
    #         "suggestions": suggestions
    #     })
        
    #     return task
    
    # @crew
    # def testbench_fixer_crew(self) -> Crew:
    #     """Testbench Fixer crew"""
    #     return Crew(
    #         agents=[self.testbench_fixer_agent()],
    #         tasks=[self.fix_testbench_task()],
    #         process=Process.sequential,
    #         verbose=True,
    #         memory=True,
    #         embedder={
    #             "provider": "ollama",
    #             "config": {"model": "all-minilm"}
    #         },
    #         output_log_file=os.path.join(".crew", "logs", "testbench.json"),
    #     )

    @task
    def fix_design_task(self) -> Task:
        try:
            with open("iverilog_report.json", "r") as f:
                data = json.load(f)
            design_file = data.get("files", {}).get("design", {}).get("content", "")
            suggestions = data.get("files", {}).get("design", {}).get("suggestions", "")
        except Exception as e:
            print(f"Error loading iverilog_report.json: {e}")
            design_file = ""
            suggestions = ""
        
        task_config = self.tasks_config['fix_design_task'].copy()

        task = Task(
            name="fix_design_task",
            config=task_config,
            agent=self.design_fixer_agent(),
            output_file="fixed_design.sv",
            context=[]
        )
        
        task.interpolate_inputs_and_add_conversation_history({
            "design_file": design_file,
            "suggestions": suggestions
        })
        
        return task
    @agent
    def design_fixer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['design_fixer_agent'],
            llm=llm,
            tools=[],
            verbose=True
        )
    @crew
    def Design_fixer_crew(self) -> Crew:
        """Icarus simulation crew"""
        return Crew(
            agents=[self.design_fixer_agent()],
            tasks=[self.fix_design_task()],
            process=Process.sequential,
            verbose=True,
            memory=True,
            embedder={
                "provider": "ollama",
                "config": {"model": "all-minilm"}
            },
            output_log_file=os.path.join(".crew", "logs", "iverilog_simulation.json"),
        ) 

    def _save_fixed_design_results(self, results):
        """
        Save the results from the design fixer crew by cleaning and writing to design.sv
        """
        # Handle CrewOutput objects
        processed_results = []
        for result in results:
            if hasattr(result, 'raw_output'):
                # Extract raw_output from CrewOutput
                processed_results.append(str(result.raw_output))
            else:
                # Handle other types (strings, tuples, etc.)
                processed_results.append(str(result))
        
        # Combine all snippets with proper formatting
        final_code = "\n\n".join(processed_results)
        
        # Write raw output to a temporary file
        temp_file = "fixed_design_raw.sv"
        with open(temp_file, "w") as f:
            f.write(final_code)
        
        # Use the clean_verilog_file function to clean the output
        output_file = "design.sv"  # Overwrite the original design file
        clean_verilog_file(temp_file, output_file)
        print(f"Saved cleaned fixed design code to {output_file}") 
