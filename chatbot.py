import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango, GdkPixbuf
import subprocess
import threading
import re
import os
from datetime import datetime
import signal
import sys

class ChatGPTApp(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="ChatGPT")
        self.set_default_size(800, 600)
        self.set_border_width(10)

        # File to save chat history (plain text format)
        self.chat_history_file = "chat_history.txt"
        self.temp_history_file = "chat_history.tmp"

        # Dark theme CSS 
        css = b"""
        * {
            background-color: #1e1e1e;
            color: #e0e0e0;
            font-family: 'Segoe UI', sans-serif;
        }
        
        .user-message {
            background: linear-gradient(135deg, #6e48aa, #9d50bb);
            color: white;
            border-radius: 15px 15px 0 15px;
            padding: 12px 16px;
            margin: 8px 80px 8px 40px;
            border: 1px solid #6e48aa;
        }
        
        .bot-message {
            background-color: #2d2d2d;
            color: #e0e0e0;
            border-radius: 15px 15px 15px 0;
            padding: 12px 16px;
            margin: 8px 40px 8px 80px;
            border: 1px solid #444444;
        }
        
        .loading-message {
            color: #9a9a9a;
            font-style: italic;
            margin-left: 85px;
            font-size: 0.9em;
        }
        
        .session-start {
            color: #9a9a9a;
            font-size: 0.8em;
            margin: 10px 0;
        }
        
        GtkEntry {
            background-color: #2d2d2d;
            color: #e0e0e0;
            border-radius: 25px;
            padding: 12px 20px;
            border: 1px solid #444444;
            font-size: 14px;
            margin-right: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        GtkEntry:focus {
            border-color: #007bff;
        }
        
        GtkButton {
            background: linear-gradient(135deg, #007bff, #0056b3);
            color: white;
            border-radius: 25px;
            padding: 12px 24px;
            border: none;
            font-weight: bold;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.2s ease;
        }
        
        GtkButton:hover {
            background: linear-gradient(135deg, #0056b3, #003f7f);
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }
        
        GtkScrolledWindow {
            border-radius: 10px;
            background-color: #2d2d2d;
            margin-bottom: 15px;
            border: 1px solid #444444;
        }
        
        .input-container {
            background-color: #2d2d2d;
            border-radius: 25px;
            padding: 8px;
            margin: 0 20px 20px 20px;
            border: 1px solid #444444;
        }
        
        .image-button-active {
            background: linear-gradient(135deg, #90EE90, #32CD32);
            color: white;
            border-radius: 25px;
            padding: 12px 24px;
            border: none;
            font-weight: bold;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.2s ease;
        }
        
        .chat-image {
            margin: 10px 40px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        """
        
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Main container
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(self.main_box)

        # Chat history area
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.main_box.pack_start(self.scrolled_window, True, True, 0)

        self.chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.scrolled_window.add(self.chat_box)

        # Input container
        input_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        input_container.get_style_context().add_class("input-container")
        self.main_box.pack_start(input_container, False, False, 0)

        # Image button (toggle for tgpt -img)
        self.image_button = Gtk.Button(label="Image")
        self.image_button.connect("clicked", self.on_image_button_clicked)
        input_container.pack_start(self.image_button, False, False, 0)

        # Input area
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Write a message...")
        self.entry.set_hexpand(True)
        self.entry.connect("activate", self.on_send_clicked)
        input_container.pack_start(self.entry, True, True, 0)

        # Send button
        self.send_button = Gtk.Button(label="Send")
        self.send_button.connect("clicked", self.on_send_clicked)
        input_container.pack_start(self.send_button, False, False, 0)

        # Loading state
        self.loading = False
        self.loading_message = None

        # Chat history 
        self.chat_history = []

        # Load the last few lines of chat history
        self.load_chat_history_lazy()

        # session start time for the current session
        self.start_new_session()

        signal.signal(signal.SIGINT, self.on_keyboard_interrupt)

        self.connect("delete-event", self.on_window_close
                
        self.image_mode_active = False

    def on_window_close(self, widget, event):
        """window close event."""
        self.save_chat_history()
        Gtk.main_quit()
        return False

    def on_keyboard_interrupt(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        print("\nExiting gracefully...")
        self.save_chat_history()
        Gtk.main_quit()
        sys.exit(0)

    def start_new_session(self):
        """Start a new session with a timestamp."""
        session_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.current_session = {
            "timestamp": session_timestamp,
            "messages": []
        }
        self.chat_history.append(self.current_session)
        self.add_session_start_time(session_timestamp)

    def add_session_start_time(self, timestamp):
        """centered timestamp for the start of the session."""
        session_start_label = Gtk.Label(label=f"--- Session started at {timestamp} ---")
        session_start_label.set_halign(Gtk.Align.CENTER)  # Center-align the label
        session_start_label.get_style_context().add_class("session-start")
        self.chat_box.pack_start(session_start_label, False, False, 0)
        session_start_label.show_all()

    def load_chat_history_lazy(self, lines_to_load=20):
        """Load the last few lines of chat history, including images."""
        if os.path.exists(self.chat_history_file):
            try:
                with open(self.chat_history_file, "r") as file:
                    lines = file.readlines()
                    # Parse sessions from the file
                    current_session = None
                    for line in lines:
                        if line.startswith("--- Session started at"):
                            # New session
                            timestamp = line.strip().replace("--- Session started at ", "").replace(" ---", "")
                            current_session = {
                                "timestamp": timestamp,
                                "messages": []
                            }
                            self.chat_history.append(current_session)
                            # session start time to the UI
                            self.add_session_start_time(timestamp)
                        else:
                            # Message in the current session
                            if current_session:
                                try:
                                    timestamp, sender, text = line.strip().split(" | ")
                                    text = text.replace("\\n", "\n")
                                    current_session["messages"].append({
                                        "timestamp": timestamp,
                                        "is_user": sender == "user",
                                        "text": text
                                    })
                                    # Add message or image to the UI
                                    if text.startswith("Generated image:"):
                                        image_name = text.replace("Generated image: ", "").strip()
                                        image_path = os.path.join(os.path.expanduser("~/chatgpt/images"), image_name)
                                        if os.path.exists(image_path):
                                            self.add_image_to_chat(image_path)
                                    else:
                                        self._add_message_to_chat_box(text, sender == "user")
                                except ValueError:
                                    print(f"Skipping invalid line: {line.strip()}")
            except Exception as e:
                print(f"Error loading chat history: {e}. Resetting chat history.")
                self.chat_history = []
                self.save_chat_history()
        else:
            self.chat_history = []

    def _add_message_to_chat_box(self, text, is_user):
        """Helper method to add messages to the chat box without timestamps."""
        message_bubble = self.create_message_bubble(text, is_user)
        self.chat_box.pack_start(message_bubble, False, False, 0)
        message_bubble.show_all()
        self.scroll_to_bottom()

    def save_chat_history(self):
        """Save the current chat history to a plain text file, including image references."""
        try:
            with open(self.temp_history_file, "w") as file:
                for session in self.chat_history:
                    file.write(f"--- Session started at {session['timestamp']} ---\n")
                    for message in session["messages"]:
                        sender = "user" if message["is_user"] else "bot"
                        text = message["text"].replace("\n", "\\n")
                        file.write(f"{message['timestamp']} | {sender} | {text}\n")
            os.replace(self.temp_history_file, self.chat_history_file)
        except Exception as e:
            print(f"Error saving chat history: {e}")

    def add_message_to_chat_box(self, text, is_user=True):
        """Add a new message to the chat box and save it to the history."""
        self._add_message_to_chat_box(text, is_user)
        
        new_message = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "is_user": is_user,
            "text": text
        }
        self.current_session["messages"].append(new_message)
        self.save_chat_history()

    def create_message_bubble(self, text, is_user=True):
        """Create a message bubble without timestamps."""
        lines = text.split("\n")
        formatted_lines = []
        
        for line in lines:
            if line.startswith("### "):
                line = line.replace("### ", "<b><span foreground='#000000' size='x-large'>", 1) + "</span></b>"
                formatted_lines.extend(["", line, ""])
            else:
                formatted_lines.append(line)
        
        formatted_text = "\n".join(formatted_lines)
        
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.END if is_user else Gtk.Align.START,
            spacing=10
        )
        label = Gtk.Label()
        label.set_markup(formatted_text)
        label.set_line_wrap(True)
        label.set_max_width_chars(60)
        label.set_selectable(True)
        label.get_style_context().add_class("user-message" if is_user else "bot-message")
        box.pack_start(label, False, False, 0)
        return box

    def create_loading_message(self):
        """Create a loading message."""
        box = Gtk.Box(halign=Gtk.Align.START)
        label = Gtk.Label(label="RukoZAraaa...SAbarKAroo....!!!")
        label.get_style_context().add_class("loading-message")
        box.pack_start(label, False, False, 0)
        return box

    def create_image_widget(self, image_path):
        """Create a widget to display the generated image."""
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                image_path, 
                width=400, 
                height=300, 
                preserve_aspect_ratio=True
            )
            image = Gtk.Image.new_from_pixbuf(pixbuf)
            image.get_style_context().add_class("chat-image")
            return image
        except Exception as e:
            print(f"Error loading image: {e}")
            return None

    def add_image_to_chat(self, image_path):
        """Add an image to the chat box."""
        image_widget = self.create_image_widget(image_path)
        if image_widget:
            box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                halign=Gtk.Align.START,
                spacing=10
            )
            box.pack_start(image_widget, False, False, 0)
            self.chat_box.pack_start(box, False, False, 0)
            box.show_all()
            self.scroll_to_bottom()

    def on_send_clicked(self, widget):
        """Handle the send button click or Enter key press."""
        user_input = self.entry.get_text().strip()
        if not user_input:
            return

        self.entry.set_text("")
        self.add_message_to_chat_box(user_input, is_user=True)

        self.loading = True
        self.loading_message = self.create_loading_message()
        self.chat_box.pack_start(self.loading_message, False, False, 0)
        self.loading_message.show_all()

        GLib.idle_add(self.scroll_to_bottom)
        threading.Thread(target=self.run_tgpt_command, args=(user_input,), daemon=True).start()

    def on_image_button_clicked(self, widget):
        """Toggle the image mode on/off."""
        self.image_mode_active = not self.image_mode_active
        if self.image_mode_active:
            self.image_button.get_style_context().add_class("image-button-active")
        else:
            self.image_button.get_style_context().remove_class("image-button-active")

    def run_tgpt_command(self, user_input):
        """Run the tgpt command and handle the output."""
        try:
            if self.image_mode_active:
                command = ["tgpt", "-img", user_input]
                # Create images directory if it doesn't exist
                images_dir = os.path.expanduser("~/chatgpt/images")
                os.makedirs(images_dir, exist_ok=True)
                # Run command in the images directory
                process = subprocess.Popen(command, 
                                         stdout=subprocess.PIPE, 
                                         stderr=subprocess.PIPE,
                                         cwd=images_dir)
            else:
                command = ["tgpt", user_input]
                process = subprocess.Popen(command, 
                                         stdout=subprocess.PIPE, 
                                         stderr=subprocess.PIPE)

            stdout, stderr = process.communicate()
            output = self.clean_output(stdout.decode("utf-8"))
            error = stderr.decode("utf-8")
            
            print(f"Output: {output}")
            print(f"Error: {error}")
            
            GLib.idle_add(self.show_response, output, error)
        except Exception as e:
            print(f"Error executing command: {e}")
            GLib.idle_add(self.show_error, str(e))

    def clean_output(self, text):
        """Clean the output from tgpt."""
        text = re.sub(r'⣾|⣽|⣻|⢿|⡿|⣟|⣯|⣷|Loading', '', text)
        text = re.sub(r'\n\s*\n', '\n', text)
        return text.strip()

    def show_response(self, output, error):
        """Display the bot's response or image."""
        if self.loading_message and self.loading_message.get_parent():
            self.chat_box.remove(self.loading_message)
        self.loading = False
        
        # Check if the output contains an image filename
        image_match = re.search(r'Saved image as (\S+\.jpg)', output)
        if image_match:
            image_name = image_match.group(1)
            image_path = os.path.join(os.path.expanduser("~/chatgpt/images"), image_name)
            if os.path.exists(image_path):
                self.add_image_to_chat(image_path)
               
            else:
                self.add_message_to_chat_box("Error: Image file not found", is_user=False)
        else:
            response = f"Error: {error}" if error else output or "No response received"
            self.add_message_to_chat_box(response, is_user=False)

    def show_error(self, error):
        """Display an error message."""
        if self.loading_message and self.loading_message.get_parent():
            self.chat_box.remove(self.loading_message)
        self.loading = False
        self.add_message_to_chat_box(f"Error: {error}", is_user=False)

    def scroll_to_bottom(self):
        """Scroll the chat window to the bottom."""
        adj = self.scrolled_window.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())

if __name__ == "__main__":
    win = ChatGPTApp()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
