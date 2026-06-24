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


def reports_verified(result: str) -> bool:
    normalized = result.lower()
    no_sorryax = "no sorryax" in normalized or "no sorry ax" in normalized
    success_markers = [
        "lean_verify success",
        "lean_verify: success",
        "verification successful",
        "verified successfully",
    ]
    failure_markers = [
        "lean_verify failed",
        "verification failed",
        "diagnosis:",
        "unproved_node:",
        "proof_too_hard",
        "statement_wrong",
    ]
    has_success = any(marker in normalized for marker in success_markers) or no_sorryax
    has_failure = any(marker in normalized for marker in failure_markers)
    has_sorryax_failure = ("sorryax" in normalized or "sorry ax" in normalized) and not no_sorryax
    return has_success and not has_failure and not has_sorryax_failure


def blueprint_quality_issues(text: str) -> list[str]:
    issues: list[str] = []
    forbidden_fragments = [
        'macro "sorry_using"',
        "syntax (name := blueprint",
        "syntax (name := blueprintAttr)",
        "macro_rules",
        "Placeholder `sorry_using`",
        "Placeholder `blueprint`",
    ]
    for fragment in forbidden_fragments:
        if fragment in text:
            issues.append(f"contains fake/local LeanArchitect replacement: {fragment}")

    if "import Architect" not in text:
        issues.append("missing real `import Architect`")

    theorem_lines = [
        line.strip()
        for line in text.splitlines()
        if line.lstrip().startswith("theorem ")
    ]
    if not theorem_lines:
        issues.append("missing a main `theorem` declaration")

    for line in theorem_lines:
        if ": True" in line or ": Prop := by" in line:
            issues.append(f"vacuous or placeholder theorem statement: {line}")

    if ": True := by" in text:
        issues.append("contains theorem/lemma with conclusion `True`")

    trivial_definition_fragments = [
        ": Prop :=\n  True",
        ": Prop := True",
        ": ℝ :=\n  0",
        ": ℝ := 0",
        "fun _t =>",
        "t • 0",
        "• 0",
    ]
    for fragment in trivial_definition_fragments:
        if fragment in text:
            issues.append(f"contains scaffold/trivializing definition fragment: {fragment!r}")

    load_bearing_names = [
        "total_effective_resistance",
        "laplacian_update",
        "has_spectral_resistance_formula",
        "edge_update_is_affine",
        "pseudoinverse_trace_convex_on_slice",
        "iteration_objective_is_convex",
    ]
    for name in load_bearing_names:
        if f"def {name}" in text:
            for bad in [f"def {name}", f"noncomputable def {name}"]:
                start = text.find(bad)
                if start == -1:
                    continue
                block = text[start:text.find("@[blueprint", start + 1) if text.find("@[blueprint", start + 1) != -1 else len(text)]
                if ": Prop :=" in block and "True" in block:
                    issues.append(f"`{name}` is defined as a `True` placeholder")
                if ": ℝ :=" in block and "\n  0" in block:
                    issues.append(f"`{name}` is defined as zero placeholder")
                if "fun _" in block:
                    issues.append(f"`{name}` ignores its mathematical argument")

    return issues


async def run_stage(agent: Agent, prompt: str, max_turns: int) -> str:
    result = await Runner.run(agent, prompt, max_turns=max_turns)
    print(f"\n--- {agent.name} result ---")
    print(result.final_output)
    return str(result.final_output)

async def main() -> None:
    common_tools = [read_workspace, write_workspace, read_project_file, WebSearchTool()]
    lean_mcp_server = MCPServerStdio(name = "Lean MCP", params ={
        "command":"uvx",
        "args":["lean-lsp-mcp"],
        "env":{
            "LEAN_PROJECT_PATH": str(PROJECT_ROOT),
            "LEAN_LOG_LEVEL": "NONE",
        },
    },
        cache_tools_list=True,
        client_session_timeout_seconds=200,
        max_retry_attempts=4,
        retry_backoff_seconds_base=1.5,
    )
    async with lean_mcp_server:
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
            mcp_servers = [lean_mcp_server],
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
            mcp_servers = [lean_mcp_server],
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
            mcp_servers = [lean_mcp_server],
            handoff_description="Generates the initial LeanArchitect blueprint skeleton and checks it with Lean MCP."
           
        )
        #configure the input
        input = TheoremState(
            user_input = "Prove the theorem given and use the lean file given with the workspace path to prove it.",
            theorem = """If a function f(x) is continuous on a closed interval [a,b], then f(x) has both a maximum and a minimum on [a,b]. If f(x) has an extremum on an open interval (a,b), then the extremum occurs at a critical point""",
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

        quality_issues = blueprint_quality_issues(workspace_text())
        if quality_issues:
            last_result = await run_stage(
                blueprint_refinement_agent,
                f"""
                The generated blueprint is unacceptable and must be repaired before proving.
                User theorem:
                {input.theorem}

                Quality issues:
                {chr(10).join(f"- {issue}" for issue in quality_issues)}
                
                Rewrite `{WORKSPACE_PATH}` so it uses real LeanArchitect (`import Architect`), contains no fake `blueprint` or `sorry_using` definitions, and has a faithful non-vacuous main theorem. Do not change the problem to `True`. Use `write_workspace`, then call `lean_diagnostic_messages` with file_path `{WORKSPACE_PATH}`.""",
                max_turns=None,
            )
            quality_issues = blueprint_quality_issues(workspace_text())
            if quality_issues:
                print("Pipeline stopped: blueprint quality issues remain.")
                for issue in quality_issues:
                    print(f"- {issue}")
                print("Last result:", last_result)
                return

        last_result = ""
        for attempt in range(1, 4):
            quality_issues = blueprint_quality_issues(workspace_text())
            if quality_issues:
                last_result = await run_stage(
                    blueprint_refinement_agent,
                    f"""Attempt {attempt}: repair blueprint quality issues in `{WORKSPACE_PATH}` before proving.
                    User theorem:
                    {input.theorem}
                    Quality issues:
                    {chr(10).join(f"- {issue}" for issue in quality_issues)}

                    Do not weaken the theorem. Remove fake LeanArchitect replacements. Use real `import Architect`.
                    Use `write_workspace`, then call `lean_diagnostic_messages` with file_path `{WORKSPACE_PATH}`.
                    """,
                    max_turns=None,
                )
                if blueprint_quality_issues(workspace_text()):
                    continue

            if not has_incomplete_proofs(workspace_text()):
                quality_issues = blueprint_quality_issues(workspace_text())
                if quality_issues:
                    print("Pipeline stopped: no sorries remain, but blueprint is unacceptable.")
                    for issue in quality_issues:
                        print(f"- {issue}")
                    return
                print("No textual `sorry` remains, but verification has not been confirmed. Continuing with Theorem Prover.")

            last_result = await run_stage(
                theorem_proving_agent,
                f"""
                Attempt {attempt}: prove the blueprint declarations in `{WORKSPACE_PATH}`.
                Input state: {state_json}
                Use `read_workspace`, edit the file with `write_workspace`, then call
                `lean_diagnostic_messages` with file_path `{WORKSPACE_PATH}`.
                You must call `lean_verify` before claiming success. If the proof is too hard,
                leave the failing node incomplete and return the Too-hard protocol diagnosis.
                """,
                max_turns=None,
            )

            quality_issues = blueprint_quality_issues(workspace_text())
            if quality_issues:
                last_result = await run_stage(
                    blueprint_refinement_agent,
                    f"""The theorem prover produced an unacceptable result.
                    User theorem:{input.theorem}

                    Quality issues:{chr(10).join(f"- {issue}" for issue in quality_issues)}
                    Restore a faithful theorem and blueprint. Do not solve by weakening to `True`.
                    Use `write_workspace`, then call `lean_diagnostic_messages` with file_path `{WORKSPACE_PATH}`.
                    """,
                    max_turns=None,
                )
                continue

            if reports_verified(last_result):
                print("Pipeline finished: theorem prover reported Lean verification success.")
                return

            last_result = await run_stage(
                blueprint_refinement_agent,
                f"""Attempt {attempt}: the theorem prover did not provide Lean verification success. Refine the blueprint in `{WORKSPACE_PATH}`.
                Use this prover result as diagnostic context:{last_result}
                Keep the main theorem statement unchanged. Use `write_workspace`, then call `lean_diagnostic_messages` with file_path `{WORKSPACE_PATH}`.
                """,
                max_turns=None,
            )

        print("Pipeline stopped: reached maximum prove/refine attempts.")
        print("Last result:", last_result)
    
if __name__ == "__main__":
    asyncio.run(main())
