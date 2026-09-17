import asyncio
from app.services.llm import llm_service

def test():
    query = "list of all the games with creed?"
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
    
    prompt = f"""Read the following document context carefully. Answer the question specifically using the data provided.
If the question asks for a list or multiple items, you must provide all matching items.

Context:
{text}

Question: {query}
Answer:"""

    if llm_service._is_available():
        inputs = llm_service._tokenizer(prompt, return_tensors="pt").to(llm_service._model.device)
        outputs = llm_service._model.generate(**inputs, max_new_tokens=512)
        answer = llm_service._tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
        print("Test Prompt 4 Answer:", answer)

if __name__ == "__main__":
    test()
