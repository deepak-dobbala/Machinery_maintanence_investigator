from google.adk.agents import LlmAgent
from google.adk.workflow import Workflow, FunctionNode, Edge, START


def first_step():
    print("SPIKE_FIRST_STEP_OK")
    return {"message": "First function completed"}


first = FunctionNode(
    name="first_step",
    func=first_step,
    parameter_binding="node_input",
)

spike_agent = LlmAgent(
    name="spike_agent",
    model="gemini-2.5-flash",
    instruction="Reply with exactly: SPIKE_OK",
)


def final_step(node_input):
    print("SPIKE_FINAL_STEP_OK")
    print("Agent output received:", repr(node_input))
    return {
        "status": "SPIKE_COMPLETE",
        "agent_output": str(node_input),
    }


last = FunctionNode(
    name="final_step",
    func=final_step,
    parameter_binding="node_input",
)


root_agent = Workflow(
    name="day41_spike",
    description="Day 4.1 minimal function-agent-function workflow",
    edges=[
        Edge(from_node=START, to_node=first),
        Edge(from_node=first, to_node=spike_agent),
        Edge(from_node=spike_agent, to_node=last),
    ],
)
