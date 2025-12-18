// oh man, whats for dinner??
import OpenAI from "openai";
import * as fs from "fs";
import * as readline from "readline";

const client = new OpenAI();

const tools: OpenAI.ChatCompletionTool[] = [
  {
    type: "function",
    function: {
      name: "read_file",
      description: "Read the contents of a file",
      parameters: {
        type: "object",
        properties: { path: { type: "string" } },
        required: ["path"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "list_directory",
      description: "List files and directories in a path",
      parameters: {
        type: "object",
        properties: { path: { type: "string" } },
      },
    },
  },
];

function readFile(path: string): string {
  return fs.readFileSync(path, "utf-8");
}

function listDirectory(path: string = "."): string {
  return fs.readdirSync(path).join("\n");
}

async function run(prompt: string) {
  const messages: OpenAI.ChatCompletionMessageParam[] = [
    { role: "user", content: prompt },
  ];

  while (true) {
    const response = await client.chat.completions.create({
      model: "gpt-4o",
      messages,
      tools,
    });

    const msg = response.choices[0].message;

    if (!msg.tool_calls) {
      console.log(msg.content);
      break;
    }

    messages.push(msg);
    for (const tc of msg.tool_calls) {
      const name = tc.function.name;
      const args = JSON.parse(tc.function.arguments);
      console.log(`[${name}]`, args);

      let result: string;
      if (name === "read_file") {
        result = readFile(args.path);
      } else if (name === "list_directory") {
        result = listDirectory(args.path ?? ".");
      } else {
        result = "Unknown tool";
      }

      console.log(`  -> ${result.slice(0, 100)}${result.length > 100 ? "..." : ""}\n`);
      messages.push({ role: "tool", tool_call_id: tc.id, content: result });
    }
  }
}

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

function prompt() {
  rl.question("> ", async (input) => {
    if (input.trim()) {
      await run(input);
    }
    prompt();
  });
}

prompt();
