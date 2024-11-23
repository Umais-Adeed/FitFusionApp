import datetime
import sys
import logging
import playsound  # To play audio cues
import threading
from PyQt5.QtGui import QMovie  # For animated GIFs
import sqlite3
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QStackedWidget, \
    QTabWidget, QSizePolicy, QHBoxLayout, QMessageBox, QTextEdit, QSlider, QComboBox
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QBrush, QPalette
import speech_recognition as sr  # Added for voice recognition
import threading
# Backend
import google.generativeai as genai
import requests
from PyQt5.QtGui import QMovie  # For animated GIFs
import time
import playsound  # To play audio cues


import pyttsx3  # For text-to-speech
from gtts import gTTS  # Optional alternative for text-to-speech
import os  # To handle audio playback

class BMI:
    def __init__(self):
        self.weight_kg = 0.0
        self.height_m = 0.0
        self.age = 0

    def get_bmi_category(self, bmi):
        if bmi < 18.5:
            return "You are Underweight"
        elif 18.5 <= bmi <= 24.9:
            return "You are Normal weight"
        elif 25.0 <= bmi <= 29.9:
            return "You are Overweight"
        else:
            return "You are Suffering from obesity"

class BMIMetric(BMI):
    def __init__(self, weight_kg, height_cm, age):
        super().__init__()
        self.weight_kg = weight_kg
        self.height_m = height_cm / 100  # Convert height from cm to meters
        self.age = age

    def calculate_bmi(self):
        return self.weight_kg / (self.height_m ** 2)
class MealPlanner:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.spoonacular.com/mealplanner/generate"

        # Initialize Gemini AI
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        self.chat = self.model.start_chat(history=[])

        self.system_prompt = """
        You are FitFusion AI, a health and nutrition expert. Provide meal plans based on calorie requirements,
        dietary preferences, and health goals. Ensure the meals are diverse, nutritious, and practical.
        """

    def get_meal_plan(self, target_calories, dietary_preferences=None):
        """Fetch a meal plan using Spoonacular or Gemini AI."""
        params = {
            "apiKey": self.api_key,
            "timeFrame": "day",
            "targetCalories": target_calories,
        }

        # Try Spoonacular API first
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Spoonacular API error: {e}")

        # Fall back to Gemini AI if Spoonacular fails
        try:
            user_query = f"Suggest meals for {target_calories} calories. Preferences: {dietary_preferences or 'None'}."
            self.chat.send_message(self.system_prompt)
            ai_response = self.chat.send_message(user_query)
            return {"ai_generated": ai_response.text}
        except Exception as e:
            print(f"Gemini AI error: {e}")
            return None


class FitnessAIAssistant:
    def __init__(self, api_key):
        self.api_key = api_key
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        self.system_prompt = """
        You are FitFusion AI, an expert in fitness, nutrition, and health. Respond concisely to user queries.
        """
        self.chat = None
        self.initialize_chat()

    def initialize_chat(self):
        """Initialize the chat object with the system prompt."""
        try:
            self.chat = self.model.start_chat(history=[])
            self.chat.send_message(self.system_prompt)
        except Exception as e:
            print(f"Error initializing Gemini AI chat: {e}")

    def send_query(self, user_query: str) -> str:
        """Send a query to Gemini AI and return the response."""
        try:
            if not self.chat:
                self.initialize_chat()
            response = self.chat.send_message(user_query)
            return response.text
        except Exception as e:
            print(f"Error communicating with Gemini AI: {str(e)}")
            return "Sorry, I couldn't process your request at the moment."


class WorkoutPlanner:
    def __init__(self, api_key):
        self.api_key = api_key

    def get_exercises_by_muscle(self, muscle):
        api_url = f'https://api.api-ninjas.com/v1/exercises?muscle={muscle}'
        response = requests.get(api_url, headers={'X-Api-Key': self.api_key})

        if response.status_code == requests.codes.ok:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return []

    def filter_exercises(self, exercises, filter_key, filter_value):
        return [exercise for exercise in exercises if exercise.get(filter_key) == filter_value]

    def format_exercise_details(self, exercises, total_time):
        if not exercises:
            return "No exercises found for the given criteria."

        time_per_exercise = total_time / len(exercises)
        details = "<h3>Workout Plan:</h3>"
        for idx, exercise in enumerate(exercises, start=1):
            details += f"<b>Exercise {idx}:</b> {exercise['name']}<br>"
            details += f"Type: {exercise['type']}<br>"
            details += f"Equipment: {exercise.get('equipment', 'N/A')}<br>"
            details += f"Difficulty: {exercise['difficulty']}<br>"
            details += f"Instructions: {exercise['instructions']}<br>"
            details += f"Allocated Time: {time_per_exercise:.2f} seconds<br><br>"
        return details



class LoginSignupApp(QWidget):
    def __init__(self, api_key,gemini_api_key):
        super().__init__()
        self.fitness_ai_assistant = FitnessAIAssistant(gemini_api_key)
        self.meal_planner = MealPlanner(api_key)  # Create an instance of MealPlanner

        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone(sample_rate=16000, chunk_size=1024)
        self.voice_assistant_active = False
        # Pre-adjust ambient noise once during initialization
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)

        self.setWindowTitle('FitFusion: Fitness Tracker')
        self.setGeometry(100, 100, 800, 600)  # Set window size
        self.central_widget = QStackedWidget(self)

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.central_widget)

        # Add back and forward buttons
        self.back_button = QPushButton("Back")
        self.forward_button = QPushButton("Forward")

        # Set button styles
        self.set_back_button_style(self.back_button)
        self.set_forward_button_style(self.forward_button)

        # Connect buttons to their respective functions
        self.back_button.clicked.connect(self.go_back)
        self.forward_button.clicked.connect(self.go_forward)

        # Add buttons to the layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.back_button)
        button_layout.addWidget(self.forward_button)

        self.layout().addLayout(button_layout)

        # Initialize history stack
        self.history = []
        self.current_index = -1

        self.init_main_ui()
        self.init_login_ui()
        self.init_signup_ui()
        self.init_forgot_password_ui()
        self.init_welcome_ui()

        self.central_widget.setCurrentIndex(0)  # Start with the main UI
        self.add_to_history(0)  # Add main UI to history




    def set_back_button_style(self, button):
        button.setStyleSheet("""
            background-color: #64B5F6;  /* Light blue for back button */
            color: white;                /* White text */
            font-size: 18px;             /* Increased font size */
            padding: 15px;               /* Increased padding */
            border-radius: 5px;          /* Rounded corners */
            cursor: pointer;              /* Change cursor to pointer */
        }
        QPushButton:hover {
            background-color: #5a9bd4;  /* Darker blue on hover */
        }
        """)

    def set_forward_button_style(self, button):
        button.setStyleSheet("""
            background-color: #FFB74D;  /* Light orange for forward button */
            color: white;                /* White text */
            font-size: 18px;             /* Increased font size */
            padding: 15px;               /* Increased padding */
            border-radius: 5px;          /* Rounded corners */
            cursor: pointer;              /* Change cursor to pointer */
        }
        QPushButton:hover {
            background-color: #ff9f3d;  /* Darker orange on hover */
        }
        """)
    def set_button_style(self, button):
        button.setStyleSheet("""
            background-color: #E1BEE7;  /* Light purple background */
            color: black;                /* Black text for contrast */
            font-size: 18px;             /* Increased font size */
            padding: 10px 20px;          /* Padding for better visibility */
            border: 1px solid #ccc;      /* Border around buttons */
            border-radius: 4px;          /* Rounded corners */
            cursor: pointer;              /* Change cursor to pointer */
        }
        QPushButton:hover {
            background-color: #D5006D;  /* Darker purple on hover */
        }
        """)

    def set_text_field_style(self, text_field):
        text_field.setStyleSheet("""
            font-size: 24px;  /* Increased font size */
            padding: 12px;    /* Increased padding */
            border: 2px solid #444444;
            border-radius: 5px;
            background-color: #f1f1f1;
        """)


    def add_to_history(self, index):
        """Add the current index to the history."""
        if self.current_index + 1 < len(self.history):
            self.history = self.history[:self.current_index + 1]

        self.history.append(index)
        self.current_index += 1

    def go_back(self):
        """Navigate to the previous view."""
        if self.current_index > 0:
            self.current_index -= 1
            self.central_widget.setCurrentIndex(self.history[self.current_index])

    def go_forward(self):
        """Navigate to the next view."""
        if self.current_index < len(self.history) - 1:
            self.current_index += 1
            self.central_widget.setCurrentIndex(self.history[self.current_index])

    def init_main_ui(self):
        """Initial window with Register Here options (Login/Signup)"""
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)

        # Background Image for Main Window
        self.set_background_image("background_image_dark")  # Set your downloaded background image path here

        # Title label (adjusted font size)
        label = QLabel("Welcome to FitFusion!", self)
        label.setStyleSheet("font-size: 50px; font-weight: bold; color: white;")
        label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(label)

        # Buttons for Login and Signup with modern styles
        btn_login = QPushButton('Login', self)
        self.set_button_style(btn_login)
        btn_login.setStyleSheet(btn_login.styleSheet() + "font-size: 30px; margin-top: 20px;")
        btn_login.clicked.connect(lambda: self.switch_to_login())  # Switch to login
        main_layout.addWidget(btn_login)

        btn_signup = QPushButton('Signup', self)
        self.set_button_style(btn_signup)
        btn_signup.setStyleSheet(btn_signup.styleSheet() + "font-size: 30px; margin-top: 20px;")
        btn_signup.clicked.connect(lambda: self.switch_to_signup())  # Switch to signup
        main_layout.addWidget(btn_signup)

        self.central_widget.addWidget(main_widget)

    def switch_to_login(self):
        self.central_widget.setCurrentIndex(1)  # Switch to login
        self.add_to_history(1)  # Add login UI to history

    def switch_to_signup(self):
        self.central_widget.setCurrentIndex(2)  # Switch to signup
        self.add_to_history(2)  # Add signup UI to history

    def init_login_ui(self):
        """Login UI with enhanced interaction"""
        login_widget = QWidget()
        layout = QVBoxLayout(login_widget)

        # Login Form UI with Custom Styling
        email_label = QLabel("Email: ", self)
        email_label.setStyleSheet("font-size: 30px; color: white; font-weight: bold;")
        layout.addWidget(email_label)

        self.login_email = QLineEdit(self)
        self.set_text_field_style(self.login_email)
        self.login_email.setPlaceholderText("Enter your email")
        layout.addWidget(self.login_email)

        password_label = QLabel("Password: ", self)
        password_label.setStyleSheet("font-size: 30px; color: white; font-weight: bold;")
        layout.addWidget(password_label)

        self.login_password = QLineEdit(self)
        self.set_text_field_style(self.login_password)
        self.login_password.setEchoMode(QLineEdit.Password)
        self.login_password.setPlaceholderText("Enter your password")
        layout.addWidget(self.login_password)

        # Login button with animation and feedback
        btn_login = QPushButton("Login", self)
        self.set_button_style(btn_login)
        btn_login.setStyleSheet(btn_login.styleSheet() + "font-size: 25px; margin-top: 20px; font-weight: bold;")
        btn_login.clicked.connect(self.on_login_button_click)
        layout.addWidget(btn_login)


        # Feedback label
        self.login_feedback = QLabel("", self)
        self.login_feedback.setStyleSheet("font-size: 25px; color: white;")
        layout.addWidget(self.login_feedback)


        # Forgot Password Button
        btn_forgot_password = QPushButton("Forgot Password?", self)
        self.set_button_style(btn_forgot_password)
        btn_forgot_password.clicked.connect(self.open_forgot_password_window)
        layout.addWidget(btn_forgot_password)

        self.central_widget.addWidget(login_widget)

    def on_login_button_click(self):
        """Triggered when the login button is clicked."""
        email = self.login_email.text().strip()
        password = self.login_password.text().strip()

        if not email:
            self.login_feedback.setText("Please enter your email.")
            return
        if not password:
            self.login_feedback.setText("Please enter your password.")
            return

        self.login_feedback.setText("")  # Clear previous feedback
        self.login_database()

    def login_database(self):
        """Check credentials in the database for login"""
        email = self.login_email.text().strip()
        password = self.login_password.text().strip()

        try:
            conn = sqlite3.connect("1.db")
            cur = conn.cursor()
            cur.execute("SELECT * FROM test WHERE email=? AND password=?", (email, password))
            row = cur.fetchall()
        except sqlite3.Error as e:
            self.login_feedback.setStyleSheet("font-size: 25px; color: red;")
            self.login_feedback.setText(f"Database error: {e}")
            return
        finally:
            conn.close()  # Ensure the connection is closed

        if row:
            user_name = row[0][1]
            self.login_feedback.setStyleSheet("font-size: 25px; color: white;")
            self.login_feedback.setText(f"Login successful. Welcome {user_name}!")
            self.show_welcome_frame(user_name)  # Show welcome frame upon successful login
        else:
            # Provide a more user-friendly message
            self.login_feedback.setStyleSheet("font-size: 25px; color: white;")
            self.login_feedback.setText("No such user found. Please sign up or check your credentials.")
    def open_forgot_password_window(self, event):
        """Open the forgot password dialog"""
        self.central_widget.setCurrentIndex(3)  # Switch to forgot password UI
        self.add_to_history(3)  # Add forgot password UI to history

    def init_forgot_password_ui(self):
        """Forgot Password UI"""
        forgot_widget = QWidget()
        layout = QVBoxLayout(forgot_widget)

        # Label and input for email
        email_label = QLabel("Enter your registered email:", self)
        email_label.setStyleSheet("font-size: 25px; color: white; font-weight: bold;")
        layout.addWidget(email_label)

        self.forgot_email = QLineEdit(self)
        self.set_text_field_style(self.forgot_email)
        self.forgot_email.setPlaceholderText("Enter your email")
        layout.addWidget(self.forgot_email)

        # Submit button for password reset
        btn_reset = QPushButton("Reset Password", self)
        self.set_button_style(btn_reset)
        btn_reset.setStyleSheet(btn_reset.styleSheet() + "font-size: 25px; margin-top: 20px; font-weight: bold;")
        btn_reset.clicked.connect(self.reset_password)
        layout.addWidget(btn_reset)

        # Feedback label
        self.forgot_password_feedback = QLabel("", self)
        self.forgot_password_feedback.setStyleSheet("font-size: 25px; color: white;")
        layout.addWidget(self.forgot_password_feedback)

        self.central_widget.addWidget(forgot_widget)

    def reset_password(self):
        """Simulate password reset process (for now just a placeholder)"""
        email = self.forgot_email.text().strip()

        if not email:
            self.forgot_password_feedback.setText("Please enter your email.")
            return

        # Here you would typically send the email for password reset
        # For now, we will simulate this with a message
        self.forgot_password_feedback.setText(
            "Password reset instructions sent to your email! Please check your inbox.")
        # Do not switch back to the main UI; stay on the forgot password screen

    def init_signup_ui(self):
        # Signup UI
        signup_widget = QWidget()
        layout = QVBoxLayout(signup_widget)

        # Signup Form UI with Custom Styling
        name_label = QLabel("User  Name: ", self)
        name_label.setStyleSheet("font-size: 30px; color: white;")
        layout.addWidget(name_label)

        self.signup_name = QLineEdit(self)
        self.set_text_field_style(self.signup_name)
        layout.addWidget(self.signup_name)

        email_label = QLabel("User  Email: ", self)
        email_label.setStyleSheet("font-size: 30px; color: white;")
        layout.addWidget(email_label)

        self.signup_email = QLineEdit(self)
        self.set_text_field_style(self.signup_email)
        layout.addWidget(self.signup_email)

        password_label = QLabel("Password: ", self)
        password_label.setStyleSheet("font-size: 30px; color: white;")
        layout.addWidget(password_label)

        self.signup_password = QLineEdit(self)
        self.set_text_field_style(self.signup_password)
        self.signup_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.signup_password)

        # Feedback label
        self.signup_feedback = QLabel("", self)
        self.signup_feedback.setStyleSheet("font-size: 25px; color: white;")
        layout.addWidget(self.signup_feedback)

        # Sign up button
        btn_signup = QPushButton("Signup", self)
        self.set_button_style(btn_signup)
        btn_signup.setStyleSheet(btn_signup.styleSheet() + "font-size: 25px; margin-top: 20px;")
        btn_signup.clicked.connect(self.signup_database)
        layout.addWidget(btn_signup)

        self.central_widget.addWidget(signup_widget)

    def signup_database(self):
        """Handle database actions for signup"""
        name = self.signup_name.text().strip()
        email = self.signup_email.text().strip()
        password = self.signup_password.text().strip()

        if not name or not email or not password:
            self.signup_feedback.setText("Please fill in all fields.")
            return

        conn = sqlite3.connect("1.db")
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS test(id INTEGER PRIMARY KEY, name TEXT, email TEXT, password TEXT)")
        cur.execute("INSERT INTO test (name, email, password) VALUES (?, ?, ?)", (name, email, password))

        conn.commit()
        conn.close()

        self.signup_feedback.setText("Account created successfully!")
        self.signup_name.clear()
        self.signup_email.clear()
        self.signup_password.clear()
        self.central_widget.setCurrentIndex(0)  # Go back to main UI
        self.add_to_history(0)  # Add main UI to history

    def init_welcome_ui(self):
        """Show a welcome frame after successful login"""
        welcome_widget = QWidget()
        layout = QVBoxLayout(welcome_widget)

        # Welcome message with custom style
        self.welcome_msg = QLabel("", self)
        self.welcome_msg.setStyleSheet("font-size: 40px; font-weight: bold; color: #333333;")
        self.welcome_msg.setAlignment(Qt.AlignCenter)  # Centering the label
        layout.addWidget(self.welcome_msg)

        # Logout button with modern style
        btn_logout = QPushButton("Logout", self)
        self.set_button_style(btn_logout)
        btn_logout.setStyleSheet(btn_logout.styleSheet() + "font-size: 25px; margin-top: 20px;")
        btn_logout.clicked.connect(self.logout)
        layout.addWidget(btn_logout)

        self.central_widget.addWidget(welcome_widget)

    def show_welcome_frame(self, user_name):
        """Show welcome message and initialize tabs after successful login"""
        self.central_widget.setCurrentIndex(5)  # Switch to a new index for tabs
        self.init_tabs(user_name)  # Initialize tabs
        self.add_to_history(5)  # Add tabs UI to history

    def init_tabs(self, user_name):
        """Initialize the tabbed interface after login"""
        tabs_widget = QWidget()
        tabs_layout = QVBoxLayout(tabs_widget)

        # Create QTabWidget
        self.tabs = QTabWidget()

        # Apply the updated style sheet for colorful and fitting tab buttons
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                background-color: #E1BEE7;  /* Light purple background */
                color: black;               /* Black text for contrast */
                font-size: 14px;            /* Font size */
                padding: 10px 25px;         /* Ensure proper padding for better visibility */
                border: 1px solid #ccc;     /* Border around tabs */
                border-bottom: none;        /* Smooth look */
                border-radius: 4px;         /* Rounded corners */
                min-width: 100px;           /* Minimum width to prevent truncation */
            }

            QTabBar::tab:selected {
                background-color: #D81B60;  /* Darker purple for selected tab */
                font-weight: bold;          /* Bold text for selected tab */
            }

            QTabBar::tab:hover {
                background-color: #D5006D;  /* Lighter purple on hover */
            }

            QTabWidget::pane {
                border: 1px solid #ccc;     /* Border around tab content */
                border-top: none;           /* Merge content with tabs */
            }
        """)

        # Allow tabs to expand with window size
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Add the QTabWidget to the layout
        tabs_layout.addWidget(self.tabs)

        # Create tabs
        self.create_workout_planner_tab()
        self.create_streak_tab()
        self.create_bmi_visualization_tab()
        self.create_meal_planner_tab()
        self.create_interactive_assistant_tab()
        self.create_help_tab()

        # Set the tabs widget as the central widget
        self.central_widget.addWidget(tabs_widget)
        self.central_widget.setCurrentWidget(tabs_widget)  # Show the tabs widget

        # Use stretch to ensure resizing affects tab size properly
        tabs_layout.setStretch(0, 1)  # Allow the tab widget to stretch
    def create_workout_planner_tab(self):
        workout_tab = QWidget()
        layout = QVBoxLayout(workout_tab)

        # Title
        label = QLabel("Workout Planner", self)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 30px; font-weight: bold; color: white;")
        layout.addWidget(label)

        # Exercise Name Input (Optional)
        self.exercise_name_input = QLineEdit(self)
        self.exercise_name_input.setPlaceholderText("Exercise Name (partial match allowed)")
        self.set_text_field_style(self.exercise_name_input)
        layout.addWidget(self.exercise_name_input)

        # Exercise Type ComboBox
        self.type_combo = QComboBox(self)
        self.type_combo.addItems([
            "Any Type", "cardio", "olympic_weightlifting", "plyometrics",
            "powerlifting", "strength", "stretching", "strongman"
        ])
        layout.addWidget(self.type_combo)

        # Muscle Group ComboBox
        self.muscle_combo = QComboBox(self)
        self.muscle_combo.addItems([
            "Any Muscle", "abdominals", "abductors", "adductors", "biceps",
            "calves", "chest", "forearms", "glutes", "hamstrings", "lats",
            "lower_back", "middle_back", "neck", "quadriceps", "traps", "triceps"
        ])
        layout.addWidget(self.muscle_combo)

        # Difficulty ComboBox
        self.difficulty_combo = QComboBox(self)
        self.difficulty_combo.addItems(["Any Difficulty", "beginner", "intermediate", "expert"])
        layout.addWidget(self.difficulty_combo)

        # Workout Duration Input
        self.workout_duration_input = QLineEdit(self)
        self.workout_duration_input.setPlaceholderText("Workout Duration (minutes)")
        self.set_text_field_style(self.workout_duration_input)
        layout.addWidget(self.workout_duration_input)

        # Generate Button
        generate_button = QPushButton("Generate Workout Plan", self)
        self.set_button_style(generate_button)
        generate_button.clicked.connect(self.generate_workout_plan)
        layout.addWidget(generate_button)

        # Output Area
        self.workout_plan_output = QTextEdit(self)
        self.workout_plan_output.setReadOnly(True)
        self.workout_plan_output.setStyleSheet("""
            background-color: #f9f9f9;
            border: 1px solid #cccccc;
            font-size: 14px;
            padding: 10px;
        """)
        layout.addWidget(self.workout_plan_output)

        # Add tab
        self.tabs.addTab(workout_tab, "Workouts")

    def generate_workout_plan(self):
        name = self.exercise_name_input.text().strip()  # Optional exercise name
        exercise_type = self.type_combo.currentText() if self.type_combo.currentText() != "Any Type" else None
        muscle = self.muscle_combo.currentText() if self.muscle_combo.currentText() != "Any Muscle" else None
        difficulty = self.difficulty_combo.currentText() if self.difficulty_combo.currentText() != "Any Difficulty" else None

        try:
            total_time = float(self.workout_duration_input.text().strip())
        except ValueError:
            self.workout_plan_output.setPlainText("Please enter a valid number for workout duration.")
            return

        # Fetch exercises using the API
        planner = WorkoutPlanner(api_key="1c55tgO/oZW1c40Dtz+PxQ==hGupNoi6khvXO6Xv")
        exercises = planner.get_exercises(
            name=name, exercise_type=exercise_type, muscle=muscle, difficulty=difficulty
        )

        # Format and display the workout plan
        formatted_plan = planner.format_exercise_details(exercises, total_time)
        self.workout_plan_output.setHtml(formatted_plan)
    def create_streak_tab(self):
        streak_tab = QWidget()
        layout = QVBoxLayout(streak_tab)

        label = QLabel("Streak Tracker", self)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 30px; font-weight: bold; color: white;")
        layout.addWidget(label)


        button_reset = QPushButton("Reset Streak", self)
        button_view = QPushButton("View Progress", self)

        self.set_button_style(button_reset)
        self.set_button_style(button_view)

        button_layout = QHBoxLayout()
        button_layout.addWidget(button_reset)
        button_layout.addWidget(button_view)

        layout.addLayout(button_layout)
        self.tabs.addTab(streak_tab, "Streak")





    def create_bmi_visualization_tab(self):
        bmi_tab = QWidget()
        layout = QVBoxLayout(bmi_tab)

        label = QLabel("BMI Visualization", self)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 30px; font-weight: bold; color: white;")
        layout.addWidget(label)

        self.weight_input = QLineEdit(self)
        self.weight_input.setPlaceholderText("Weight (kg)")
        self.set_text_field_style(self.weight_input)
        layout.addWidget(self.weight_input)

        self.height_input = QLineEdit(self)
        self.height_input.setPlaceholderText("Height (cm)")
        self.set_text_field_style(self.height_input)
        layout.addWidget(self.height_input)

        self.age_input = QLineEdit(self)
        self.age_input.setPlaceholderText("Age")
        self.set_text_field_style(self.age_input)
        layout.addWidget(self.age_input)

        calculate_button = QPushButton("Calculate BMI", self)
        self.set_button_style(calculate_button)
        calculate_button.clicked.connect(self.calculate_bmi)
        layout.addWidget(calculate_button)

        # Create a text field to show the BMI result
        self.bmi_output = QLineEdit(self)
        self.bmi_output.setReadOnly(True)  # Make it read-only
        layout.addWidget(self.bmi_output)

        self.tabs.addTab(bmi_tab, "BMI")

    def calculate_bmi(self):
        try:
            weight = float(self.weight_input.text())
            height = float(self.height_input.text())
            age = int(self.age_input.text())

            bmi_metric = BMIMetric(weight, height, age)
            bmi_value = bmi_metric.calculate_bmi()
            bmi_category = bmi_metric.get_bmi_category(bmi_value)

            # Display the BMI value and category in the text field
            self.bmi_output.setText(f"BMI Value: {bmi_value:.2f}, Category: {bmi_category}")

        except ValueError:
            self.bmi_output.setText("Please enter valid numbers for weight, height, and age.")

    def create_meal_planner_tab(self):
        meal_tab = QWidget()
        layout = QVBoxLayout(meal_tab)

        label = QLabel("Meal Planner", self)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 30px; font-weight: bold; color: white;")
        layout.addWidget(label)

        self.calories_input = QLineEdit(self)
        self.calories_input.setPlaceholderText("Enter Target Calories")
        self.set_text_field_style(self.calories_input)
        self.calories_input.setStyleSheet(self.calories_input.styleSheet() + "margin-bottom: 15px;")
        layout.addWidget(self.calories_input)



        generate_meal_button = QPushButton("Generate Meal Plan", self)
        self.set_button_style(generate_meal_button)
        generate_meal_button.clicked.connect(self.generate_meal_plan)
        layout.addWidget(generate_meal_button)

        self.meal_plan_output = QTextEdit(self)
        self.meal_plan_output.setReadOnly(True)
        self.meal_plan_output.setStyleSheet("""
            background-color: #f9f9f9;
            border: 1px solid #cccccc;
            font-size: 14px;
            line-height: 1.5;
            padding: 10px;
        """)
        layout.addWidget(self.meal_plan_output)

        self.tabs.addTab(meal_tab, "Meal Planner")

    def generate_meal_plan(self):
        try:
            target_calories = int(self.calories_input.text())
            meal_plan = self.meal_planner.get_meal_plan(target_calories)

            if meal_plan and "meals" in meal_plan:
                meals = ""
                for meal in meal_plan["meals"]:
                    meals += f"<b>- {meal['title']}</b><br>"
                    meals += f"  Ready in: {meal['readyInMinutes']} minutes<br>"
                    meals += f"  Servings: {meal['servings']}<br>"
                    meals += f"  Recipe Link: {meal['sourceUrl']}<br><br>"  # Display URL directly

                self.meal_plan_output.setHtml(f"<h3>Recommended Meals:</h3>{meals}")
            else:
                self.meal_plan_output.setPlainText("Failed to generate meal plan.")
        except ValueError:
            self.meal_plan_output.setPlainText("Please enter a valid number for target calories.")
        except Exception as e:
            self.meal_plan_output.setPlainText(f"An error occurred: {e}")




    def get_fitness_support(self):
        # Placeholder for Fitness Support API call
        try:
            response = requests.get("https://api.fitnesssupport.com/getSupport")  # Replace with actual API URL
            response.raise_for_status()
            support_info = response.json()
            support_message = support_info.get("message", "No support information available.")
            self.show_message(support_message)
        except requests.exceptions.RequestException as e:
            self.show_message(f"Error fetching support information: {e}")

    def activate_voice_assistant(self):
        """Activate the voice assistant with enhanced visual and audio feedback."""
        self.voice_assistant_active = True
        self.dynamic_button.setText("Stop Recording")  # Change button label
        self.assistant_status_label.setText("🎤 Listening...")
        self.assistant_status_label.setStyleSheet("font-size: 20px; color: green; font-weight: bold;")

        # Start animated visual feedback
        self.start_recording_visual_feedback()

        # Play a sound to indicate recording start
        threading.Thread(target=lambda: self.play_sound("start_sound.mp3"), daemon=True).start()

        def listen():
            try:
                while self.voice_assistant_active:
                    with self.microphone as source:
                        # Adjust for ambient noise and start listening
                        self.recognizer.adjust_for_ambient_noise(source)
                        audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=2)

                    # Stop recording if the user presses "Stop"
                    if not self.voice_assistant_active:
                        break

                    # Play a sound to indicate recording stop
                    threading.Thread(target=lambda: self.play_sound("stop_sound.mp3"), daemon=True).start()

                    # Stop visual feedback
                    self.stop_recording_visual_feedback()

                    # Process the audio input
                    try:
                        command = self.recognizer.recognize_google(audio)
                        self.chat_output.append(
                            f"<b>You (Voice)</b> ({datetime.datetime.now().strftime('%H:%M')}): {command}")
                        self.process_voice_command(command)
                    except sr.UnknownValueError:
                        self.chat_output.append("<b>Assistant</b>: Sorry, I couldn't understand that.")
                    except sr.RequestError as e:
                        self.chat_output.append(f"<b>Assistant</b>: Error with voice recognition service: {e}")
            except sr.WaitTimeoutError:
                self.chat_output.append("<b>Assistant</b>: No input detected. Please try again.")
                self.stop_recording_visual_feedback()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Voice Assistant Error: {str(e)}")
                self.stop_recording_visual_feedback()
            finally:
                self.deactivate_voice_assistant()  # Ensure cleanup

        threading.Thread(target=listen, daemon=True).start()

    def start_recording_visual_feedback(self):
        """Start the visual feedback for recording."""
        self.mic_animation = QMovie("mic_listening.gif")  # Animated microphone icon
        self.mic_label.setMovie(self.mic_animation)
        self.mic_animation.start()

        self.recording_timer_start = time.time()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_recording_timer)
        self.timer.start(1000)

    def stop_recording_visual_feedback(self):
        """Stop the visual feedback for recording."""
        self.assistant_status_label.setText("🔴 Recording Stopped.")
        self.assistant_status_label.setStyleSheet("font-size: 20px; color: gray;")
        if hasattr(self, "mic_animation") and self.mic_animation:
            self.mic_animation.stop()
            self.mic_label.clear()
        if hasattr(self, "timer") and self.timer:
            self.timer.stop()

    def update_recording_timer(self):
        """Update the timer for how long the recording has been active."""
        elapsed_time = int(time.time() - self.recording_timer_start)
        minutes, seconds = divmod(elapsed_time, 60)
        self.assistant_status_label.setText(f"🎤 Listening... {minutes}:{seconds:02}")

    def play_sound(self, file_path):
        """Play a sound file."""
        try:
            playsound.playsound(file_path)
        except Exception as e:
            print(f"Error playing sound: {e}")

    def process_voice_command(self, command: str):
        """Process commands received from voice input with intent detection."""
        command = command.lower()
        if "login" in command:
            self.switch_to_login()
        elif "sign up" in command or "register" in command:
            self.switch_to_signup()
        elif "meal plan" in command:
            self.central_widget.setCurrentIndex(3)  # Navigate to meal planner
        elif "calculate bmi" in command or "bmi" in command:
            self.central_widget.setCurrentIndex(4)  # Navigate to BMI calculator
        elif "exit" in command or "logout" in command:
            self.logout()
        else:
            self.chat_output.append("<b>Assistant</b>: Let me think about that...")
            response = self.fitness_ai_assistant.send_query(command)
            formatted_response = self.format_response(response)
            self.chat_output.append(f"<b>Assistant</b>: {formatted_response}")

    def deactivate_voice_assistant(self):
        """Deactivate the voice assistant and reset UI state."""
        self.voice_assistant_active = False
        self.assistant_status_label.setText("🔴 Status: Inactive")
        self.assistant_status_label.setStyleSheet("font-size: 20px; color: gray;")
        self.dynamic_button.setText("Record")  # Reset button label
        self.stop_recording_visual_feedback()
        self.chat_output.append("<b>Assistant</b>: Voice assistant deactivated.")

    def toggle_button_mode(self):
        """Toggle the dynamic button mode based on chat input or recording state."""
        if self.dynamic_button.text() == "Deactivate":
            return  # If actively recording, the button stays as "Deactivate"
        elif self.chat_input.text().strip():  # If chat input is not empty
            self.dynamic_button.setText("Send")
        else:  # If the chat input is empty
            self.dynamic_button.setText("Record")

    def handle_dynamic_button_action(self):
        """Handle actions for the dynamic button based on its current state."""
        current_text = self.dynamic_button.text()
        if current_text == "Send":
            self.send_chat_message()
        elif current_text == "Record":
            self.activate_voice_assistant()
        elif current_text == "Stop Recording":
            self.deactivate_voice_assistant()

    def create_interactive_assistant_tab(self):
        """Create the interactive assistant tab with enhanced chat and voice features."""
        assistant_tab = QWidget()
        layout = QVBoxLayout(assistant_tab)
        # Microphone animation label


        # Tab title
        label = QLabel("AI Assistant", self)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 30px; font-weight: bold; color: white;")
        layout.addWidget(label)

        # Chat output area
        self.chat_output = QTextEdit(self)
        self.chat_output.setStyleSheet("""
            QTextEdit {
                background-color: #f9f9f9;
                border: 1px solid #cccccc;
                border-radius: 5px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                color: #333333;
                padding: 8px;
                line-height: 1.5;
            }
        """)
        self.chat_output.setReadOnly(True)
        layout.addWidget(self.chat_output)

        # Input area and dynamic button
        input_layout = QHBoxLayout()

        self.chat_input = QLineEdit(self)
        self.chat_input.setPlaceholderText("Type your message here or press record...")
        self.set_text_field_style(self.chat_input)
        self.chat_input.textChanged.connect(self.toggle_button_mode)
        input_layout.addWidget(self.chat_input)


        self.mic_label = QLabel(self)
        self.mic_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.mic_label)

        self.dynamic_button = QPushButton("Record", self)
        self.set_button_style(self.dynamic_button)
        self.dynamic_button.clicked.connect(self.handle_dynamic_button_action)
        input_layout.addWidget(self.dynamic_button)

        layout.addLayout(input_layout)

        # Status label for assistant state
        self.assistant_status_label = QLabel("Status: Inactive", self)
        self.assistant_status_label.setAlignment(Qt.AlignCenter)
        self.assistant_status_label.setStyleSheet("font-size: 20px; color: #cccccc;")
        layout.addWidget(self.assistant_status_label)

        # Add the tab to the QTabWidget
        self.tabs.addTab(assistant_tab, "AI Assistant")

    def send_chat_message(self):
        """Handle user input and communicate with Gemini AI."""
        message = self.chat_input.text().strip()
        if message:
            self.chat_output.append(f"<b>You</b> ({datetime.datetime.now().strftime('%H:%M')}): {message}")
            self.chat_input.clear()

            self.chat_output.append("<b>Assistant</b> is typing...")
            self.chat_output.repaint()

            def process_message():
                try:
                    response = self.fitness_ai_assistant.send_query(message)
                    formatted_response = self.format_response(response)
                    self.chat_output.append(
                        f"<b>Assistant</b> ({datetime.datetime.now().strftime('%H:%M')}): {formatted_response}")
                except Exception as e:
                    self.chat_output.append(f"<b>Assistant</b>: Sorry, I encountered an error: {e}")
                finally:
                    self.chat_output.append("")  # Remove the typing indicator

            threading.Thread(target=process_message, daemon=True).start()
        else:
            self.chat_output.append("<b>Assistant</b>: Please enter a message or use the voice assistant.")

    def format_response(self, response: str) -> str:
        """Format the assistant's response to ensure consistency and readability."""
        return response.strip().replace("*", "").replace("\n", " ")

    def create_help_tab(self):
        help_tab = QWidget()
        layout = QVBoxLayout(help_tab)

        label = QLabel("Help & FAQs", self)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 30px; font-weight: bold; color: white;")
        layout.addWidget(label)

        faqs = [
            "Q: How do I reset my password?\nA: Click on 'Forgot Password?' on the login screen.",
            "Q: How can I contact support?\nA: Please use the contact form on our website.",
            "Q: What features does this app offer?\nA: The app provides workout planning, meal planning, and fitness tracking."
        ]

        for faq in faqs:
            faq_label = QLabel(faq, self)
            faq_label.setStyleSheet("font-size: 20px; color: #cccccc;")
            layout.addWidget(faq_label)

        self.tabs.addTab(help_tab, "Help")

    def show_message(self, message):
        """Display a message in a dialog."""
        msg_box = QMessageBox()
        msg_box.setText(message)
        msg_box.exec_()

    def logout(self):
        """Logout function - Close the welcome window and return to the main window"""
        self.central_widget.setCurrentIndex(0)  # Go back to main UI
        self.add_to_history(0)  # Add main UI to history

    def set_background_image(self, image_path):
        """Set a background image for the window."""
        pixmap = QPixmap(image_path)  # Load the image
        if pixmap.isNull():
            print("Failed to load background image.")
            return

        # Set the background image to the central widget
        palette = QPalette()
        palette.setBrush(QPalette.Window, QBrush(pixmap))
        self.setPalette(palette)


if __name__ == "__main__":
    api_key = "e5968cb05a3b42a4845c016350e83f17"
    gemini_api_key = "AIzaSyA1RJISbzG7WJ0T_ZRQIEVj_WWkhiHKml4"

    app = QApplication(sys.argv)
    window = LoginSignupApp(api_key, gemini_api_key)
    window.show()
    sys.exit(app.exec_())

