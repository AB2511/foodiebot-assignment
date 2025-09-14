import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
from pydantic import BaseModel, Field
from typing import List

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Define the Pydantic model for validation (not for schema generation)
class Product(BaseModel):
    product_id: str = Field(description="Unique ID like FF001")
    name: str
    category: str
    description: str
    ingredients: List[str]
    price: float
    calories: int
    prep_time: str = Field(description="Time like '8-10 mins'")
    dietary_tags: List[str]
    mood_tags: List[str]
    allergens: List[str]
    popularity_score: int = Field(ge=0, le=100)
    chef_special: bool
    limited_time: bool
    spice_level: int = Field(ge=0, le=10)
    image_prompt: str

class ProductsList(BaseModel):
    products: List[Product]

# Categories from the assignment
categories = [
    "Burgers (classic, fusion, vegetarian)",
    "Pizza (traditional, gourmet, personal)",
    "Fried Chicken (wings, tenders, sandwiches)",
    "Tacos & Wraps (mexican, fusion, healthy)",
    "Sides & Appetizers (fries, onion rings, etc.)",
    "Beverages (sodas, shakes, specialty drinks)",
    "Desserts (ice cream, cookies, pastries)",
    "Salads & Healthy Options",
    "Breakfast Items (all-day breakfast)",
    "Limited Time Specials"
]

all_products = []
start_id = 1
model = genai.GenerativeModel('gemini-1.5-flash')  # Fast, free model

for category in categories:
    print(f"Generating for {category}...")
    
    # Detailed prompt with explicit JSON structure
    prompt = f"""
    Generate exactly 10 unique, realistic fast food products in this category: {category}.
    Ensure variety (e.g., classic, fusion, healthy options where applicable).
    Use sequential product_ids starting from FF{start_id:03d}.
    Output ONLY a valid JSON object with this structure:
    {{
        "products": [
            {{
                "product_id": "FFXXX",
                "name": "Product Name",
                "category": "Category Name",
                "description": "Detailed description",
                "ingredients": ["ingredient1", "ingredient2"],
                "price": 10.99,
                "calories": 500,
                "prep_time": "8-10 mins",
                "dietary_tags": ["vegetarian", "spicy"],
                "mood_tags": ["fun", "comfort"],
                "allergens": ["nuts", "gluten"],
                "popularity_score": 75,
                "chef_special": true,
                "limited_time": false,
                "spice_level": 5,
                "image_prompt": "A colorful photo of the product"
            }}
            // Repeat the above object 9 more times with unique data
        ]
    }}
    Make descriptions creative and detailed. Prices between $5-15, calories 200-900, spice_level 0-10.
    Dietary/mood/allergens tags should be relevant (e.g., ['spicy', 'vegetarian']).
    Do not include any text outside the JSON object.
    """
    
    # Generate content
    response = model.generate_content(
        prompt,
        generation_config={
            "response_mime_type": "application/json",  # Enforces JSON output
            "temperature": 0.7,
            "max_output_tokens": 4096
        }
    )
    
    if response.text:
        try:
            # Parse and validate the JSON response
            generated_data = json.loads(response.text)
            generated_products = [Product(**p) for p in generated_data['products']]  # Validate with Pydantic
            all_products.extend(generated_products)
            start_id += 10
        except json.JSONDecodeError as e:
            print(f"JSON parsing error for {category}: {e}. Skipping this batch.")
        except ValueError as e:
            print(f"Validation error for {category}: {e}. Skipping this batch.")
    else:
        print(f"No response for {category}. Check API key or quota.")

# Save to JSON
with open('products.json', 'w') as f:
    json.dump({"products": [p.dict() for p in all_products]}, f, indent=2)

print(f"Generated {len(all_products)} products in products.json")