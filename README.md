<div align="center">
  <img src="./imgs/cody.png" width="128px">
</div>
<p>cody is a cl agent harnessing openrouter models</p>
<p>cody has these tools: read_file, list_directory, write_file, edit_file, delete_file, search, fetch_webpage, web_search, and run_bash</p>
<p>run as <code>python agent.py</code> after installing the dependencies in requirements.txt as well as <a href="https://github.com/BurntSushi/ripgrep">ripgrep</a></p>

### slash commands
- `/model` - list available models, and switch models  `/model <n>`
- `/clear` - clear session context
- `---` - enter this delimeter on its own line to paste in multiple lines at a time. then enter it again to stop.
- `ctrl-c` - kill cody

### confirmations
most tools require `y/n` confirmation. special inputs:
- `!` - auto-confirm for rest of turn
- `n` - deny the tool call and yield back to the input prompt (cody cancels any pending tool calls for that turn)

### flags
- `--yolo` - skip all confirmations for the session
- `--cwd <path>` or `-C <path>` - set a different working directory

### openrouter api key
on first run you will be prompted to paste in your API key, which can be created <a href="https://openrouter.ai/settings/keys">here</a>. If you want to update your key, it can then be found in `config.toml`.

### config
edit `config.toml` to add models, set pricing, toggle reasoning output, adjust cost limits, as well as modify the system prompt. models are listed on <a href="https://openrouter.ai/models">openrouter's site</a>

---
<img src="./imgs/screen5.png" width="800px">
<img src="./imgs/screen6.png" width="800px">
