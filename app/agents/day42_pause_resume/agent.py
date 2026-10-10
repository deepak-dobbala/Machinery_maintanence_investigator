from google.adk.workflow import Workflow, FunctionNode, Edge, START
from google.adk.events.request_input import RequestInput


def begin_test():
    print("PAUSE_RESUME_BEGIN_OK")
    return {"status": "started"}


def request_technician_confirmation(ctx):
    print("RESUME_INPUTS_DEBUG:", repr(ctx.resume_inputs))
    response = ctx.resume_inputs.get("technician_confirmation_day42")

    if response is not None:
        print("PAUSE_RESUME_RESUMED_OK")
        print("Resume response:", repr(response))
        return response

    print("PAUSE_RESUME_REQUESTING_INPUT")
    return RequestInput(
        interrupt_id="technician_confirmation_day42",
        message="Day 4.2 test: enter CONFIRM to resume the workflow.",
        response_schema=str,
        payload={"purpose": "pause_resume_test"},
    )


def finish_test(node_input):
    print("PAUSE_RESUME_FINISH_OK")
    print("Technician response received:", repr(node_input))

    if node_input != "CONFIRM":
        return {
            "status": "RESPONSE_PROPAGATION_FAILED",
            "received": repr(node_input),
        }

    return {
        "status": "PAUSE_RESUME_COMPLETE",
        "technician_response": node_input,
        "response_propagation_verified": True,
    }


begin = FunctionNode(
    name="begin_test",
    func=begin_test,
    parameter_binding="node_input",
)

request_input = FunctionNode(
    name="request_technician_confirmation",
    func=request_technician_confirmation,
    parameter_binding="node_input",
    rerun_on_resume=True,
)

finish = FunctionNode(
    name="finish_test",
    func=finish_test,
    parameter_binding="state",
)

root_agent = Workflow(
    name="day42_pause_resume",
    description="Isolated ADK workflow pause and resume test",
    edges=[
        Edge(from_node=START, to_node=begin),
        Edge(from_node=begin, to_node=request_input),
        Edge(from_node=request_input, to_node=finish),
    ],
)
