from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from database import db
from graph_utils import create_plot
from ai_integration import get_ai_diet_suggestion, get_ai_workout_plan, get_nutrition_info,get_daily_quote, get_workout_calories, get_ai_chat_response
from export_utils import generate_pdf_report, generate_excel_report
from datetime import datetime, timedelta
import os
import json
from config import Config


app = Flask(__name__)
app.config.from_pyfile('config.py')
app.config.from_object(Config)
Config.init_app(app)


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# --- FIX: STEP 2 of 2: This context processor makes `now` available in all templates ---
@app.context_processor
def inject_now():
    """Injects the `datetime` object into the template context."""
    return {'now': datetime.utcnow}


# ===============================================================
# The rest of your file remains exactly as it was.
# No other changes are needed.
# ===============================================================

class User(UserMixin):
    def __init__(self, user_dict):
        self.id = user_dict.get('id')
        self.email = user_dict.get('email')
        self.name = user_dict.get('name')
        self.password = user_dict.get('password')
        self.profile_photo = user_dict.get('profile_photo', 'default.png')
        self.age = user_dict.get('age')
        self.gender = user_dict.get('gender')
        self.height = user_dict.get('height')
        self.weight = user_dict.get('weight')
        self.goal_weight = user_dict.get('goal_weight')
        self.diet_preference = user_dict.get('diet_preference')
        self.fitness_goal = user_dict.get('fitness_goal')
        self.activity_level = user_dict.get('activity_level')
        self.daily_calories = user_dict.get('daily_calories', 2000)
        self.dark_mode = user_dict.get('dark_mode', False)
        self.created_at = user_dict.get('created_at')
        self.medical_conditions = user_dict.get('medical_conditions')
        self.past_surgeries = user_dict.get('past_surgeries')

    def get_id(self):
        return str(self.id)

    @staticmethod
    def get(user_id):
        query = "SELECT * FROM users WHERE id = %s"
        user_data = db.execute_query(query, (user_id,), fetch_one=True)
        return User(user_data) if user_data else None

    @staticmethod
    def get_by_email(email):
        query = "SELECT * FROM users WHERE email = %s"
        user_data = db.execute_query(query, (email,), fetch_one=True)
        return User(user_data) if user_data else None

    def save(self):
        # This method is now fully corrected to handle both updates and new user creation.
        if self.id:
            # This query is for updating an existing user's profile
            query = """
                UPDATE users SET
                    email = %s, name = %s, password = %s, profile_photo = %s,
                    age = %s, gender = %s, height = %s, weight = %s,
                    goal_weight = %s, diet_preference = %s, fitness_goal = %s,
                    activity_level = %s, daily_calories = %s, dark_mode = %s,
                    medical_conditions = %s, past_surgeries = %s
                WHERE id = %s
            """
            params = (
                self.email, self.name, self.password, self.profile_photo,
                self.age, self.gender, self.height, self.weight,
                self.goal_weight, self.diet_preference, self.fitness_goal,
                self.activity_level, self.daily_calories, self.dark_mode,
                self.medical_conditions, self.past_surgeries, self.id
            )
            db.execute_query(query, params, commit=True)
        else:
            # This query is for creating a brand new user
            query = """
                INSERT INTO users (email, name, password, profile_photo, age, 
                                   gender, height, weight, goal_weight, diet_preference, 
                                   fitness_goal, activity_level, daily_calories, dark_mode,
                                   medical_conditions, past_surgeries)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                self.email, self.name, self.password, self.profile_photo, self.age, 
                self.gender, self.height, self.weight, self.goal_weight, self.diet_preference, 
                self.fitness_goal, self.activity_level, self.daily_calories, self.dark_mode,
                self.medical_conditions, self.past_surgeries
            )
            db.execute_query(query, params, commit=True)
            # Get the new ID for the user object
            self.id = db.execute_query("SELECT LAST_INSERT_ID()", fetch_one=True)['LAST_INSERT_ID()']
            
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def calculate_daily_calories(user):
    if not all([user.gender, user.weight, user.height, user.age, user.activity_level, user.fitness_goal]):
        return 2000
    if user.gender == 'male':
        bmr = 88.362 + (13.397 * float(user.weight)) + (4.799 * float(user.height)) - (5.677 * int(user.age))
    else:
        bmr = 447.593 + (9.247 * float(user.weight)) + (3.098 * float(user.height)) - (4.330 * int(user.age))
    activity_multiplier = {'sedentary': 1.2, 'light': 1.375, 'moderate': 1.55, 'active': 1.725, 'very_active': 1.9}.get(user.activity_level, 1.2)
    tdee = bmr * activity_multiplier
    if user.fitness_goal == 'lose': return tdee - 500
    elif user.fitness_goal == 'gain': return tdee + 500
    else: return tdee


@app.route('/toggle-dark-mode', methods=['POST'])
@login_required
def toggle_dark_mode():
    try:
        current_user.dark_mode = not current_user.dark_mode
        current_user.save()
        return jsonify({'success': True, 'dark_mode': current_user.dark_mode})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/')
def index():
    # If the user is already logged in, redirect them to the dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    # Otherwise, show the new landing page
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.get_by_email(request.form.get('email'))
        if not user or not check_password_hash(user.password, request.form.get('password')):
            flash('Please check your login details and try again.', 'error')
            return redirect(url_for('login'))
        login_user(user, remember=True if request.form.get('remember') else False)
        return redirect(url_for('dashboard'))
    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        if User.get_by_email(request.form.get('email')):
            flash('Email address already exists', 'error')
            return redirect(url_for('register'))
        new_user = User({
            'id': None, 'email': request.form.get('email'), 'name': request.form.get('name'), 
            'password': generate_password_hash(request.form.get('password')),
            'created_at': datetime.utcnow()
        })
        new_user.save()
        login_user(new_user)
        flash('Welcome! Please complete your profile to continue.', 'success')
        return redirect(url_for('profile'))
    return render_template('auth/register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        try:
            # Handle photo upload
            if 'profile_photo' in request.files:
                file = request.files['profile_photo']
                if file and file.filename != '':
                    # Your file saving logic here...
                    filename = secure_filename(f"user_{current_user.id}_{datetime.now().timestamp()}.{file.filename.rsplit('.', 1)[1].lower()}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    current_user.profile_photo = filename
            
            # Update user attributes from the form
            current_user.name = request.form.get('name')
            current_user.email = request.form.get('email')
            current_user.gender = request.form.get('gender')
            current_user.age = int(request.form.get('age', 0))
            current_user.height = float(request.form.get('height', 0))
            current_user.weight = float(request.form.get('weight', 0))
            current_user.goal_weight = float(request.form.get('goal_weight', 0))
            current_user.diet_preference = request.form.get('diet_preference')
            current_user.fitness_goal = request.form.get('fitness_goal')
            current_user.activity_level = request.form.get('activity_level')

            # --- THIS IS THE MISSING PART ---
            current_user.medical_conditions = request.form.get('medical_conditions')
            current_user.past_surgeries = request.form.get('past_surgeries')
            
            # Recalculate daily calories
            current_user.daily_calories = calculate_daily_calories(current_user)
            
            # Now, call the save method to update the database
            current_user.save()
            flash('Profile updated successfully!', 'success')

        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'error')
        
        return redirect(url_for('profile'))

    return render_template('profile.html', user=current_user)

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        today = datetime.utcnow().date()
        
        # Profile completeness check
        if not all([current_user.age, current_user.height, current_user.weight, current_user.daily_calories]):
            flash('Please complete your profile for a personalized experience.', 'warning')
            return redirect(url_for('profile'))

        # --- NEW: Daily Motivational Quote Logic ---
        today_str = today.isoformat()
        if session.get('quote_date') != today_str:
            session['daily_quote'] = get_daily_quote()
            session['quote_date'] = today_str
        
        daily_quote = session.get('daily_quote')

        # --- Data Fetching ---
        thirty_days_ago = today - timedelta(days=29)
        seven_days_ago = today - timedelta(days=6)

        user_meals_today = db.execute_query("SELECT * FROM meal_logs WHERE user_id = %s AND DATE(date) = %s", (current_user.id, today), fetch_all=True) or []
        user_workouts_today = db.execute_query("SELECT * FROM workout_logs WHERE user_id = %s AND DATE(date) = %s", (current_user.id, today), fetch_all=True) or []
        
        weight_data = db.execute_query("SELECT date, weight FROM weight_logs WHERE user_id = %s AND DATE(date) >= %s ORDER BY date", (current_user.id, thirty_days_ago), fetch_all=True) or []
        calorie_trend_data = db.execute_query(
            """SELECT DATE(date) as log_date, SUM(calories) as total_calories 
               FROM meal_logs WHERE user_id = %s AND DATE(date) >= %s 
               GROUP BY DATE(date) ORDER BY log_date""",
            (current_user.id, seven_days_ago),
            fetch_all=True
        ) or []

        # --- Metric Calculations ---
        total_calories = sum(float(meal.get('calories', 0)) for meal in user_meals_today)
        workout_calories = sum(float(workout.get('calories_burned', 0)) for workout in user_workouts_today)
        streak = calculate_streak(current_user.id)
        
        # --- Generate Graphs as Base64 Images ---
        weight_graph_img = None
        if weight_data and len(weight_data) > 1:
            weight_dates = [entry['date'].strftime('%b %d') for entry in weight_data]
            weights = [float(entry['weight']) for entry in weight_data]
            weight_graph_img = create_plot(weight_dates, weights, "Weight Progress (30 Days)", "Weight (kg)", "#4f46e5")

        calorie_graph_img = None
        date_map = { (seven_days_ago + timedelta(days=i)).strftime('%b %d'): 0 for i in range(7) }
        for row in calorie_trend_data:
            date_map[row['log_date'].strftime('%b %d')] = float(row['total_calories'])
        
        if any(v > 0 for v in date_map.values()):
             calorie_graph_img = create_plot(list(date_map.keys()), list(date_map.values()), "Calorie Trend (7 Days)", "Calories (kcal)", "#10b981")

        # --- AI Plan Generation ---
        diet_plan_html = get_or_create_plan_html(current_user, today, 'diet')
        workout_plan_html = get_or_create_plan_html(current_user, today, 'workout')

        return render_template('dashboard.html',
            total_calories=total_calories,
            workout_calories=workout_calories,
            weight_graph_img=weight_graph_img,
            calorie_graph_img=calorie_graph_img,
            streak=streak,
            daily_goal=current_user.daily_calories,
            diet_plan_html=diet_plan_html,
            workout_plan_html=workout_plan_html,
            user_meals_today=user_meals_today,
            user_workouts_today=user_workouts_today,
            daily_quote=daily_quote  # --- MODIFIED: Pass the new quote to the template ---
        )
    except Exception as e:
        print(f"--- CRITICAL DASHBOARD ERROR ---")
        import traceback
        traceback.print_exc()
        print(f"---------------------------------")
        flash(f"A critical error occurred while loading the dashboard. Please check your profile information.", "error")
        return redirect(url_for('profile'))
    
# --- NEW: Helper function to get/create AI plans ---
def get_or_create_plan_html(user, date, plan_type):
    """
    Checks for a cached daily plan in the database. 
    If not found, it generates a new one using the AI and saves it.
    """
    # --- FIX IS HERE: Use user.id instead of passing the whole user object ---
    query = "SELECT html_content FROM daily_plans WHERE user_id = %s AND date = %s AND plan_type = %s"
    existing_plan = db.execute_query(query, (user.id, date, plan_type), fetch_one=True)

    if existing_plan and existing_plan['html_content']:
        return existing_plan['html_content']

    # If not, generate a new plan using the AI
    html_content = ""
    try:
        if plan_type == 'diet':
            ai_response_str = get_ai_diet_suggestion(user) or ""
            for item in ai_response_str.split(';'):
                if ':' in item and len(item.split(':')) == 3:
                    meal_type, food, cals = item.split(':')
                    html_content += f"""<li class="plan-item" data-name="{food}" data-calories="{float(cals)}" data-type="meal"><input type="checkbox"><div class="item-details"><div class="item-name">{meal_type}: {food}</div><div class="item-info">{float(cals):.0f} kcal</div></div><div class="item-actions"><button class="edit-btn"><i class="fas fa-pencil-alt"></i></button></div></li>"""
        
        elif plan_type == 'workout':
            ai_response_str = get_ai_workout_plan(user) or ""
            for item in ai_response_str.split(';'):
                if ':' in item and len(item.split(':')) == 3:
                    cat, ex, cals = item.split(':')
                    html_content += f"""<li class="plan-item" data-name="{ex}" data-calories="{float(cals)}" data-type="workout"><input type="checkbox"><div class="item-details"><div class="item-name">{cat}: {ex}</div><div class="item-info">{float(cals):.0f} kcal burned</div></div><div class="item-actions"><button class="edit-btn"><i class="fas fa-pencil-alt"></i></button></div></li>"""
        
        if html_content:
            save_query = """
                INSERT INTO daily_plans (user_id, date, plan_type, html_content) 
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE html_content = VALUES(html_content)
            """
            db.execute_query(save_query, (user.id, date, plan_type, html_content), commit=True)

    except Exception as e:
        print(f"CRITICAL ERROR generating AI {plan_type} plan: {e}")
        return ""

    return html_content

# --- NEW: API endpoint for smart food logging ---
@app.route('/api/get-food-details', methods=['POST'])
@login_required
def get_food_details():
    food_query = request.json.get('food_name')
    if not food_query:
        return jsonify({'success': False, 'error': 'Food name is required.'}), 400
    
    try:
        # This calls your AI function to get nutrition data
        # Example return: {"calories": 95, "protein": 1.3, "carbs": 25, "fat": 0.3}
        nutrition_data = get_nutrition_info(food_query) 
        
        if not nutrition_data:
            return jsonify({'success': False, 'error': 'Could not find nutrition data for this food.'}), 404
            
        return jsonify({'success': True, 'data': nutrition_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def calculate_streak(user_id):
    query = """
        WITH DateSeries AS (
            SELECT DISTINCT DATE(date) as log_date FROM meal_logs WHERE user_id = %s
        ),
        DateGroups AS (
            SELECT log_date, DATE_SUB(log_date, INTERVAL DENSE_RANK() OVER (ORDER BY log_date) DAY) as grp
            FROM DateSeries
        )
        SELECT COUNT(*) as streak_length FROM DateGroups WHERE grp = (SELECT grp FROM DateGroups ORDER BY log_date DESC LIMIT 1)
    """
    result = db.execute_query(query, (user_id,), fetch_one=True)
    return result['streak_length'] if result and result['streak_length'] is not None else 0
    

@app.route('/log_item_from_dashboard', methods=['POST'])
@login_required
def log_item_from_dashboard():
    try:
        data = request.get_json()
        item_type = data.get('type')
        if item_type == 'meal':
            db.execute_query("INSERT INTO meal_logs (user_id, name, calories, date) VALUES (%s, %s, %s, %s)",
                             (current_user.id, data.get('name'), int(data.get('calories',0)), datetime.utcnow()), commit=True)
        elif item_type == 'workout':
            db.execute_query("INSERT INTO workout_logs (user_id, type, calories_burned, date) VALUES (%s, %s, %s, %s)",
                             (current_user.id, data.get('name'), int(data.get('calories',0)), datetime.utcnow()), commit=True)
        else:
            return jsonify({'success': False, 'error': 'Invalid item type'}), 400
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/log/meal', methods=['GET', 'POST'])
@login_required
def log_meal():
    if request.method == 'POST':
        try:
            # FIX: Convert form calories to float
            calories = float(request.form.get('calories', 0))
            protein = float(request.form.get('protein', 0))
            carbs = float(request.form.get('carbs', 0))
            fat = float(request.form.get('fat', 0))
            
            params = (current_user.id, request.form.get('name'), calories, protein, carbs, fat, request.form.get('notes'))
            db.execute_query("INSERT INTO meal_logs (user_id, name, calories, protein, carbs, fat, notes) VALUES (%s, %s, %s, %s, %s, %s, %s)", params, commit=True)
            
            flash('Meal logged successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Error logging meal: {str(e)}', 'error')
    return render_template('logs/meals.html')

@app.route('/api/get-workout-calories', methods=['POST'])
@login_required
def api_get_workout_calories():
    try:
        description = request.json.get('description')
        if not description:
            return jsonify({'success': False, 'error': 'Description is required'}), 400
        
        # Call the new AI function
        calorie_data = get_workout_calories(description)
        if not calorie_data:
            return jsonify({'success': False, 'error': 'Could not calculate calories'}), 500
            
        return jsonify({'success': True, 'data': calorie_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
    
@app.route('/log/workout', methods=['GET', 'POST'])
@login_required
def log_workout():
    if request.method == 'POST':
        try:
            db.execute_query(
                "INSERT INTO workout_logs (user_id, type, duration, calories_burned, notes, date) VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    current_user.id,
                    request.form.get('type'),
                    int(request.form.get('duration', 0)),
                    float(request.form.get('calories_burned', 0)),
                    request.form.get('notes'),
                    datetime.utcnow()
                ),
                commit=True
            )
            flash('Workout logged successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Error logging workout: {str(e)}', 'error')
    
    # Fetch recent workouts to display on the page
    recent_workouts = db.execute_query(
        "SELECT * FROM workout_logs WHERE user_id = %s ORDER BY date DESC LIMIT 5",
        (current_user.id,),
        fetch_all=True
    )
    return render_template('logs/workouts.html', recent_workouts=recent_workouts)


@app.route('/log/weight', methods=['GET', 'POST'])
@login_required
def log_weight():
    if request.method == 'POST':
        try:
            weight_today = float(request.form.get('weight', 0))
            db.execute_query("INSERT INTO weight_logs (user_id, weight, notes) VALUES (%s, %s, %s)", (current_user.id, weight_today, request.form.get('notes')), commit=True)
            current_user.weight = weight_today
            current_user.daily_calories = calculate_daily_calories(current_user)
            current_user.save()
            flash('Weight logged successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Error logging weight: {str(e)}', 'error')
    return render_template('logs/weight.html')


@app.route('/ai/diet', methods=['GET', 'POST'])
@login_required
def ai_diet():
    suggestion = None
    if request.method == 'POST':
        try:
            suggestion = get_ai_diet_suggestion(current_user, request.form.get('prompt', ''))
        except Exception as e:
            flash(f'Error getting diet suggestion: {str(e)}', 'error')
    return render_template('ai/diet.html', suggestion=suggestion)


@app.route('/ai/workout', methods=['GET', 'POST'])
@login_required
def ai_workout():
    plan = None
    if request.method == 'POST':
        try:
            plan = get_ai_workout_plan(current_user, request.form.get('prompt', ''))
        except Exception as e:
            flash(f'Error getting workout plan: {str(e)}', 'error')
    return render_template('ai/workout.html', plan=plan)


@app.route('/ai/weekly-summary')
@login_required
def weekly_summary():
    try:
        return jsonify({'success': True, 'summary': get_weekly_summary(current_user)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/export/pdf')
@login_required
def export_pdf():
    try:
        end_date, start_date = datetime.utcnow(), datetime.utcnow() - timedelta(days=7)
        meals = db.execute_query("SELECT * FROM meal_logs WHERE user_id = %s AND date BETWEEN %s AND %s", (current_user.id, start_date, end_date), fetch_all=True)
        workouts = db.execute_query("SELECT * FROM workout_logs WHERE user_id = %s AND date BETWEEN %s AND %s", (current_user.id, start_date, end_date), fetch_all=True)
        weights = db.execute_query("SELECT * FROM weight_logs WHERE user_id = %s AND date BETWEEN %s AND %s", (current_user.id, start_date, end_date), fetch_all=True)
        pdf_data = generate_pdf_report(current_user, meals, workouts, weights)
        return send_file(pdf_data, as_attachment=True, download_name=f"fitness_report_{end_date.strftime('%Y%m%d')}.pdf", mimetype='application/pdf')
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('dashboard'))


@app.route('/export/excel')
@login_required
def export_excel():
    try:
        end_date, start_date = datetime.utcnow(), datetime.utcnow() - timedelta(days=30)
        meals = db.execute_query("SELECT * FROM meal_logs WHERE user_id = %s AND date BETWEEN %s AND %s", (current_user.id, start_date, end_date), fetch_all=True)
        workouts = db.execute_query("SELECT * FROM workout_logs WHERE user_id = %s AND date BETWEEN %s AND %s", (current_user.id, start_date, end_date), fetch_all=True)
        weights = db.execute_query("SELECT * FROM weight_logs WHERE user_id = %s AND date BETWEEN %s AND %s", (current_user.id, start_date, end_date), fetch_all=True)
        excel_data = generate_excel_report(current_user, meals, workouts, weights)
        return send_file(excel_data, as_attachment=True, download_name=f"fitness_data_{end_date.strftime('%Y%m%d')}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'Error generating Excel file: {str(e)}', 'error')
        return redirect(url_for('dashboard'))


@app.route('/api/calories-trend')
@login_required
def calories_trend():
    try:
        end_date, start_date = datetime.utcnow().date(), datetime.utcnow().date() - timedelta(days=6)
        dates = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
        calories_data = {date: 0 for date in dates}
        results = db.execute_query("SELECT DATE(date) as log_date, SUM(calories) as total_calories FROM meal_logs WHERE user_id = %s AND DATE(date) BETWEEN %s AND %s GROUP BY DATE(date)", (current_user.id, start_date, end_date), fetch_all=True)
        for row in results:
            calories_data[row['log_date'].strftime('%Y-%m-%d')] = row['total_calories']
        return jsonify({'success': True, 'dates': dates, 'calories': [calories_data[date] for date in dates], 'goal': current_user.daily_calories})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    try:
        prompt = request.json.get('prompt')
        if not prompt:
            return jsonify({'reply': 'Please enter a message.'})

        # Get chat history from the user's session, or start a new one
        chat_history = session.get('chat_history', [])
        
        chat_history.append({"role": "user", "content": prompt})

        ai_reply = get_ai_chat_response(chat_history)

        chat_history.append({"role": "assistant", "content": ai_reply})

        session['chat_history'] = chat_history

        return jsonify({'reply': ai_reply})
    except Exception as e:
        return jsonify({'reply': f'An error occurred: {str(e)}'}), 500




if __name__ == '__main__':
    app.run(debug=True)