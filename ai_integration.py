import os
import groq
from datetime import datetime, timedelta
from config import Config
from database import db
import json

client = groq.Client(api_key=Config.GROQ_API_KEY)

def get_recent_meals(user_id):
    """Helper function to get meals from the database."""
    return db.execute_query(
        """SELECT name, calories FROM meal_logs 
           WHERE user_id = %s AND date >= %s 
           ORDER BY date DESC LIMIT 10""",
        (user_id, datetime.utcnow() - timedelta(days=3)),
        fetch_all=True
    ) or []

def get_recent_workouts(user_id):
    """Helper function to get workouts from the database."""
    return db.execute_query(
        """SELECT type, duration FROM workout_logs 
           WHERE user_id = %s AND date >= %s 
           ORDER BY date DESC LIMIT 10""",
        (user_id, datetime.utcnow() - timedelta(days=7)),
        fetch_all=True
    ) or []

def get_ai_diet_suggestion(user, prompt=""):
    try:
        recent_meals = get_recent_meals(user.id)
        
        # --- MODIFIED: Added medical history to the context ---
        context = f"""
        User Profile:
        - Age: {user.age}, Gender: {user.gender}
        - Weight: {user.weight} kg, Height: {user.height} cm
        - Goal: {user.fitness_goal} weight
        - Diet Preference: {user.diet_preference}
        - Daily Calorie Target: {user.daily_calories}
        - Medical Conditions: {user.medical_conditions or 'None specified'}
        - Past Surgeries/Injuries: {user.past_surgeries or 'None specified'}
        - Recent Meals: {[f"{meal['name']} ({meal['calories']} cal)" for meal in recent_meals]}
        """

        # --- MODIFIED: Updated system prompt ---
        system_prompt = """You are a cautious and responsible diet planning AI. Your ONLY job is to create a one-day meal plan.
        **CRITICAL RULES:**
        1. You MUST carefully consider the user's medical conditions and diet preferences. For example, for high blood pressure, suggest low-sodium foods.
        2. You MUST respond in the format: `MealType:FoodName:Calories;MealType:FoodName:Calories`.
        3. Do NOT include any text other than the plan string.
        4. If you cannot generate a safe plan, you MUST respond with the single word: `None`.
        **EXAMPLE RESPONSE:**
        Breakfast:Oatmeal with Berries:350;Lunch:Grilled Chicken Salad:450;Dinner:Salmon with Quinoa:550
        """
        
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            temperature=0.5,
            max_tokens=200
        )
        ai_response = response.choices[0].message.content
        return "" if ai_response.strip() == "None" else ai_response

    except Exception as e:
        print(f"AI Diet Suggestion Error: {str(e)}")
        return ""

def get_ai_workout_plan(user, prompt=""):
    try:
        recent_workouts = get_recent_workouts(user.id)

        # --- MODIFIED: Added medical history to the context ---
        context = f"""
        User Profile:
        - Name: {user.name}, Age: {user.age}, Gender: {user.gender}
        - Weight: {user.weight} kg, Height: {user.height} cm
        - Fitness Goal: {user.fitness_goal}
        - Activity Level: {user.activity_level}
        - Medical Conditions: {user.medical_conditions or 'None specified'}
        - Past Surgeries/Injuries: {user.past_surgeries or 'None specified'}
        - Recent Workouts: {[f"{workout['type']} ({workout['duration']} min)" for workout in recent_workouts]}
        """

        # --- MODIFIED: Updated system prompt ---
        system_prompt = """You are a cautious and responsible personal trainer AI. Your ONLY job is to create a one-day workout plan.
        **CRITICAL RULES:**
        1. You MUST create a safe workout that considers the user's medical conditions and past injuries. Avoid any exercises that could cause harm or strain.
        2. You MUST respond in the format: `Category:ExerciseName:CaloriesBurned;Category:ExerciseName:CaloriesBurned`.
        3. Do NOT include any text other than the plan string.
        4. If you cannot generate a safe plan, you MUST respond with the single word: `None`.
        **EXAMPLE RESPONSE:**
        Cardio:Brisk Walking:250;Strength:Bodyweight Squats:100;Flexibility:Gentle Stretching:50
        """
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            temperature=0.5,
            max_tokens=200
        )
        ai_response = response.choices[0].message.content
        return "" if ai_response.strip() == "None" else ai_response
    except Exception as e:
        print(f"AI Workout Plan Error: {str(e)}")
        return ""

def get_nutrition_info(food_name: str) -> dict:
    system_prompt = """Your only task is to analyze a food description and respond with a valid JSON object containing "calories", "protein", "carbs", and "fat". The values must be numbers. Example: {"calories": 260, "protein": 13.5, "carbs": 28.0, "fat": 11.2}"""
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": food_name}
            ],
            temperature=0.2,
            max_tokens=100,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error getting nutrition info from AI: {str(e)}")
        return {}
    
def get_workout_calories(workout_description: str) -> dict:
    """
    Uses AI to estimate calories burned from a workout description.
    """
    system_prompt = """You are a fitness expert AI. Your only task is to analyze a workout description and respond with a valid JSON object containing the key "calories_burned". The value must be an integer.
    Example for "running on treadmill for 30 minutes": {"calories_burned": 300}
    Example for "weight lifting 1 hour": {"calories_burned": 250}
    """
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": workout_description}
            ],
            temperature=0.1,
            max_tokens=100,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error getting workout calories from AI: {str(e)}")
        return {}

def get_weekly_summary(user):
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        
        meals = db.execute_query(
            """SELECT * FROM meal_logs WHERE user_id = %s AND date >= %s AND date <= %s""",
            (user.id, start_date, end_date), fetch_all=True
        ) or []
        workouts = db.execute_query(
            """SELECT * FROM workout_logs WHERE user_id = %s AND date >= %s AND date <= %s""",
            (user.id, start_date, end_date), fetch_all=True
        ) or []
        weights = db.execute_query(
            """SELECT * FROM weight_logs WHERE user_id = %s AND date >= %s AND date <= %s ORDER BY date""",
            (user.id, start_date, end_date), fetch_all=True
        ) or []
        
        total_calories = sum(float(meal.get('calories', 0)) for meal in meals)
        avg_daily_calories = total_calories / 7 if meals else 0
        calorie_goal_met = (avg_daily_calories / float(user.daily_calories) * 100) if user.daily_calories else 0
        total_workout_minutes = sum(float(workout.get('duration', 0)) for workout in workouts)
        total_calories_burned = sum(float(workout.get('calories_burned', 0)) for workout in workouts)
        weight_change = float(weights[-1].get('weight', 0)) - float(weights[0].get('weight', 0)) if len(weights) >= 2 else 0
        
        context = f"""
        Weekly Fitness Summary for {user.name}:
        Nutrition:
        - Total Calories Consumed: {total_calories}
        - Average Daily Calories: {avg_daily_calories:.0f}
        - Daily Calorie Goal: {user.daily_calories}
        - Goal Met: {calorie_goal_met:.1f}%
        Exercise:
        - Total Workout Time: {total_workout_minutes} minutes
        - Total Calories Burned: {total_calories_burned}
        Weight:
        - Starting Weight: {weights[0].get('weight', 'N/A') if weights else 'N/A'} kg
        - Ending Weight: {weights[-1].get('weight', 'N/A') if weights else 'N/A'} kg
        - Change: {weight_change:.1f} kg
        """
        system_prompt = """You are a fitness coach AI assistant. Analyze the user's weekly summary and provide encouraging feedback and actionable tips for the next week. Keep it concise and positive."""
        
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            temperature=0.7,
            max_tokens=1024
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Weekly Summary Error: {str(e)}")
        return "Could not generate weekly summary. Please try again later."
    
def get_ai_chat_response(message_history: list) -> str:
    """
    Gets a conversational response from the AI, using the chat history.
    """
    system_prompt = "You are a friendly and knowledgeable fitness assistant named FitBot. Your goal is to help users with their diet, workout, and general health questions. Keep your answers concise and encouraging."
    
    # The message history is passed directly to the AI
    messages_to_send = [{"role": "system", "content": system_prompt}] + message_history
    
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=messages_to_send,
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI Chat Error: {str(e)}")
        return "Sorry, I'm having trouble connecting right now. Please try again in a moment."
    
def get_daily_quote():
    """Gets a short, motivational fitness quote from the AI."""
    try:
        system_prompt = "You are a motivational coach. Your only task is to provide one short, powerful, and inspiring fitness or health-related quote. Do not include quotation marks or any other text."
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "system", "content": system_prompt}],
            temperature=1.2, # Make it creative
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"AI Quote Error: {str(e)}")
        # Provide a fallback quote in case the AI fails
        return "The only bad workout is the one that didn't happen."