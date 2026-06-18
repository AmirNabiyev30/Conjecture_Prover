import asyncio

from agents import Agent,Runner
from agents.mcp import MCPServerStdio


async def main():
    async with MCPServerStdio(name = "Filesystem MCP", params ={
        "command":"node",
        "args":["/Users/amirnabiyev/Conjecture Prover/filesystem-mcp-server/dist/index.js"],
    }) as codex_mcp_server:
        print("MCP Server started")
        #describe our agents now
        result = await codex_mcp_server.list_tools()
        print(f"Available tools: {result}")
        #Formalizer Agent: Agent will take user input and formalize into lean verifiable code
        return
if __name__ == "__main__":
    asyncio.run(main())

