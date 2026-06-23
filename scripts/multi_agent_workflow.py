import os
import asyncio
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv
from agents import function_tool


#configure state for theorems, agent can populate some fields

PROJECT_ROOT = Path("/Users/amirnabiyev/Conjecture_Prover")
WORKSPACE_PATH = PROJECT_ROOT / "LeanWorkspace/input.lean"


class TheoremState(BaseModel):
    user_input:str
    theorem: str
    workspace_path: str
    errors_remaining: bool = True


@function_tool
def read_workspace() -> str:
    """Read the Lean workspace file that all pipeline stages must edit."""
    return WORKSPACE_PATH.read_text()


@function_tool
def write_workspace(content: str) -> str:
    """Overwrite the Lean workspace file with the provided Lean code."""
    WORKSPACE_PATH.write_text(content)
    return f"wrote {len(content)} characters to {WORKSPACE_PATH}"


@function_tool
def read_project_file(relative_path: str) -> str:
    """Read a UTF-8 text file under the project root, such as examples or prompts."""
    path = (PROJECT_ROOT / relative_path).resolve()
    if not path.is_relative_to(PROJECT_ROOT):
        raise ValueError("relative_path must stay inside the project root")
    return path.read_text()

from agents import (
    Agent,
    Runner,
    WebSearchTool,
    set_default_openai_api,
)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from agents.mcp import MCPServerStdio


load_dotenv(override=True) # the override isnt strictly necessary since we aren't committing the .env file, but it doesn't hurt to be explicit

set_default_openai_api(os.getenv("OPENAI_API_KEY")) # gets api key for model usage


LEAN_MCP_TOOL_RULES = f"""

## Lean MCP tool rules
You have access to the Lean MCP server. Use its Lean-specific tools for compile/build/proof feedback.
Important tools include `lean_diagnostic_messages`, `lean_goal`, `lean_code_actions`, `lean_run_code`, `lean_build`, and `lean_verify`.

The workspace file is exactly:
{WORKSPACE_PATH}

The Lean project root is exactly:
{PROJECT_ROOT}

Before handing control back:
1. Save any intended edits to the workspace file using `write_workspace`.
2. Call `lean_diagnostic_messages` with `file_path` exactly `{WORKSPACE_PATH}`.
3. If project-level generated files or imports may be affected, call `lean_build`.
4. If you claim the theorem is proved, call `lean_verify` on the relevant declaration.
5. Return a concise summary of the files changed and the Lean MCP result.

Do not use structured final output. Your job is to modify files and use tools.
"""


WORKER_RETURN_RULES = """

## Stage completion rule
When your stage is finished or blocked, return a concise plain-text summary.
Do not hand off to another agent yourself. The Python workflow decides the next stage.
If you could not complete the stage, include the exact Lean MCP diagnostics and the next recommended stage.
"""


def workspace_text() -> str:
    return WORKSPACE_PATH.read_text() if WORKSPACE_PATH.exists() else ""


def has_blueprint(text: str) -> bool:
    return "@[blueprint" in text and ("theorem " in text or "lemma " in text)


def has_incomplete_proofs(text: str) -> bool:
    return "sorry" in text or "sorry_using" in text


async def run_stage(agent: Agent, prompt: str, max_turns: int) -> str:
    result = await Runner.run(agent, prompt, max_turns=max_turns)
    print(f"\n--- {agent.name} result ---")
    print(result.final_output)
    return str(result.final_output)

async def main() -> None:
    common_tools = [read_workspace, write_workspace, read_project_file, WebSearchTool()]
    codex_mcp_server = MCPServerStdio(name = "Codex CLI",
        params = {
            "command":"codex",
            "args":["mcp-server"]
        },
        client_session_timeout_seconds=360000,)
    filesystem_mcp_server = MCPServerStdio(name = "Filesystem MCP", params ={
        "command":"node",
        "args":["/Users/amirnabiyev/Conjecture_Prover/filesystem-mcp-server/dist/index.js"],
    })
    lean_mcp_server = MCPServerStdio(name = "Lean MCP", params ={
        "command":"uvx",
        "args":["lean-lsp-mcp"],
        "env":{
            "LEAN_PROJECT_PATH": str(PROJECT_ROOT),
            "LEAN_LOG_LEVEL": "NONE",
        },
    })
    async with (codex_mcp_server, filesystem_mcp_server,lean_mcp_server):
        """
        We will have 3 agents for this workflow:
        -Blueprint Generator Agent: Generates a blueprint for the theorem to be proved
        -Theorem Prover Agent: Attempts to prove the lemmas in the blueprint and the main theorem
        -Blueprint Refinement Agent: If the theorem prover fails, this agent will refine the blueprint and try again
        """
        theorem_proving_agent = Agent(
            name = "Theorem Prover",
            instructions = (
                RECOMMENDED_PROMPT_PREFIX
                + Path(PROJECT_ROOT / "prompts/theorem_prover.md").read_text()
                + LEAN_MCP_TOOL_RULES
                + WORKER_RETURN_RULES
            ),
            tools = common_tools,
            model = "gpt-5.4",
            mcp_servers = [codex_mcp_server,filesystem_mcp_server,lean_mcp_server],
            handoff_description="Completes Lean proofs in the workspace and checks them with Lean MCP."
        )
        blueprint_refinement_agent = Agent(
            name = "Blueprint Refinement",
            instructions = (
                RECOMMENDED_PROMPT_PREFIX
                + Path(PROJECT_ROOT / "prompts/blueprint_refiner.md").read_text()
                + LEAN_MCP_TOOL_RULES
                + WORKER_RETURN_RULES
            ),
            tools = common_tools,
            model = "gpt-5.4",
            mcp_servers = [codex_mcp_server,filesystem_mcp_server,lean_mcp_server],
            handoff_description="Refines the blueprint skeleton after failed proof attempts and checks it with Lean MCP."
          
        )
        blueprint_generator_agent  = Agent(
            name = "Blueprint Generator",
            instructions = (
                RECOMMENDED_PROMPT_PREFIX
                + Path(PROJECT_ROOT / "prompts/blueprint_generator.md").read_text()
                + f"""\n\nYou can look at {PROJECT_ROOT / "LeanWorkspace/Main.lean"} for an example on how to structure the blueprint."""
                + LEAN_MCP_TOOL_RULES
                + WORKER_RETURN_RULES
            ),
            tools = common_tools,
            model = "gpt-5.4",
            mcp_servers = [codex_mcp_server,filesystem_mcp_server,lean_mcp_server],
            handoff_description="Generates the initial LeanArchitect blueprint skeleton and checks it with Lean MCP."
           
        )
        #configure the input
        input = TheoremState(
            user_input = "Prove the theorem given and use the lean file given with the workspace path to prove it.",
            theorem = """Let G be a simple, undirected, unweighted graph with edge set E. Denote nonedges with E_cand. Given the objective function as the total effective resistance R_G = N sum_(1<= i <= j<= N) R_(i j) = N sum_(i=2)^(N) 1/lambda_i, we wish to minimize R_G for every step of a "graph iteration", with the addition of one edge per graph iteration. Prove that this problem is convex.""",
            workspace_path = str(WORKSPACE_PATH)
        )

        state_json = input.model_dump_json()
        text = workspace_text()

        if not has_blueprint(text):
            await run_stage(
                blueprint_generator_agent,
                f"""Generate the LeanArchitect blueprint now.
                Input state:{state_json}
                You must call `write_workspace` with the complete Lean file content.
                Then call `lean_diagnostic_messages` with file_path `{WORKSPACE_PATH}`.
                Return a concise summary only after those tool calls.
""",
                max_turns=None,
            )

        if not has_blueprint(workspace_text()):
            await run_stage(
                blueprint_generator_agent,
                f"""The previous generator pass did not create a blueprint in `{WORKSPACE_PATH}`.
                Do not return a message until you have called `write_workspace`.
                The file must contain imports, `@[blueprint]` declarations, and the main theorem for: {input.theorem}
                After writing, call `lean_diagnostic_messages` with file_path `{WORKSPACE_PATH}`.
""",
                max_turns=None,
            )

        if not has_blueprint(workspace_text()):
            print(f"Pipeline stopped: blueprint generator did not modify {WORKSPACE_PATH}.")
            return

        last_result = ""
        for attempt in range(1, 4):
            if not has_incomplete_proofs(workspace_text()):
                print("Pipeline finished: workspace has no textual `sorry` or `sorry_using`.")
                return

            last_result = await run_stage(
                theorem_proving_agent,
                f"""
                Attempt {attempt}: prove the blueprint declarations in `{WORKSPACE_PATH}`.
                Input state: {state_json}
                Use `read_workspace`, edit the file with `write_workspace`, then call
                `lean_diagnostic_messages` with file_path `{WORKSPACE_PATH}`.
                If the main theorem is solved, call `lean_verify`.
                """,
                max_turns=None,
            )

            if not has_incomplete_proofs(workspace_text()):
                print("Pipeline finished: theorem prover removed all textual `sorry`s.")
                return

            last_result = await run_stage(
                blueprint_refinement_agent,
                f"""Attempt {attempt}: the theorem prover did not finish. Refine the blueprint in `{WORKSPACE_PATH}`.
                Use this prover result as diagnostic context:{last_result}

Keep the main theorem statement unchanged. Use `write_workspace`, then call
`lean_diagnostic_messages` with file_path `{WORKSPACE_PATH}`.
""",
                max_turns=None,
            )

        print("Pipeline stopped: reached maximum prove/refine attempts.")
        print("Last result:", last_result)
    
if __name__ == "__main__":
    asyncio.run(main())
