<h1 align="center">patdb</h1>
<h2 align="center">A snappy + easy + pretty TUI debugger for Python.</h2>

- The only Python debugger to allow inspecting re-raised or grouped exceptions!
- Inspect frames in a full Python REPL, with syntax highlighting and autocompletion.
- Walk through the whole stack interactively.
- A snappy single-keystroke interface.
- Respects `__tracebackhide__` hidden frames.
- Usable inside `threading`, `asyncio`, and even `multiprocessing`.

<br>
<div align="center">
<div><em>Here we have a program that raises an error. So we display the <code>s</code>ource of the problem function, then walk the s<code>t</code>ack into the nested <code>__cause__</code> of the exception, display the <code>s</code>ource of the called function, and finally open an <code>i</code>nterpreter inside that frame.</em></div><br>
<img style="width: 70%;" src="https://github.com/patrick-kidger/patdb/blob/main/imgs/splash.png?raw=true" alt="Demo image">
</div>

## Installation

```
pip install patdb
```

## Usage

### To use this as your `breakpoint()`:

Set the environment variable `PYTHONBREAKPOINT=patdb.debug`, and then place a `breakpoint()` anywhere in your source code. (Or call `import patdb; patdb.debug()` directly yourself, [which is the same thing](https://peps.python.org/pep-0553/).)

### With `pytest`:

Pass the `--patdb` flag, e.g. `pytest test_foo.py --patdb`, to open the debugger on failure.

### To open a debugger 'post mortem', after an error hits the top level:

When running interactively: call `patdb.debug()` after the error has returned you to the REPL. (Or `breakpoint()` if you've set the environment variable as above.)  
When running code in a file: `python -m patdb foo.py`.  
When running code on the command line: `python -m patdb -c "import foo; foo.problematic_function()"`.

## Commands

```
j: down_frame        - Move one frame down.
k: up_frame          - Move one frame up.
J: down_callstack    - Move one callstack down.
K: up_callstack      - Move one callstack up.
s: show_function     - Show the current function's source code and interactively set breakpoints.
S: show_file         - Show the current file's source code and interactively set breakpoints.
t: stack             - Show all frames in all callstacks and interactively scroll through them.
p: print             - Pretty-prints the value of an expression.
P: print_long_arrays - Pretty-prints the value of an expression, without summarising arrays.
e: edit              - Open the current function in your `$EDITOR`.
i: interpret         - Open a Python interpreter in the current frame.
v: visibility        - Toggles skipping hidden frames when moving frames or callstacks.
c: continue          - Close the debugger and continue the program.
q: quit              - Quit the whole Python program.
?: help              - Display a list of all debugger commands.
```

These can be rebound, see 'configuration' below.

Here, a "callstack" refers to all of the frames in the traceback of a single exception, so e.g. `J` moves down to a nested exception.

## Configuration

<details>
<summary>The following environment variables are respected:</summary>

```
PATDB_CODE_STYLE
PATDB_EMPH_COLOR
PATDB_ERROR_COLOR
PATDB_INFO_COLOR
PATDB_PROMPT_COLOR

PATDB_DEPTH
PATDB_EDITOR

PATDB_KEY_{command name}, e.g. `PATDB_DOWN_FRAME`

COLORFGBG
EDITOR
PTPYTHON_CONFIG_HOME
```

- `PATDB_CODE_STYLE`: used by the `show_function` and `show_file` commands, as the colour theme for displaying code. Can be the name of any [Pygments style](https://pygments.org/styles/), to use as the theme for code. Defaults to `solarized-dark`.
- `PATDB_EMPH_COLOR`: the colour used to emphasise the file/function/lines when displaying location, e.g. in `File *foo.py*, at *some_fn* from *1*, line *2*`. Defaults to `#4cb066`.
- `PATDB_ERROR_COLOR`: the colour used to display the type of error e.g. in `*RuntimeError*: something went wrong`. Defaults to `#dc322f`.
- `PATDB_INFO_COLOR`: the colour used to display `patdb:` info prompts. Defaults to `#888888`.
- `PATDB_PROMPT_COLOR`: the color used to display the `patdb>` REPL prompt. Defaults to `#268bd2`.

- `PATDB_DEPTH`: controls the `patdb` prompt and the prompt of any nested `interpret`ers. By default it is just `patdb>` and `>>>` respectively. If you nest `patdb->interpret->patdb->...` then this environment variable will increment and successive prompts will appear as `patdb1>`, `1>>>`, `patdb2>` etc.
- `PATDB_EDITOR`: used by the `edit` command. If set then this command will call `$PATDB_EDITOR $filename $linenumber`. If not set then it will fall back to just `$EDITOR $filename`.

- `PATDB_KEY_{command name}`: this offers a way to rebind keys. For example `PATDB_KEY_DOWN_FRAME=d` to replace the default `j` with `d`.
    - Can require that a chain of keys is pressed by separating them with `+`. For example `PATDB_KEY_DOWN_FRAME=a+b` requires that `a` and then `b` be pressed to trigger that command.
    - Can accept multiple different key bindings for the same command by separating them with a `/`. For example `PATDB_KEY_DOWN_FRAME=j/d`.
    - Modifiers keys can be applied following [prompt_toolkit syntax](https://python-prompt-toolkit.readthedocs.io/en/master/pages/advanced_topics/key_bindings.html). In particular this treats `Control` as part of the same key, so that for example `c-x` is `Control x`. Meanwhile `Alt` is (in the usual way for terminals) treated as a separate key press of `escape`, so that for example `escape+d` is `Alt d` 
    - Overall, for example: `a/c-k+b/escape+l` means that any of `a`, or `Control k` followed by `b`, or `Alt l`, will trigger that keybind.
    - The full list of all keys is as follows. The group of keys starting `PATDB_KEY_SHOW_` correspond to the interactive commands within the `show_file` and `show_function` command. The group of keys starting `PATDB_KEY_STACK_` correspond to the interactive commands within the `stack` command.
        ```
        PATDB_KEY_DOWN_FRAME
        PATDB_KEY_UP_FRAME
        PATDB_KEY_DOWN_CALLSTACK
        PATDB_KEY_UP_CALLSTACK
        PATDB_KEY_SHOW_FUNCTION
        PATDB_KEY_SHOW_FILE
        PATDB_KEY_STACK
        PATDB_KEY_PRINT
        PATDB_KEY_PRINT_LONG_ARRAYS
        PATDB_KEY_EDIT
        PATDB_KEY_INTERPRET
        PATDB_KEY_VISIBILITY
        PATDB_KEY_CONTINUE
        PATDB_KEY_QUIT
        PATDB_KEY_HELP
        PATDB_KEY_SHOW_DOWN_LINE
        PATDB_KEY_SHOW_UP_LINE
        PATDB_KEY_SHOW_LEFT
        PATDB_KEY_SHOW_RIGHT
        PATDB_KEY_SHOW_DOWN_CALL
        PATDB_KEY_SHOW_SELECT
        PATDB_KEY_SHOW_LEAVE
        PATDB_KEY_STACK_DOWN_FRAME
        PATDB_KEY_STACK_UP_FRAME
        PATDB_KEY_STACK_DOWN_CALLSTACK
        PATDB_KEY_STACK_UP_CALLSTACK
        PATDB_KEY_STACK_LEFT
        PATDB_KEY_STACK_RIGHT
        PATDB_KEY_STACK_VISIBILITY
        PATDB_KEY_STACK_ERROR
        PATDB_KEY_STACK_COLLAPSE_SINGLE
        PATDB_KEY_STACK_COLLAPSE_ALL
        PATDB_KEY_STACK_SELECT
        PATDB_KEY_STACK_LEAVE
        ```

- `COLORFGBG`: some environments provide this to describe the colour of the terminal. If available, this will be queried to determine if your terminal is using a light or dark background. This is used to determine the fallback colour for any tokens not specified by the code style specified in `PATDB_CODE_STYLE`.
- `EDITOR`: used as a fallback if `PATDB_EDITOR` is not available.
- `PTPYTHON_CONFIG_HOME`: used by the `interpret` command. This command uses [`ptpython`](https://github.com/prompt-toolkit/ptpython) for the interpreter, and we respect any existing configuration you have configured for `ptpython`.
</details>

## FAQ

<details>
<summary>Why the name <code>patdb</code>?</summary>
<br>

The built-in debugger is called `pdb`, and my name is Patrick! 😁
</details>
<details>
<summary>Why this (fairly small) set of commands?</summary>
<br>

`patdb` was designed for its commands to be almost entirely be about understanding the stack trace. Once you're where you need to be, then hit `i` to open a REPL and start interacting with the variables directly.
</details>
<details>
<summary>How does <code>patdb</code> differ from <code>pdb</code>/... etc?</summary>

##### `pdb`/`pdb++`/`ipdb`?

We handle nested exceptions; scrolling through the stack; syntax highlighting; interacting with hidden frames; etc etc. (`ipdb` does offer a couple of those last ones as well.)

`patdb` largely aims to supersede these debuggers.

##### `pudb`?

We handle nested exceptions. The main difference, though, is that `pudb` offers a "graphical" interface, displaying information about variables / exceptions / code / etc. in multiple panes. This is a bit of a philosophical choice -- personally I prefer REPL-like interfaces, as these keep a history of all the things I've ever done, which I can go back and check if required. I find this particularly valuable when debugging! But others may prefer the graphical interface of `pudb`.
</details>

## Advanced usage

<details>
<summary>Can I customise the interpreter?</summary>
<br>

Yes! We use [`ptpython`](https://github.com/prompt-toolkit/ptpython) for our nested REPL, and will respect any `ptpython` configuration you already have.

Why not `ipython`? The reason is that I found `ipython` to be pretty unclear to work with. They have all of:

```
IPython.core.interactiveshell.InteractiveShell
IPython.terminal.interactiveshell.TerminalInteractiveShell
IPython.terminal.embed.InteractiveShellEmbed
```

and I couldn't easily figure out how to get any of them to operate correctly when embedded in a larger program. In contrast `ptpython` pretty much worked out-of-the-box!
</details>
</details>
<details>
<summary>When using <code>edit</code>, how can I open my <code>$EDITOR</code> to the current line number? (And not just the top of the current file.)</summary>
<br>

Set `PATDB_EDITOR` as discussed in 'configuration' above.
</details>
<details>
<summary>How can I access the current exception or the current frame?</summary>
<br>

When `p`rinting or `i`nteracting then the current exception is available as `__exception__` and the current frame is available as `__frame__`.
</details>
<details>
<summary>Investigating an existing exception, traceback, or frame object.</summary>
<br>

Call either `patdb.debug(some_exception)` or `patdb.debug(some_traceback)` or `patdb.debug(some_frame)` if you have a particular exception/traceback/frame that you'd like to investigate. Exceptions may potentially have multiple callstacks (subexceptions via `__cause__` and `__context__` are checked, with one callstack for each exception), the others will enable debugging of a single callstack.
</details>
<details>
<summary>Setting <code>sys.excepthook</code>.</summary>
<br>

By default, Python will call `sys.excepthook` on any exception that reaches the top of your program. In practice we usually recommend using `python -m patdb foo.py` as the way to open a debugger when an exception occurs, as unfortunately Python offers no easy way to set `sys.excepthook` from outside a program.

However if you can modify the top of your script, or if you use [`usercustomize.py`](https://docs.python.org/3/library/site.html#module-usercustomize), then another way to enable `patdb` is to set `sys.excepthook = patdb.debug` before any exceptions hit the top level.
</details>
