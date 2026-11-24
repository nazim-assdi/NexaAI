def register(context):
    """Called only after the user enables this imported plugin."""
    context.add_command("example.hello", lambda: "Hello from the Nexa AI plugin system")
