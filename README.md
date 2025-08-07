# fitness-ai-tracker# 🏋️ FitTracker – Personalized Fitness & Health Tracker

FitTracker is a full-stack fitness tracking web application built with Flask, MySQL, and AI-powered recommendation systems. It helps users manage workouts, diet plans, health metrics, and track progress toward their fitness goals.

## 🚀 Features

- 🔐 User Authentication (Login/Register)
- 📊 Dashboard with weight, calorie, and activity metrics
- 🧠 AI-based personalized diet and workout recommendations (GROQ/LLaMA)
- 📆 Daily logging for:
  - Meals 🍽️
  - Workouts 🏃‍♂️
  - Weight tracking ⚖️
- 📄 Export workout plan as PDF and Excel
- 🌑 Dark Mode toggle
- 💬 Motivational quotes on login
- 🏅 Progress Milestones (e.g., streaks, goals achieved)
- 🧘 Mindfulness features (meditation, rest day advice)
- 📈 AI Alerts for calorie/eating trends

## 📸 Screenshots

(Add screenshots of the dashboard, diet recommendation, etc.)

## 🛠️ Tech Stack

| Layer         | Technology Used                  |
|---------------|----------------------------------|
| Frontend      | HTML, CSS, JavaScript            |
| Backend       | Python (Flask)                   |
| Database      | MySQL                            |
| AI Integration| GROQ / LLaMA                     |

## ⚙️ Installation

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/fitness-tracker.git
cd fitness-tracker
```

2. **Create a virtual environment**

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# OR
source venv/bin/activate  # macOS/Linux
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Set up environment variables**

Create a `.env` file:

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=root
DB_NAME=fittracker
GROQ_API_KEY=your_actual_groq_api_key
SECRET_KEY=your_flask_secret_key
```

5. **Set up the database**

Use the provided SQL file or run:

```sql
CREATE DATABASE fittracker;
```

Then, import the tables or let the app auto-create them.

6. **Run the app**

```bash
python app.py
```

App will be available at: `http://127.0.0.1:5000`

## 🧠 AI Integration (GROQ/LLaMA)

This app integrates with GROQ AI to provide:
- Calorie trend analysis
- Personalized diet and workout plans
- Motivation and mindfulness tips

## 📦 Export Features

- Download diet/workout plans as **PDF**
- Export your logged workouts as **Excel**

## 🛡️ Security

- Passwords are hashed before storing
- Sessions are managed securely using Flask
- Environment variables hidden via `.env`

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you’d like to change.

## 📝 License

This project is open-source and available under the MIT License.

---

### 🙋 Author

**Dhanush S**  
📧 dhanushs1756@gmail.com  
🔗 [GitHub Profile](https://github.com/Dhanush1756)