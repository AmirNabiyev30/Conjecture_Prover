import os
import asyncio
from pathlib import Path
import subprocess
from agents import function_tool
from pydantic import BaseModel
from dotenv import load_dotenv


#configure state for theorems, agent can populate some fields

class theorem_state(BaseModel):
    theorem: str
    workspace_path: str
    errors_remaining: bool = True

from agents import (
    Agent,
    ModelSettings,
    Runner,
    WebSearchTool,
    set_default_openai_api,
)
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX
from agents.mcp import MCPServerStdio
from openai.types.shared import Reasoning


load_dotenv(override=True) # the override isnt strictly necessary since we aren't committing the .env file, but it doesn't hurt to be explicit

set_default_openai_api(os.getenv("OPENAI_API_KEY")) # gets api key for model usage

async def main() -> None:
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
        "args":["lean-lsp-mcp"]
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
            instructions = RECOMMENDED_PROMPT_PREFIX + Path("/Users/amirnabiyev/Conjecture_Prover/prompts/theorem_prover.md").read_text(),
            tools = [WebSearchTool()],
            model = "gpt-5-nano",
            mcp_servers = [codex_mcp_server,filesystem_mcp_server,lean_mcp_server],
            output_type = theorem_state
        )
        blueprint_refinement_agent = Agent(
            name = "Blueprint Refinement",
            instructions = RECOMMENDED_PROMPT_PREFIX + Path("/Users/amirnabiyev/Conjecture_Prover/prompts/blueprint_refiner.md").read_text(),
            tools = [WebSearchTool()],
            model = "gpt-5-nano",
            mcp_servers = [codex_mcp_server,filesystem_mcp_server,lean_mcp_server],
            output_type = theorem_state 
        )
        blueprint_generator_agent  = Agent(
            name = "Blueprint Generator",
            instructions = RECOMMENDED_PROMPT_PREFIX + Path("/Users/amirnabiyev/Conjecture_Prover/prompts/blueprint_generator.md").read_text(),
            tools = [WebSearchTool()],
            model = "gpt-5-nano",
            mcp_servers = [codex_mcp_server,filesystem_mcp_server,lean_mcp_server],
            output_type = theorem_state
        )
        #configure the input
        input = theorem_state(
            theorem = "Prove Prove the transitive property where if a = b and b = c, then a = c",
            workspace_path = "/Users/amirnabiyev/Conjecture_Prover/LeanWorkspace/input.lean"
        )
        #define the loop, where we will query each agent in turn, and if the theorem prover fails, we will refine the blueprint and try again
        MAX_ITERATIONS = 5
        for i in range(MAX_ITERATIONS):
            print(f"Iteration {i+1} of {MAX_ITERATIONS}")
            #generate the blueprint
            blueprint = await Runner.run(blueprint_generator_agent, input.model_dump_json())
            print(f"Blueprint generated: {blueprint}")
            #attempt to prove the theorem
            proof_attempt = await Runner.run(theorem_proving_agent, blueprint.model_dump_json())
            print(f"Proof attempt: {proof_attempt}")
            if proof_attempt.remaining_errors == False:
                print("Theorem proved successfully!")
                break
            else:
                print("Theorem proving failed, refining blueprint...")
                input = await Runner.run(blueprint_refinement_agent, proof_attempt.model_dump_json())

    
if __name__ == "__main__":
    asyncio.run(main())
