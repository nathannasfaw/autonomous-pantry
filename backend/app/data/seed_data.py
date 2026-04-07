# Simulates YOLO camera output
PANTRY = [
    {"item": "sushi rice", "quantity": 2.0, "unit": "cups", "confidence": 0.91},
    {"item": "soy sauce", "quantity": 1.0, "unit": "bottle", "confidence": 0.88},
    {"item": "sesame oil", "quantity": 0.5, "unit": "bottle", "confidence": 0.76},
    {"item": "nori", "quantity": 1.0, "unit": "sheets", "confidence": 0.95},
    {"item": "olive oil", "quantity": 1.0, "unit": "bottle", "confidence": 0.89},
    {"item": "garlic", "quantity": 3.0, "unit": "cloves", "confidence": 0.84},
    {"item": "mozzarella", "quantity": 0.2, "unit": "lbs", "confidence": 0.72},
    {"item": "eggs", "quantity": 4.0, "unit": "count", "confidence": 0.93},
]

# Simulates Google Calendar output
CALENDAR = {
    "events_this_week": [
        {"title": "Dinner party", "guests": 5, "day": "Friday", "cuisine_hint": "Japanese"},
        {"title": "Lunch with family", "guests": 3, "day": "Sunday", "cuisine_hint": None}
    ],
    "tonight_guests": 2
}

# Simulates preference form + learned chat history
PREFERENCES = {
    "dietary_flags": [],
    "cuisine_weights": {"Japanese": 0.85, "Italian": 0.70, "Mexican": 0.55},
    "budget_per_order": 80.0,
    "budget_per_person": 20.0,
    "quality_priority": 0.5,       # 0 = price-focused, 1 = quality-focused
    "preferred_organic": False,
    "disliked_ingredients": [],
    "household_size": 2,
    "serving_size": 2,             # default servings per meal
    "skill_level": "intermediate", # beginner, intermediate, advanced
    "max_prep_time": 60,           # minutes, 0 = no limit
}
