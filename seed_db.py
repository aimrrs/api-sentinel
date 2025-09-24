# This script is run once to populate the database with initial data.

# We must import the same way our app does to find the modules
from database import SessionLocal
from models import ApiPricing

# Create a new database session
db = SessionLocal()

print("Seeding database with initial API pricing data...")

# --- Define the pricing data ---
# Prices are per 1 million tokens in USD
pricing_data = [
    {
        "api_name": "openai",
        "model_name": "gpt-4o",
        "input_cost_per_million_usd": 5.00,
        "output_cost_per_million_usd": 15.00,
    },
    {
        "api_name": "openai",
        "model_name": "gpt-4-turbo",
        "input_cost_per_million_usd": 10.00,
        "output_cost_per_million_usd": 30.00,
    },
    {
        "api_name": "openai",
        "model_name": "gpt-3.5-turbo",
        "input_cost_per_million_usd": 0.50,
        "output_cost_per_million_usd": 1.50,
    },
        {
        "api_name": "openai",
        "model_name": "gpt-oss-20b",
        "input_cost_per_million_usd": 0.20,
        "output_cost_per_million_usd": 0.30,
    },
    {
        "api_name": "openai",
        "model_name": "gemma-7b-it",
        "input_cost_per_million_usd": 0.80,
        "output_cost_per_million_usd": 1.20,
    },
    {
        "api_name": "openai",
        "model_name": "eleutherai/llemma_7b",
        "input_cost_per_million_usd": 0.80,
        "output_cost_per_million_usd": 1.20,
    },
    {
        "api_name": "openai",
        "model_name": "google/gemma-7b-it",
        "input_cost_per_million_usd": 0.80,
        "output_cost_per_million_usd": 1.20,
    },
    {
        "api_name": "openai",
        "model_name": "google/gemma-3n-e2b-it:free",
        "input_cost_per_million_usd": 0.80,
        "output_cost_per_million_usd": 1.20,
    },
    {
        "api_name": "openai",
        "model_name": "llama3-8b-8192",
        "input_cost_per_million_usd": 0.5,
        "output_cost_per_million_usd": 1.30,
    },
    {
        "api_name": "openai", # It's still OpenAI-compatible
        "model_name": "llama3-70b-8192", # <-- The new, current, and powerful model
        "input_cost_per_million_usd": 0.60,
        "output_cost_per_million_usd": 1.20,
    },
    {
        "api_name": "openai",
        "model_name": "gemma-7b-it", # <-- The stable, available Groq model
        "input_cost_per_million_usd": 1.20,
        "output_cost_per_million_usd": 0.50,
    },
    {
        "api_name": "openai", # OpenAI-compatible
        "model_name": "openai/gpt-oss-20b", # <-- The official model from your successful test
        "input_cost_per_million_usd": 1.20,
        "output_cost_per_million_usd": 0.30,
    },
]

try:
    for item in pricing_data:
        # Check if the model already exists to prevent adding duplicates
        # if the script is accidentally run more than once.
        exists = db.query(ApiPricing).filter(ApiPricing.model_name == item["model_name"]).first()
        if not exists:
            new_price = ApiPricing(**item)
            db.add(new_price)
            print(f"  - Adding pricing for {item['model_name']}")
    
    # Commit all the changes to the database
    db.commit()
    print("Seeding successful!")

except Exception as e:
    print(f"An error occurred during seeding: {e}")
    db.rollback() # If an error occurs, undo any changes

finally:
    # Always close the database session
    db.close()