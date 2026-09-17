import asyncio
from app.services.llm import llm_service

def test():
    query = "list all the games whith creed in there name?"
    text = """
*Pc Games List*

A Plague Tale Innocence
Age of Empires 4
Alan Wake 2
Alan Wake Remastered
Alone in the Dark (2024)
Assassin's Creed 2
7. Assassin's Creed 3
8. Assassin's Creed 4 Black Flag
9. Assassin's Creed Odyssey
10. Assassin's Creed Origins
11. Assassin's Creed Unity
12. Assassin's Creed Valhalla
13. Baldur's Gate 3
    """
    
    contexts = [{"text": text, "filename": "test.txt", "summary": "A list of PC games."}]
    
    print("Testing generate_rag_answer:")
    res = llm_service.generate_rag_answer(query, contexts)
    print(res)

    print("\nTesting generate_rag_stream:")
    for chunk in llm_service.generate_rag_stream(query, contexts):
        print(chunk)

if __name__ == "__main__":
    test()
