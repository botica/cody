
import OpenAI from "openai";
import * as fs from "fs";
import * as path from "path";
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
  {
    type: "function",
    function: {
      name: "search",
      description:
        "Search for a pattern in files. Returns matching lines with file paths and line numbers.",
      parameters: {
        type: "object",
        properties: {
          pattern: {
            type: "string",
            description: "The regex pattern to search for",
          },
          path: {
            type: "string",
            description: "Directory to search in (default: current directory)",
          },
          file_pattern: {
            type: "string",
            description: "Glob pattern for files to search (e.g., '*.py', '*.txt')",
          },
        },
        required: ["pattern"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "write_file",
      description: "Create a new file or overwrite an existing file with content",
      parameters: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description: "Path to the file to create/overwrite",
          },
          content: {
            type: "string",
            description: "Content to write to the file",
          },
        },
        required: ["path", "content"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "edit_file",
      description:
        "Edit a file by replacing a specific string with new content. The old_string must match exactly.",
      parameters: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description: "Path to the file to edit",
          },
          old_string: {
            type: "string",
            description: "The exact string to find and replace",
          },
          new_string: {
            type: "string",
            description: "The string to replace it with",
          },
        },
        required: ["path", "old_string", "new_string"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "delete_file",
      description: "Delete a file or empty directory",
      parameters: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description: "Path to the file or empty directory to delete",
          },
        },
        required: ["path"],
      },
    },
  },
];

function readFileTool(p: string): string {
  try {
    return fs.readFileSync(p, "utf-8");
  } catch (e: any) {
    if (e?.code === "ENOENT") return `Error: File not found: ${p}`;
    return `Error reading file: ${e?.message ?? String(e)}`;
  }
}

function listDirectoryTool(p: string = "."): string {
  const dir = p && p.trim() ? p : ".";
  try {
    return fs.readdirSync(dir).join("\n");
  } catch (e: any) {
    if (e?.code === "ENOENT") return `Error: Directory not found: ${dir}`;
    return `Error listing directory: ${e?.message ?? String(e)}`;
  }
}

function globToRegExp(glob: string): RegExp {
  // Very small glob implementation: supports *, ?, and treats path separators literally.
  const escaped = glob
    .replace(/[.+^${}()|[\]\\]/g, "\\$&")
    .replace(/\*/g, ".*")
    .replace(/\?/g, ".");
  return new RegExp(`^${escaped}$`, "i");
}

function walkFiles(rootDir: string): string[] {
  const out: string[] = [];

  function walk(current: string) {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch {
      return;
    }

    for (const ent of entries) {
      const full = path.join(current, ent.name);
      if (ent.isDirectory()) {
        walk(full);
      } else if (ent.isFile()) {
        out.push(full);
      }
    }
  }

  walk(rootDir);
  return out;
}

function searchTool(pattern: string, p: string = ".", filePattern?: string): string {
  const root = p && p.trim() ? p : ".";

  let regex: RegExp;
  try {
    regex = new RegExp(pattern, "i");
  } catch (e: any) {
    return `Invalid regex pattern: ${e?.message ?? String(e)}`;
  }

  let fileFilter: RegExp | null = null;
  if (filePattern && filePattern.trim()) {
    fileFilter = globToRegExp(filePattern.trim());
  }

  const results: string[] = [];
  const files = walkFiles(root);

  for (const filePath of files) {
    if (fileFilter && !fileFilter.test(path.basename(filePath))) continue;

    let content: string;
    try {
      content = fs.readFileSync(filePath, "utf-8");
    } catch {
      continue;
    }

    const lines = content.split(/\r?\n/);
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (regex.test(line)) {
        results.push(`${filePath}:${i + 1}: ${line}`);
        if (results.length >= 50) {
          results.push("... (truncated, more results available)");
          return results.join("\n");
        }
      }
    }
  }

  if (results.length === 0) return "No matches found";
  return results.join("\n");
}

function writeFileTool(p: string, content: string): string {
  try {
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(p, content, "utf-8");
    return `Successfully wrote ${Buffer.byteLength(content, "utf-8")} bytes to ${p}`;
  } catch (e: any) {
    return `Error writing file: ${e?.message ?? String(e)}`;
  }
}

function editFileTool(p: string, oldString: string, newString: string): string {
  try {
    const content = fs.readFileSync(p, "utf-8");

    const idx = content.indexOf(oldString);
    if (idx === -1) return `Error: old_string not found in ${p}`;

    const count = content.split(oldString).length - 1;
    if (count > 1) {
      return `Error: old_string appears ${count} times in ${p}. Must be unique.`;
    }

    const newContent = content.replace(oldString, newString);
    fs.writeFileSync(p, newContent, "utf-8");
    return `Successfully edited ${p}`;
  } catch (e: any) {
    if (e?.code === "ENOENT") return `Error: File not found: ${p}`;
    return `Error editing file: ${e?.message ?? String(e)}`;
  }
}

function deleteFileTool(p: string): string {
  try {
    const st = fs.statSync(p);
    if (st.isFile()) {
      fs.unlinkSync(p);
      return `Successfully deleted file: ${p}`;
    }
    if (st.isDirectory()) {
      fs.rmdirSync(p);
      return `Successfully deleted directory: ${p}`;
    }
    return `Error: Path not found: ${p}`;
  } catch (e: any) {
    if (e?.code === "ENOENT") return `Error: Path not found: ${p}`;
    return `Error deleting: ${e?.message ?? String(e)}`;
  }
}

function executeTool(name: string, args: any): string {
  if (name === "read_file") return readFileTool(args.path);
  if (name === "list_directory") return listDirectoryTool(args.path ?? ".");
  if (name === "search") return searchTool(args.pattern, args.path ?? ".", args.file_pattern);
  if (name === "write_file") return writeFileTool(args.path, args.content);
  if (name === "edit_file") return editFileTool(args.path, args.old_string, args.new_string);
  if (name === "delete_file") return deleteFileTool(args.path);
  return `Unknown tool: ${name}`;
}

async function run(promptText: string) {
  const messages: OpenAI.ChatCompletionMessageParam[] = [
    { role: "user", content: promptText },
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

      const result = executeTool(name, args);

      console.log(
        `  -> ${result.slice(0, 100)}${result.length > 100 ? "..." : ""}\n`,
      );
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
