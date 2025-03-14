import base64
import io
import os
import openai
import pyautogui
import threading
import time

from tkinter import Tk, ttk, Label, Canvas, Toplevel, Button
# Added: ScrolledText for scrollable text display
from tkinter.scrolledtext import ScrolledText
from pynput import keyboard


# Initialize OpenAI API client using the API key from environment variables
# Ensure your API key is set in the environment variables
openai.api_key = os.environ.get("OPENAI_API_KEY")


class ScreenMonitorTool:
    """
    A tool for monitoring the screen, capturing screenshots, and analyzing image content using OpenAI's API.

    Attributes:
        master (Tk): The main window of the application.
        label_info (Label): Label displaying instructions to the user.
        output_label (Label): Label for the output section.
        output_text_box (ScrolledText): Scrollable text box to display analysis results.
        capture_button (Button): Button to initiate screenshot capture.
        progress (ttk.Progressbar): Progress bar indicating ongoing processes.
        listener (keyboard.Listener): Listener for keyboard events.
    """

    def __init__(self, master):
        """
        Initializes the ScreenMonitorTool with the given master window.

        Args:
            master (Tk): The main window of the application.
        """
        self.master = master
        self.master.title("Screen Monitor Tool")

        # Create GUI components
        self.label_info = Label(
            master, text="Press PgUp or use Screenshot button to ask a question"
        )
        self.label_info.pack(pady=10)

        self.output_label = Label(master, text="Output:")
        self.output_label.pack()

        # Use ScrolledText to display responses, allowing scrolling for long content
        self.output_text_box = ScrolledText(
            master, wrap='word', width=100, height=50
        )
        self.output_text_box.pack(pady=10)

        self.capture_button = Button(
            master, text="Screenshot", command=self.initiate_selection
        )
        self.capture_button.pack(pady=5)

        # Add loading animation (progress bar), initially hidden
        self.progress = ttk.Progressbar(master, mode='indeterminate')
        self.progress.pack(pady=10)
        self.progress.pack_forget()

        # Start keyboard listening
        self.start_listening()

    def start_listening(self):
        """
        Starts listening for keyboard events to trigger screenshot selection.
        """
        self.show_output_text(
            'Monitoring active. Press PgUp or click "Screenshot" to select an area and analyze the image content.'
        )
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()

    def show_output_text(self, text):
        """
        Displays the given text in the output text box.

        Clears previous text, inserts new text, and scrolls to the end.

        Args:
            text (str): The text to display.
        """
        self.output_text_box.delete("1.0", "end")
        self.output_text_box.insert("end", text)
        self.output_text_box.see("end")

    def show_loading(self, message):
        """
        Displays a loading message and shows the progress bar.

        Args:
            message (str): The loading message to display.
        """
        self.show_output_text(message)
        self.progress.pack(pady=10)
        self.progress.start(10)  # Progress bar updates every 10ms

    def hide_loading(self):
        """
        Hides the loading progress bar.
        """
        self.progress.stop()
        self.progress.pack_forget()
        self.master.update()

    def on_key_press(self, key):
        """
        Handles key press events.

        If the Page Up key is pressed, initiates screenshot selection.

        Args:
            key (keyboard.Key): The key that was pressed.
        """
        try:
            if key == keyboard.Key.page_up:
                self.initiate_selection()
        except AttributeError:
            # Ignore other keys
            pass

    def initiate_selection(self):
        """
        Initiates the area selection for screenshot capture by opening a transparent fullscreen window.
        """
        self.show_output_text("Please select the screenshot area...")
        self.selection_window = Toplevel(self.master)
        self.selection_window.attributes("-fullscreen", True)
        self.selection_window.attributes(
            "-alpha", 0.3)  # Set window transparency
        self.selection_window.configure(bg="black")

        self.canvas = Canvas(
            self.selection_window, cursor="cross", bg="gray"
        )
        self.canvas.pack(fill="both", expand=True)

        self.start_x = self.start_y = self.rect_id = None

        # Bind mouse events for drawing the selection rectangle
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        # Bind Esc key to cancel selection
        self.selection_window.bind("<Escape>", self.cancel_selection)

    def cancel_selection(self, event=None):
        """
        Cancels the screenshot selection, closes the selection window, and updates the output text.

        Args:
            event (tkinter.Event, optional): The event that triggered the cancellation.
        """
        if hasattr(self, 'selection_window') and self.selection_window.winfo_exists():
            self.selection_window.destroy()
            self.show_output_text("Screenshot selection canceled.")

    def on_mouse_down(self, event):
        """
        Handles the mouse button press event to start drawing the selection rectangle.

        Args:
            event (tkinter.Event): The mouse event.
        """
        self.start_x = event.x
        self.start_y = event.y
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2
        )

    def on_mouse_drag(self, event):
        """
        Updates the selection rectangle as the mouse is dragged.

        Args:
            event (tkinter.Event): The mouse event.
        """
        self.canvas.coords(self.rect_id, self.start_x,
                           self.start_y, event.x, event.y)

    def on_mouse_up(self, event):
        """
        Finalizes the selection rectangle upon mouse button release and initiates screenshot capture.

        Args:
            event (tkinter.Event): The mouse event.
        """
        end_x, end_y = event.x, event.y
        self.selection_window.destroy()

        # Calculate the selected region coordinates and dimensions
        region = (
            min(self.start_x, end_x),
            min(self.start_y, end_y),
            abs(self.start_x - end_x),
            abs(self.start_y - end_y),
        )
        self.capture_and_process(region)

    def capture_and_process(self, region):
        """
        Displays a loading message and starts a new thread to capture and process the screenshot.

        Args:
            region (tuple): The region of the screen to capture (x, y, width, height).
        """
        self.show_loading("Taking screenshot and analyzing image content...")
        # Use a separate thread to avoid blocking the GUI
        thread = threading.Thread(
            target=self._capture_and_process_thread, args=(region,)
        )
        thread.start()

    def _capture_and_process_thread(self, region):
        """
        Captures the screenshot of the specified region and processes it using OpenAI's API.

        Args:
            region (tuple): The region of the screen to capture (x, y, width, height).
        """
        try:
            # Delay to avoid capturing the transparent selection window
            time.sleep(0.5)
            screenshot = pyautogui.screenshot(region=region)
            # Save the screenshot to an in-memory BytesIO object instead of disk
            img_bytes = io.BytesIO()
            screenshot.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            # Send the image to OpenAI for analysis
            analysis = self.analyze_image(img_bytes)
            self.show_output_text(f"Result:\n{analysis}")
            print(f"Result:\n{analysis}")
        except Exception as e:
            self.show_output_text(f"Image analysis error: {e}")
        finally:
            self.hide_loading()

    def analyze_image(self, image_bytes):
        """
        Analyzes the provided image by sending it to the OpenAI API to solve the coding question contained in the image.

        The function follows these steps:
        1. Shows a loading message.
        2. Encodes the image in base64 format.
        3. Constructs a prompt instructing the model to solve the coding problem by following a series of steps,
        including clarifying questions, explaining the thought process, providing a Python implementation with 
        efficient algorithm recommendations, including test cases, and summarizing the time and space complexity.
        4. Sends the prompt along with the image to the OpenAI API.
        5. Measures the API call duration and extracts the total token usage from the response.
        6. Returns the response content along with API execution time and token usage information.

        Args:
            image_bytes (BytesIO): The in-memory bytes of the image to be analyzed.

        Returns:
            str: The analysis result including the response content from the API, API call duration, and token usage.
                If an exception occurs, returns an error message.
        """
        try:
            self.show_loading("Analyzing the image, please wait...")

            # Initialize OpenAI client
            client = openai.OpenAI()

            # Encode the image to base64
            base64_image = base64.b64encode(
                image_bytes.getvalue()).decode("utf-8")

            # Define the prompt for solving the coding problem in the image
            prompt = """
            You are a LeetCode coding problem solving master. 
            Please solve the coding question shown in the image by following these steps:
            1. Ask clarifying questions if any part of the problem is ambiguous.
            2. Explain your thought process, including the problem type (e.g., binary search, BFS, DP, etc.).
            3. Provide a complete Python implementation with clear comments. Use efficient algorithms (e.g., O(1) or O(n)) and avoid inefficient ones (e.g., O(n^2) or O(2^n)).
            4. Include multiple test cases to validate your solution.
            5. Summarize your solution with an explanation of its time and space complexity.

            Please refer below examples for naming conventions:
            - "l" and "r" for binary search boundaries.
            - "curr" for current.
            - "num" for number
            - Always save the result to "res" variable if possible.
            - Avoid overly verbose or LLM-like naming.
            """

            # Build the message payload with text and the encoded image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ]

            # Record the start time for API call timing
            start_time = time.time()

            # Send the request to OpenAI's chat completions API
            response = client.chat.completions.create(
                model="o1",  # Adjust the model name as per your usage
                messages=messages,
            )

            # Calculate the elapsed time for the API call
            elapsed_time = time.time() - start_time

            # Access token usage information if available, else default to "N/A"
            total_tokens = (
                response.usage.total_tokens if hasattr(response, "usage") and response.usage is not None
                else "N/A"
            )

            # Extract the response content from the API result
            response_content = response.choices[0].message.content.strip()

            # Append API call duration and token usage information to the response content
            analysis_result = (
                f"{response_content}\n\nAPI call duration: {elapsed_time:.2f} seconds\nToken usage: {total_tokens}"
            )
            print(analysis_result)
            return analysis_result

        except Exception as e:
            return f"Error: {e}"
        finally:
            self.hide_loading()


# Main program execution
if __name__ == "__main__":
    root = Tk()
    root.attributes("-alpha", 0.8)
    root.attributes("-topmost", True)
    tool = ScreenMonitorTool(root)
    root.mainloop()
