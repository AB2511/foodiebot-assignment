# FoodieBot: Database-Driven Conversational Fast Food System

This is my implementation for the Tecnvirons Pvt Ltd AI Food Agent Internship Assignment. Deadline: September 15, 2025. I used Gemini API as an alternative to Grok for data generation in Phase 1. The system analyzes conversations, calculates interest scores, and recommends from a 100-product database in real-time.

## Assignment Overview
Created an intelligent AI bot that works with pre-generated fast food data in SQLite. It analyzes user conversations, computes interest scores based on engagement factors (preferences, dietary, budget, mood, enthusiasm, order intent) and negative factors (rejection, no match), and provides real-time recommendations. Includes a Streamlit UI for chat and analytics.

## Phase 1: Product Data Generation & Database Setup
- **Generation**: Used Gemini API to generate 100 unique fast food products across 10 categories (e.g., 10 Burgers, 10 Pizzas, 10 Tacos & Wraps, etc.). Follows the exact JSON structure from the assignment (product_id, name, category, description, ingredients as array, price, calories, prep_time, dietary_tags, mood_tags, allergens, popularity_score, chef_special, limited_time, spice_level, image_prompt).
- **Dataset**: See `products.json` (100 entries, FF001-FF100). Example: {"product_id": "FF001", "name": "Classic Cheeseburger", ...}.
- **Database**: SQLite (`foodiebot.db`) with `products` table (comma-separated strings for lists, booleans as 1/0). Added indexes for fast queries (sub-100ms: category, price, spice_level, dietary_tags, mood_tags). Also created `conversations` table for logging.
- **Setup**: Run `python setup_db.py` to load data and create tables/indexes. Verified: 100 products.

## Phase 2: Conversational AI with Interest Scoring
- **LLM**: Gemini 1.5 Flash for natural responses (free tier, optional; currently rule-based). Context is maintained (e.g., "vegetarian" carries over).
- **Scoring**: Keyword-based system in `chat_engine.py`:
  - Positive: +15 for "spicy"/preferences, +10 for "vegetarian"/restrictions, +5 for budget, +20 for mood like "adventurous", +10 for questions, +8 for enthusiasm like "love", +30 for order intent.
  - Negative: -20 for no match, -25 for rejection.
  - Scores capped at 0-100%. Example: "I’m vegetarian" = 10%; "What’s spicy?" = 25%; "Any spicy vegetarian curry under $8?" (no match) = 0%.
- **Chat Logic**: `chat_engine.py` parses input (e.g., "spicy" sets spice_min=5, "under $8" sets price_max=8), queries DB, and generates responses. Logs to `conversations` table.
- **Test**: Run `python chat_engine.py` for terminal chat.

## Phase 3: Smart Recommendation & Analytics System
- **Recommendations**: Real-time DB queries (`query_database`) with filters (price, spice, dietary tags via LIKE '%vegetarian%'). Orders by popularity_score, limits to 20. Example: "show me burgers" lists 5 vegetarian options.
- **Analytics**: Streamlit dashboard (`app.py`) shows interest progression graph (matplotlib), average interest (excludes 0%), and unique dietary mentions. Updates live after chats.
- **UI**: Streamlit for chat interface, sidebar with analytics and product admin table (pandas dataframe).

## Setup Instructions
1. Install dependencies: `pip install google-generativeai streamlit pandas matplotlib sqlite3 python-dotenv pydantic`.
2. Add Gemini API key to `.env`: `GEMINI_API_KEY=your_key_here` (get from aistudio.google.com).
3. Run `python setup_db.py` to create/load DB.
4. Run `streamlit run app.py` for UI[](http://localhost:8501).
5. Test queries: See live demo.

## Live Demo
- **Link**: [Live Demo](https://foodiebotchat.streamlit.app/)
- Test queries: `show me burgers`, `I want vegan wraps`, `Any spicy vegetarian curry under $8?`, `Less than 10 dollars pasta`.

## Testing Queries (Demo)
- "I’m vegetarian": Filters dietary, scores 10%.
- "What’s spicy?": Applies context, scores 25%.
- "I want something under $7": Budget filter, scores 5%.
- "Spicy vegetarian under $10": Multi-filter, scores 30% (if matches).
- "I’ll take the Mediterranean Veggie Burger": Order intent, high score.
- "Maybe that’s too expensive, I don’t like it": Negative factors, low score.
- "I love spicy food, amazing!": Enthusiasm, high score.

## Challenges & Fixes
- **Content Gaps**: No spicy vegetarian curries under $8 or pasta under $10 in DB. Fixed by suggesting DB expansion in setup.
- **Scoring**: Initial inconsistency for no-match cases resolved; now caps at 0% with `dietary_conflict`.
- **Analytics**: Averaging excludes 0% turns for accuracy.
- **Response Quality**: Rule-based fallback ("No matching products...") is functional but lacks engagement; LLM optional for improvement.

## Technologies
- Python, SQLite, Gemini API (optional), Streamlit, Pandas, Matplotlib.

## Submission Notes
- GitHub repo: [https://github.com/AB2511/foodiebot-assignment](https://github.com/AB2511/foodiebot-assignment)
- Contact: Anjali Barge [bargeanjali650@gmail.com](mailto:bargeanjali650@gmail.com)

This meets all phases of the assignment. Thank you!
