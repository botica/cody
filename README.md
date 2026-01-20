<div align="center">
  <img src="./imgs/cody.png" width="128px">
</div>
<p>cody is a command-line agentic harness for openrouter models</p>
<p>cody has these tools: read_file, list_directory, write_file, edit_file, delete_file, search, fetch_webpage, web_search, and run_bash.</p>
<p>run as <code>python agent.py</code> after installing the dependencies in requirements.txt as well as <a href="https://github.com/BurntSushi/ripgrep">ripgrep</a></p>

### commands
- `/model` - list available models and switch (e.g. `/model 3`)
- `/clear` - clear conversation context and token counts
- `---` - start/end multi-line input mode
- `ctrl-c` - exit

### confirmations
most tools require `y/n` confirmation. special inputs:
- `!` - auto-confirm for rest of turn
- `b` - break back to input prompt

run with `--yolo` to skip all confirmations for the session.

### config
edit `config.toml` to add models, set pricing, toggle reasoning output, adjust cost limits, etc.

---
<img src="./imgs/screen3.png" width="800px">
<img src="./imgs/screen4.png" width="800px">

<p>The name 'Cody' comes from the 2003 movie, 'Agent Cody Banks', starring Frankie Muniz. Cody's design is heavily influenced by Claude, with its goal being simple/minimal code, robust tools, and an emphasis on functionality.</p>