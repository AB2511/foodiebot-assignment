# FoodieBot: Database-Driven Conversational Fast Food System

This is my implementation for the Tecnvirons Pvt Ltd AI Food Agent Internship Assignment. Deadline: September 15, 2025. I used Gemini API as an alternative to Grok for data generation in Phase 1. The system analyzes conversations, calculates interest scores, and recommends from a 100-product database in real-time.

## Assignment Overview
Created an intelligent AI bot that works with pre-generated fast food data in SQLite. It analyzes user conversations, computes interest scores based on factors (preferences, dietary, budget, mood, enthusiasm, negatives like rejection), and recommends products. Includes Streamlit UI for chat and analytics.

## Phase 1: Product Data Generation & Database Setup
- **Generation**: Used Gemini API to generate 100 unique fast food products across 10 categories (10 each: Burgers, Pizza, Fried Chicken, Tacos & Wraps, Sides & Appetizers, Beverages, Desserts, Salads & Healthy Options, Breakfast Items, Limited Time Specials). Follows exact JSON structure from assignment (e.g., product_id, name, category, description, ingredients as array, price, calories, prep_time, dietary_tags, mood_tags, allergens, popularity_score, chef_special, limited_time, spice_level, image_prompt).
- **Dataset**: See `products.json` (100 entries, FF001-FF100). Example: {"product_id": "FF001", "name": "Classic Cheeseburger", ...}.
- **Database**: SQLite (`foodiebot.db`) with `products` table (comma-separated strings for lists, booleans as 1/0). Added indexes for fast queries (sub-100ms: category, price, spice_level, dietary_tags, mood_tags). Also created `conversations` table for logging.
- **Setup**: Run `python setup_db.py` to load data and create tables/indexes. Verified: 100 products.

## Phase 2: Conversational AI with Interest Scoring
- **LLM**: Gemini 1.5 Flash for natural responses (free tier). Prompt maintains context (e.g., "vegetarian" carries over).
- **Scoring**: Keyword-based (e.g., +15 for "spicy"/preferences, +10 for "vegetarian"/restrictions, +5 for budget, +20 for mood like "adventurous", +10 for questions, +8 for enthusiasm like "love", +30 for order intent; negatives: -20 for no match, -25 for rejection). Scores 0-100%. Example: "I’m vegetarian" = 10%; "What’s spicy?" = 25%.
- **Chat Logic**: `chat_engine.py` parses input (e.g., "spicy" sets spice_min=5, "under $10" sets price_max=10), queries DB, feeds to Gemini for response. Logs to `conversations` table.
- **Test**: Run `python chat_engine.py` for terminal chat.

## Phase 3: Smart Recommendation & Analytics System
- **Recommendations**: Real-time DB queries (`query_database`) with filters (price, spice, dietary tags via LIKE '%vegetarian%'). Orders by popularity_score, limits to 3. Example: Spicy vegetarian under $10 combines filters.
- **Analytics**: Streamlit dashboard (`app.py`) shows interest progression graph (matplotlib), average interest (excludes 0%), unique dietary mentions. Updates live after chats.
- **UI**: Streamlit for chat interface, sidebar with analytics and product admin table (pandas dataframe).

## Setup Instructions
1. Install dependencies: `pip install google-generativeai streamlit pandas matplotlib sqlite3 python-dotenv pydantic`.
2. Add Gemini API key to `.env`: `GEMINI_API_KEY=your_key_here` (get from aistudio.google.com).
3. Run `python setup_db.py` to create/load DB.
4. Run `streamlit run app.py` for UI[](http://localhost:8501).
5. Test queries: See demo video [link].

## Testing Queries (Demo)
- "I’m vegetarian": Filters dietary, scores 10%.
- "What’s spicy?": Applies context, scores 25%.
- "I want something under $7": Budget filter, scores 5%.
- "Spicy vegetarian under $10": Multi-filter, scores 30%.
- "I’ll take the Mediterranean Veggie Burger": Order intent, high score.
- "Maybe that’s too expensive, I don’t like it": Negative factors, low score.
- "I love spicy food, amazing!": Enthusiasm, high score.

## Challenges & Fixes
- **Hallucination**: Prompt restricts to DB products; if no match, says "No matching products found." Occasional LLM invention mitigated but not fully resolved.
- **Analytics**: Averaging excludes 0% turns for accuracy.
- **Data Variety**: 100 products with tags for mood/diet/spice ensure diverse filtering.

## Demo Video
 [Demo](https://youtube.com/watch?v=yourvideo). Shows live chat, recommendations, analytics.

## Technologies
- Python, SQLite, Gemini API, Streamlit, Pandas, Matplotlib.

## Submission Notes
- Excludes `.env` (API key) and optionally `foodiebot.db` (binary, recreatable with setup_db.py).
- GitHub repo: [Repo](https://github.com/AB2511/foodiebot-assignment)
- Contact: Anjali Barge [Email](bargeanjali650@gmail.com)

This meets all phases of the assignment. Thank you!
