<div align="center">
  <img src="./imgs/cody.png" width="128px">
</div>
<p>cody is a command-line agent powered by local LLMs via Ollama</p>
<p>cody has these tools: read_file, list_directory, write_file, edit_file, delete_file, search, fetch_webpage, web_search, and run_bash.</p>

### setup
1. install [Ollama](https://ollama.com)
2. pull a model: `ollama pull llama3.1:8b`
3. install dependencies: `pip install -r requirements.txt`
4. install [ripgrep](https://github.com/BurntSushi/ripgrep)
5. run: `python agent.py`

### commands
- `/model` - list available models and switch (e.g. `/model 3`)
- `/clear` - clear conversation context and token counts
- `---` - start/end multi-line input mode (enter on its own line)
- `ctrl-c` - exit

### confirmations
most tools require `y/n` confirmation. special inputs:
- `!` - auto-confirm for rest of turn
- `b` - break back to input prompt

### flags
- `--yolo` - skip all confirmations for the session
- `--cwd <path>` or `-C <path>` - set a different working directory

### config
edit `config.toml` to add models, toggle reasoning output, and modify the system prompt. add any models you've pulled to `available_models` to enable switching.

---
<img src="./imgs/screen5.png" width="800px">
<img src="./imgs/screen6.png" width="800px">

<p>The name 'Cody' comes from the 2003 movie, 'Agent Cody Banks', starring Frankie Muniz. Cody's design is heavily influenced by Claude, with its goal being simple/minimal code, robust tools, and an emphasis on functionality.</p>
