import os
import asyncio
from pathlib import Path
import subprocess
from agents import function_tool
from pydantic import BaseModel
from dotenv import load_dotenv


#configure state for theorems, agent can populate some fields

class theorem_state(BaseModel):
    user_input:str
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
            handoff_description="Once done hand back to the orchestrator agent"
        )
        blueprint_refinement_agent = Agent(
            name = "Blueprint Refinement",
            instructions = RECOMMENDED_PROMPT_PREFIX + Path("/Users/amirnabiyev/Conjecture_Prover/prompts/blueprint_refiner.md").read_text(),
            tools = [WebSearchTool()],
            model = "gpt-5-nano",
            mcp_servers = [codex_mcp_server,filesystem_mcp_server,lean_mcp_server],
            handoff_description="Once done hand back to the orchestrator agent"
          
        )
        blueprint_generator_agent  = Agent(
            name = "Blueprint Generator",
            instructions = RECOMMENDED_PROMPT_PREFIX + Path("/Users/amirnabiyev/Conjecture_Prover/prompts/blueprint_generator.md").read_text() + """\n\n You can look at 
            /Users/amirnabiyev/Conjecture_Prover/LeanWorkspace/Main.lean for an example on how to structure the blueprint.""",
            tools = [WebSearchTool()],
            model = "gpt-5-nano",
            mcp_servers = [codex_mcp_server,filesystem_mcp_server,lean_mcp_server],
            handoff_description="Once done hand back to the orchestrator agent"
           
        )
        orchestrator_agent = Agent(
            name = "Orchestrator",
            instructions = RECOMMENDED_PROMPT_PREFIX + """Your job is to manage execution flow by evaluating the current state of the Lean workspace file: /Users/amirnabiyev/Conjecture_Prover/LeanWorkspace/input.lean 
            1. If the workspace file does not contain a strategy/blueprint yet, hand off to the Blueprint Generator.
            2. If a blueprint exists but the theorem is unproven, hand off to the Theorem Prover.
            3. Use the Lean LSP tool to check for compilation errors. If the Theorem Prover leaves errors in the file, hand off to the Blueprint Refiner to adjust the strategy.
            4. If the Lean LSP reports 0 errors and the proof is complete, declare success and terminate.
            5.If agents talk to you regarding the names of lemmas or theorems, tell them they can use it
            6. If there is a issue regarding name convention, you have the freedom to say yes.

            The general workflow is as follows, Given a theorem, generate a blueprint using the blueprint generator agent, after that is done, assign the theorem proving agent to prove the blueprint,
            if the theorem prover agent fails, assign the blueprint refiner agent to refine the blueprint based on the theorem provers feedback,
            If the theorem prover success in proving, end the cycle and return a success output message
            
            CRITICAL: Sub-agents may try to talk to you instead of writing files. If an agent hands back control without modifying the workspace file or checking the LSP, immediately hand the task back to them with explicit commands to use their tools.""",
            tools = [WebSearchTool()],
            model = "gpt-5-nano",
            mcp_servers = [codex_mcp_server,filesystem_mcp_server,lean_mcp_server],
            handoffs = [blueprint_generator_agent, theorem_proving_agent, blueprint_refinement_agent],
        )
        #configure the input
        input = theorem_state(
            user_input = "Prove the theorem given and use the lean file given with the workspace path to prove it.",
            theorem = "Prove the transitive property where if a = b and b = c, then a = c",
            workspace_path = "/Users/amirnabiyev/Conjecture_Prover/LeanWorkspace/input.lean"
        )
        blueprint_generator_agent.handoffs=[orchestrator_agent]
        theorem_proving_agent.handoffs=[orchestrator_agent]
        blueprint_refinement_agent= [orchestrator_agent]
       
        result = await Runner.run(orchestrator_agent, input.model_dump_json(), max_turns = 30)

        print("Final Result:", result)
    
if __name__ == "__main__":
    asyncio.run(main())
