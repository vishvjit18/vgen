from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from pathlib import Path
import yaml
import os
import json
from vgen.config import clean_verilog_file, clean_verilog_backticks, Target_Problem, get_target_problem  
from vgen.tools.custom_tool import run_icarus_verilog, save_output_tool
from langchain_community.chat_models import ChatLiteLLM
from langchain_openai import ChatOpenAI


def get_gemini_pro_crew():
    return LLM(
        api_key=os.getenv("GEMINI_API_KEY"),
        model="gemini/gemini-2.0-flash",
    )

def get_gemini_flash_crew():
    return LLM(
        api_key=os.getenv("GOOGLE_API_KEY"),
        model="gemini/gemini-2.0-flash",
    )


llm = ChatLiteLLM(model="azure/o3-mini", temperature=0.7)

llm_lmstudio = ChatOpenAI(
    openai_api_base="http://localhost:1234/v1",
    openai_api_key="no-key-needed",
    model_name="openai/qwen3-14b",
    temperature=0.7,
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
            llm=llm,
            tools=[save_output_tool],
        )
    @task
    def high_level_planning_task(self) -> Task:
        return Task(
            config=self.tasks_config['high_level_planning_task'],
            output_file='high_level_planning_task.md',
            human_input=True,
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
    
    def _extract_verilog_code(self, obj):
        """
        Recursively extract Verilog code from complex nested data structures
        """
        def clean_verilog_string(s):
            """Extract only the Verilog part from a mixed string"""
            if not isinstance(s, str):
                return None
            
            # Find the start of Verilog code
            verilog_start = -1
            for marker in ['`timescale', 'module ']:
                idx = s.find(marker)
                if idx != -1:
                    verilog_start = idx
                    break
            
            if verilog_start == -1:
                return None
            
            # Find the end of Verilog code (before Python metadata)
            verilog_end = len(s)
            python_markers = ['\n\n(', "('pydantic'", "('json_dict'", "('tasks_output'"]
            for marker in python_markers:
                idx = s.find(marker, verilog_start)
                if idx != -1:
                    verilog_end = min(verilog_end, idx)
            
            # Extract and clean the Verilog portion
            verilog_code = s[verilog_start:verilog_end].strip()
            
            # Clean stray backticks except for `timescale
            verilog_code = clean_verilog_backticks(verilog_code)
            
            # Verify it's actually Verilog code
            if 'endmodule' in verilog_code or '`timescale' in verilog_code:
                return verilog_code
            
            return None
        
        if isinstance(obj, str):
            # If it's already a string, extract clean Verilog
            return clean_verilog_string(obj)
        
        if hasattr(obj, 'raw'):
            # Handle TaskOutput objects with 'raw' attribute
            raw_content = getattr(obj, 'raw')
            if isinstance(raw_content, str):
                return clean_verilog_string(raw_content)
            return raw_content
        
        if hasattr(obj, 'raw_output'):
            # Handle CrewOutput objects
            raw_output = str(obj.raw_output)
            return clean_verilog_string(raw_output)
        
        if isinstance(obj, (list, tuple)):
            # Handle lists/tuples - look for Verilog code in any element
            for item in obj:
                code = self._extract_verilog_code(item)
                if code:
                    return code
        
        if isinstance(obj, dict):
            # Handle dictionaries - look for keys that might contain Verilog
            for key, value in obj.items():
                if key in ['raw', 'raw_output', 'content', 'code']:
                    code = self._extract_verilog_code(value)
                    if code:
                        return code
            # If no specific keys found, search all values
            for value in obj.values():
                code = self._extract_verilog_code(value)
                if code:
                    return code
        
        # If it has attributes, check for common ones
        if hasattr(obj, '__dict__'):
            for attr_name in ['raw', 'raw_output', 'content', 'code']:
                if hasattr(obj, attr_name):
                    code = self._extract_verilog_code(getattr(obj, attr_name))
                    if code:
                        return code
        
        return None

    # Modified task creation to save individual output files
    @agent
    def verilog_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['verilog_agent'],
            verbose=True,
            llm=llm
        )

    def _load_subtasks(self):
        try:
            with open("verilog_task.json") as f:
                data = json.load(f)
            return data["Sub-Task"]
        except FileNotFoundError:
            print("Warning: verilog_task.json not found. This is expected during the planning phase.")
            return [] 

    def _load_task_template(self):
        # Correct path construction
        config_dir = Path(__file__).parent / "config"
        tasks_path = config_dir / "tasks.yaml" 

        with open(tasks_path) as f:
            return yaml.safe_load(f)['verilog_conversion']  # Access 'verilog_conversion' directly
    # Updated method to clean and save results
    def _save_results(self, results):
        # Extract Verilog code from results
        verilog_code = None
        
        # Handle single result or list of results
        if not isinstance(results, list):
            results = [results]
        
        for result in results:
            code = self._extract_verilog_code(result)
            if code:
                verilog_code = code
                break
        
        if not verilog_code:
            # Fallback to original behavior if we can't extract Verilog code
            print("Warning: Could not extract Verilog code from results, falling back to string conversion")
            processed_results = []
            for result in results:
                if hasattr(result, 'raw_output'):
                    processed_results.append(str(result.raw_output))
                else:
                    processed_results.append(str(result))
            verilog_code = "\n\n".join(processed_results)
        
        # Write raw output to a temporary file
        temp_file = "design_raw.sv"
        with open(temp_file, "w") as f:
            f.write(verilog_code)
        
        # Use the clean_verilog_file function to clean the output
        output_file = "design.sv"
        clean_verilog_file(temp_file, output_file)
        print(f"Saved cleaned Verilog code to {output_file}")
    #@task
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

    @agent
    def merger_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['verilog_merger'],
            verbose=True,
            llm=llm,
            tools=[save_output_tool]
        )
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
    @task
    def merging_task(self) -> Task:

        # Collect all subtask outputs
        subtask_code = self.collect_subtask_outputs()
        
        # Create a Task with necessary configuration
        task = Task(
            name="verilog_merging",
            config=self.tasks_config['verilog_merging'].copy(),
            agent=self.merger_agent(),
            human_input=True,
            output_file='design.sv',
            context=[]  # Empty list since we'll pass code directly via interpolation
        )
        
        # Interpolate the Target_Problem and subtask code into the task
        task.interpolate_inputs_and_add_conversation_history({
            "context": subtask_code,  # Pass collected code as context
            "Target_Problem": get_target_problem()
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
    
    @agent
    def testbench_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['testbench_agent'],
            verbose=True,
            llm=llm
        )
    # Method to save testbench results
    def _save_testbench_results(self, results):
        # Extract Verilog code from results
        verilog_code = None
        
        # Handle single result or list of results
        if not isinstance(results, list):
            results = [results]
        
        for result in results:
            code = self._extract_verilog_code(result)
            if code:
                verilog_code = code
                break
        
        if not verilog_code:
            # Fallback to original behavior if we can't extract Verilog code
            print("Warning: Could not extract Verilog code from results, falling back to string conversion")
            processed_results = []
            for result in results:
                if hasattr(result, 'raw_output'):
                    processed_results.append(str(result.raw_output))
                else:
                    processed_results.append(str(result))
            verilog_code = "\n\n".join(processed_results)
        
        # Write raw output to a temporary file
        temp_file = "testbench_raw.sv"
        with open(temp_file, "w") as f:
            f.write(verilog_code)
        
        # Use the clean_verilog_file function to clean the output
        output_file = "testbench.sv"
        clean_verilog_file(temp_file, output_file)
        print(f"Saved cleaned testbench code to {output_file}")
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
 
        # Get the testbench task configuration
        task_config = self.tasks_config['testbench_generation'].copy()
        
        # Create a Task with necessary configuration
        task = Task(
            name="testbench_generation",
            config=task_config,
            agent=self.testbench_agent(),
            output_file="testbench.sv",
            context=[]
        )
        
        # Interpolate the inputs into the task
        task.interpolate_inputs_and_add_conversation_history({
            "first_subtask": first_subtask,
            "Target_Problem": get_target_problem()
        })
        
        return task
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

    # @agent
    # def testbench_fixer_agent(self) -> Agent:
    #     return Agent(
    #         config=self.agents_config['testbench_fixer_agent'],
    #         verbose=True,
    #         llm=llm
    #     )
    
    @agent
    def iverilog_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['iverilog_agent'],
            tools=[run_icarus_verilog],
            verbose=True,
            llm=llm
        )
    @task
    def iverilog_task(self) -> Task:
        return Task(
            name="iverilog_task",
            config=self.tasks_config['iverilog_task'],
            agent=self.iverilog_agent(),
            output_file="iverilog_report.md"
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

    @agent
    def design_fixer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['design_fixer_agent'],
            llm=llm,
            tools=[],
            verbose=True
        )
    def _save_fixed_design_results(self, results):
        """
        Save the results from the design fixer crew by cleaning and writing to design.sv
        """
        # Extract Verilog code from results
        verilog_code = None
        
        # Handle single result or list of results
        if not isinstance(results, list):
            results = [results]
        
        for result in results:
            code = self._extract_verilog_code(result)
            if code:
                verilog_code = code
                break
        
        if not verilog_code:
            # Fallback to original behavior if we can't extract Verilog code
            print("Warning: Could not extract Verilog code from results, falling back to string conversion")
            processed_results = []
            for result in results:
                if hasattr(result, 'raw_output'):
                    processed_results.append(str(result.raw_output))
                else:
                    processed_results.append(str(result))
            verilog_code = "\n\n".join(processed_results)
        
        # Write raw output to a temporary file
        temp_file = "fixed_design_raw.sv"
        with open(temp_file, "w") as f:
            f.write(verilog_code)
        
        # Use the clean_verilog_file function to clean the output
        output_file = "design.sv"  # Overwrite the original design file
        clean_verilog_file(temp_file, output_file)
        print(f"Saved cleaned fixed design code to {output_file}") 
    @task
    def fix_design_task(self) -> Task:
        try:
            with open("iverilog_report.json", "r") as f:
                data = json.load(f)
            design_file = data.get("files", {}).get("design", {}).get("content", "")
            
            # Try to get suggestions with both possible spellings
            suggestions = data.get("files", {}).get("design", {}).get("suggesstions", "")
            if not suggestions:  # If empty, try alternate spelling
                suggestions = data.get("files", {}).get("design", {}).get("suggestions", "")
            
            # Debug output
            print(f"Design content length: {len(design_file)}")
            print(f"Suggestions content: {suggestions[:100]}...")  # Print first 100 chars
            
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
            human_input=True,
            context=[]
        )
        
        # Add debug info to help trace the issue
        print(f"Passing design file ({len(design_file)} chars) and suggestions ({len(suggestions)} chars) to agent")
        
        task.interpolate_inputs_and_add_conversation_history({
            "design_file": design_file,
            "suggestions": suggestions
        })
        
        return task
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
