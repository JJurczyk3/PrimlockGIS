"""Dual-terminal admin support."""

from dataclasses import dataclass
from queue import Queue
import socket
import socketserver
import threading


@dataclass
class CommandRequest:
    """A command sent from the admin terminal to the viewer."""
    text: str
    reply_queue: Queue[str]


class CommandServer(socketserver.ThreadingTCPServer):
    """Local TCP server used by the viewer to receive admin commands."""

    allow_reuse_address = True

    def __init__(self, server_address, handler_class, command_queue):
        super().__init__(server_address, handler_class)
        self.command_queue = command_queue


class CommandHandler(socketserver.StreamRequestHandler):
    """Handle one admin terminal connection."""

    def handle(self):
        for raw_line in self.rfile:
            text = raw_line.decode("utf-8").strip()

            if not text:
                continue

            reply_queue = Queue(maxsize=1)
            request = CommandRequest(
                text=text,
                reply_queue=reply_queue,
            )

            self.server.command_queue.put(request)

            try:
                response = reply_queue.get(timeout=2.0)
            except Exception:
                response = "ERROR: viewer did not respond"

            self.wfile.write((response + "\n").encode("utf-8"))
            self.wfile.flush()


def start_command_server(
        command_queue,
        host: str = "127.0.0.1",
        port: int = 8765,
) -> CommandServer:
    """Start the viewer command server in a background thread."""
    server = CommandServer(
        (host, port),
        CommandHandler,
        command_queue,
    )

    therad = threading.Thread(
        target=server.serve_forever,
        daemon=True,
    )
    therad.start()
    return server


def send_command(
        command: str,
        host: str = "127.0.0.1",
        port: int = 8765,
) -> str:
    """Send one command to the viewer and return the response."""
    with socket.create_connection((host, port), timeout=2.0) as sock:
        file = sock.makefile("rwb")

        file.write((command + "\n").encode("utf-8"))
        file.flush()

        response = file.readline().decode("utf-8").strip()
    return response


def run_admin_terminal(
        host: str = "127.0.0.1",
        port: int = 8765,
) -> None:
    """Run the admin command terminal."""
    print("Primelock GIS Admin Terminal")
    print("Type 'help' for commands. Type 'exit' to close this terminal.")
    print()

    while True:
        command = input("primelock> ").strip()

        if command in ("exit", "quit"):
            print("Closking admin terminal.")
            return
        
        if command == "help":
            print_help()
            continue

        if not command:
            continue

        try:
            response = send_command(command, host, port)
        except OSError as error:
            print(f"ERROR: could not connect to viewer: {error}")
            continue

        print(response)


def print_help() -> None:
    """Print available admin commands."""
    print("Commands:")
    print("  show grid")
    print("  hide grid")
    print("  toggle grid")
    print("  show tin")
    print("  hide tin")
    print("  toggle tin")
    print("  show points")
    print("  hide points")
    print("  toggle points")
    print("  reset")
    print("  summary")
    print("  query grid ROW COL")
    print("  quit viewer")