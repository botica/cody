<div align="center">
  <img src="./imgs/banks.png" alt="strap in" width="200px">
</div>
<p>cody is a command-line agentic harness for openrouter models</p>
<p>cody has these tools: read_file, list_directory, write_file, edit_file, delete_file, search, fetch_webpage, web_search, and run_bash.</p>
<p>run as <code>python agent.py</code> after installing the dependencies in requirements.txt as well as <a href="https://github.com/BurntSushi/ripgrep">ripgrep</a> (for search)</p>
<p>enter <code>'!'</code> instead of <code>y/n</code> to auto-confirm tools for the turn.</p>
<p>run with <code>--yolo</code> flag to auto confirm for session</p>
<p><code>/clear</code> deletes all context and token counts</p>
<p>if you need to paste multiple lines, enter <code>---</code> on its own line to begin multi-line input; end with  <code>---</code> on its own line.</p>
<p>ctrl-c kills the program.</p>
<p>edit config.toml to switch models, toggle reasoning output, etc.</p>
without reasoning:
<img src="./imgs/screen3.png" width="800px">
<br>
reasoning:
<img src="./imgs/screen4.png" width="800px">
