import json
from crewai import Agent, Task, Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI
import os

# Step 1: Load the JSON and extract subtasks
with open("cleaned.json") as f:
    data = json.load(f)
subtasks = data["Sub-Task"]

llm=ChatGoogleGenerativeAI(model="gemini-2.0-flash",
                           verbose=True,
                           temperature=0.5,
                           google_api_key=os.getenv("GOOGLE_API_KEY"))

# Step 2: Define the Verilog Agent
verilog_agent = Agent(
    role="Verilog Engineer",
    goal="Translate sub-task descriptions into accurate Verilog code",
    backstory="You're an HDL expert with deep Verilog knowledge",
    llm=llm,
    verbose=True,
    memory=False,
)

# Step 3: Create task loop per subtask
verilog_snippets = []
for st in subtasks:
    task = Task(
        description=f"""
        Convert this natural language subtask into Verilog code.

        Subtask description:
        {st['content']}

        Only return the Verilog code for this step.
        """,
        expected_output="A single snippet of Verilog code.",
        agent=verilog_agent
    )

    crew = Crew(
        agents=[verilog_agent],
        tasks=[task],
        process=Process.sequential,
    )

    result = crew.kickoff()
    verilog_snippets.append(result)

# Step 4: Combine everything and write to .v file
final_verilog = "\n".join(verilog_snippets)
with open("four_bit_adder.v", "w") as f:
    f.write(final_verilog)
