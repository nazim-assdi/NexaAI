# Nexa AI Plugin Author Guide

Create a folder containing `plugin.json` and `plugin.py`, then ZIP the folder and import the ZIP from **Plugin Manager → Import plugin ZIP**.

Example manifest:

```json
{
  "id": "example-plugin",
  "name": "Example Nexa Plugin",
  "category": "Example",
  "description": "A minimal user-imported extension for Nexa AI.",
  "entrypoint": "plugin.py"
}
```

Example entrypoint:

```python
def register(context):
    context.add_command("example.hello", lambda: "Hello from Nexa")
```

The plugin host context currently exposes:
- `context.data_dir`: the local NexaAI data directory.
- `context.add_command(name, handler)`: register a namespaced command handler.
- `context.add_panel(name, factory)`: register a UI panel factory for a host integration.

The plugin manager validates ZIP paths, limits uncompressed package size to 50 MB, stores extensions under `%LOCALAPPDATA%\NexaAI\Plugins`, and does not execute imported code until the user explicitly enables it.

**Security:** Python plugins can execute code with the same Windows permissions as Nexa AI. Import plugins only from developers you trust. Disable or remove a plugin you no longer use.
