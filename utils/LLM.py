from groq import Groq

def findsolution(text):

    client = Groq()

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that provides solutions to farming related problems. Please provide detailed and practical solutions based on the user's query. Please ensure your responses are clear and actionable.And give short and to the point answers.",
            },
            {
                "role": "user",
                "content": text,
            }
        ],

        model="llama-3.3-70b-versatile"
    )

    return chat_completion.choices[0].message.content