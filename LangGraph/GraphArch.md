# How the LangGraph Architect is supposed to look like
The goal with this pipeline is to produce a lean verifiable proof of the an input theorem using the Goedel-Architecture
## Steps(Nodes in our graph)
##### 1. Take in a input theorem/conjecture and configurations
such as model, how many prover agents you want to run in parallel, token budget, etc... 
##### 2. Blueprint Generation
Decompose the main theorem into sub lemma's while verifying the lean file can compile in lean(using sorry's for lemma definitions)
##### 3. Theorem-Proving
Assign parallel agents to solve the sub lemmas and if correctly proved, mark it proved(using node colors), if the proof was too hard, then mark as failed to prove
##### 4. Synthesizer 
(CAN BE COMBINED WITH THEOREM-PROVING POSSIBLY)
Look at blueprint and examine blueprint if all lemmas were proved without using sorry's, if any lemmas were too hard send to blueprint refiner node. If all lemmas were proved, then end the loop and return the final state
##### 5. Blueprint Refiner
Examine lemmas that were marked as too hard and refine the blueprint file and decompose the failed lemma into smaller lemmas and once done send back to the theorem-proving agent


## Deep-Dive into the exact requirements for each node!
This section talks about the intentions of design for each node, like budget and maximum amount of iterations and also what LangGraph functions and ideas will be used

#### Overall Design:
I think a linear structure where the theorem proving node can fan out and in is a viable option
I also think an orchestrator structure might work but introduces more nondeterministic factors with LLM decisions
I think deterministic evaluators such as keyword checking for sorry's in the file is good first pass for determining if a theorem is proved, and then possibly LLM as a judge as a final check to evaluate of LLM's were incorrectly abstracted away using some easy construct

Each node in the lean file can be marked different colors for different stages of completion: (Done,Unfinished, Too Hard)

#### Input: 
The configs can be passed in as runtime context allowing for different models and selections for many prover agents
The input can be passed as natural language

#### Blueprint Generation:
Using a relatively smart llm, the task is for the llm to decompose the natural language input theorem(natural language proof could be provided) into a lean verifiable lemmas with the blueprint architect specifically using the LeanArchitect library, using tools, write to a lean file and verify that the lean builds and compiles

-Feature to possibly implement: LLM can query user for additional information regarding theorem

#### Theorem-Proving:
Possibly using send and parallel agents, fill out and solve the sublemma's, each agent can fail to prove a lemma where it can then mark node colors provide feedback on what it attempted and what next steps might be. Each agent will have a token budget and attempt maximum, after subagents are done, review the lean file for the quality of the proof, using keyword searches and LLM as a judge see if the blueprint needs to be refined, if so send state to blueprint refiner, if the proof is good then go to END

More Detail:
Parallel agents will run given a lemma for each agent, then they will suggest edits with a search and replace tool, then all these edits will be passed to an aggregator node

#### Aggregator 
Takes in edits for search and replace and correctly edits the lean file  and then will pass for sysnthesizing

#### Blueprint Refiner:
If activated, attempts to refine the blueprint where the lemmas are incomplete(using sorry or hallucination). Decomposes that lemma into even more sublemma's using the LeanArchitect library to maintain the blueprint configuration. After done, it will resend to the theorem prover.


## State Design
This sections talks about the shared state that will be utilized between nodes
-WorkSpace Path
-Content of Lean File
-Input Theorem

I think all that will be necessary, is the content of the current lean file, and the workspace path for the file, technically the content can be derived through tool use with the workspace path but I think to reduce tools calls, passing the content may be more efficient

## Tool Use:
I want to expose 2 mcp's
- One is a file system MCP(may not be necessary as I can just create the few tools I actually need)
- Lean MCP Server that exposes lean tools such as diagnostic checks, lean compile tools, library search tools(finding Mathlib definitions)

## Possible features
- Breakpoints
- Human in the loop

## Things to Note:
1. When graph hits token budgets, break and ask for human input to continue going
2. If the intital blueprint generation is hallucinated we want blueprint refiner to be able to understand that and generate a whole new blueprint if necessary


