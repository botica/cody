import json
import os
from openai import OpenAI

client = OpenAI()

tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in a path",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}}
            }
        }
    }
]


def read_file(path):
    with open(path) as f:
        return f.read()


def list_directory(path="."):
    return "\n".join(os.listdir(path))


def run(prompt):
    messages = [{"role": "user", "content": prompt}]

    while True:
        response = client.chat.completions.create(
            model="gpt-4o", messages=messages, tools=tools
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            print(msg.content)
            break

        messages.append(msg)
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            print(f"[{name}] {args}")

            if name == "read_file":
                result = read_file(args["path"])
            elif name == "list_directory":
                result = list_directory(args.get("path", "."))

            print(f"  -> {result[:100]}{'...' if len(result) > 100 else ''}\n")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})


if __name__ == "__main__":
    while True:
        try:
            prompt = input("> ")
            if prompt.strip():
                run(prompt)
        except (KeyboardInterrupt, EOFError):
            break
