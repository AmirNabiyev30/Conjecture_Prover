import os
import asyncio
from pathlib import Path
import subprocess
from agents import function_tool

from dotenv import load_dotenv

@function_tool
def read_file(path: str) -> str:
    return Path(path).read_text()

@function_tool
def write_file(path: str, content: str) -> str:
    Path(path).write_text(content)
    return "written"
WORKSPACE = Path("input.lean")
@function_tool
def compile_lean(my_field: str = "") -> str:
    """
    Compiles the Lean project at the given path and returns the output.
    """
    result = subprocess.run(
        ["lake", "build"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True
    )
    return result.stdout + "\n" + result.stderr

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
        "args":["/Users/amirnabiyev/Conjecture Prover/filesystem-mcp-server/dist/index.js"],
    })
    async with (codex_mcp_server, filesystem_mcp_server):
        """
        We will have 3 agents for this workflow:
        -Formalizer Agent: Converts NL to Lean code
        -Decomposer Agent: Decomposes Lean code into smaller lemmas to make proof less complex
        -Prover Agent: Tries to prove the lemmas and the main theorem, if it fails, it will notify human with proof attempt
        """
        formalizer_agent  = Agent(
            name = "Formalizer",
            instructions = RECOMMENDED_PROMPT_PREFIX + Path("agents/formalizer.md").read_text(),
            tools = [WebSearchTool(), read_file, write_file, compile_lean],
            model = "gpt-5-nano",
            mcp_servers = [codex_mcp_server],
        )

        result = await Runner.run(formalizer_agent,"List at input theorem in input.lean file", max_turns=5)
    
if __name__ == "__main__":
    asyncio.run(main())
