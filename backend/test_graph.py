from app.agents.orchestrator import get_chat_agent

def main():
    agent = get_chat_agent()
    print("Graph compiled successfully!")
    print("Nodes:", agent.get_graph().nodes)
    
if __name__ == "__main__":
    main()
