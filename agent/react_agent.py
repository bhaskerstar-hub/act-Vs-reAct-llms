from agent.decision_engine import DecisionEngine, ReActStep
from agent.tools import get_all_tools

MAX_STEPS = 6


class ReActAgent:
    """
    Drives the Reason + Act loop:
      1. Ask the decision engine what to think and which tool to call next.
      2. Execute the tool and record the observation.
      3. Feed the updated context back and repeat until a terminal action is reached.
    """

    def __init__(self):
        self.engine = DecisionEngine()
        self.tools  = {t.name: t for t in get_all_tools()}

    def run(self, customer_id: str, message: str) -> dict:
        context = {
            "customer_id": customer_id,
            "message": message,
            "history": [],
        }

        trace       = []
        accumulated = {}

        for step_index in range(MAX_STEPS):
            step: ReActStep = self.engine.decide_next_step(context)
            context["history"].append(step)

            trace_entry = {
                "step": step_index + 1,
                "thought": step.thought,
                "action": step.action,
                "action_input": step.action_input,
                "observation": None,
            }

            if step.is_final:
                trace_entry["observation"] = step.final_answer
                trace.append(trace_entry)
                accumulated["final_answer"] = step.final_answer
                break

            if step.action and step.action in self.tools:
                observation = self.tools[step.action].run(step.action_input or {})
                context["history"].append({"tool": step.action, "result": observation})
                trace_entry["observation"] = observation
                accumulated[step.action]   = observation

            trace.append(trace_entry)

            if step.action in ("route_to_human", "generate_auto_response"):
                break

        urgency        = accumulated.get("check_urgency", {}).get("urgency", "low")
        routed_to_human = "route_to_human" in accumulated
        routing        = accumulated.get("route_to_human", {})
        auto           = accumulated.get("generate_auto_response", {})
        kb             = accumulated.get("search_knowledge_base", {})

        return {
            "trace": trace,
            "urgency": urgency,
            "routed_to_human": routed_to_human,
            "queue": routing.get("queue"),
            "escalation_reason": routing.get("reason"),
            "estimated_response_time": routing.get("estimated_response_time"),
            "auto_response": auto.get("response"),
            "kb_category": kb.get("category"),
        }
