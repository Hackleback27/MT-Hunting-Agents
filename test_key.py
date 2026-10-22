from dotenv import load_dotenv
import anthropic

load_dotenv()
client = anthropic.Anthropic()

reply = client.messages.create(
    model="claude-haiku-5-5",
    max_tokens=100,
    messages=[{"role": "user", "content": "Name one big-game species hunted in Montana. One sentence."}],
)

print(reply.content[0].text)
