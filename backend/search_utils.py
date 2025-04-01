#!/usr/bin/env python3
"""
Search Utilities Module

This module provides utility functions for text search and keyword extraction
to be used with the MongoDB API server for hotel, restaurant and other searches.

Examples:
uv run search_utils.py --type load_trip --trip_id 67d8a1e36efdc1eb41168f34

"""

import argparse
import json
import re
import os
from dotenv import load_dotenv

from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.json_util import dumps, loads
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

# Filter out common stop words and short words
stop_words = set(['the', 'and', 'or', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'with', 
                'by', 'about', 'as', 'of', 'from', 'that', 'this', 'it', 'is', 'are', 
                'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 
                'did', 'will', 'would', 'should', 'could', 'can', 'may', 'might', 'must',
                'i', 'you', 'he', 'she', 'we', 'they', 'me', 'him', 'her', 'us', 'them'])

# US state abbreviation to full name mapping
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", 
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", 
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", 
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", 
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", 
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", 
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", 
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", 
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", 
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", 
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", 
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", 
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia"
}

# Create a reverse mapping (full name to abbreviation)
US_STATE_ABBREVS = {v: k for k, v in US_STATES.items()}

def load_trip(trip_id, db):
    if trip_id is None or trip_id == "":
        print(f"Trip ID is empty or None, can't find trip")
        return None
    
    try:
        # Convert trip_id to ObjectId
        trip_obj_id = ObjectId(trip_id)
        
        # Get trip data from MongoDB
        trip_data = db.trips.find_one({"_id": trip_obj_id})
        return trip_data
    except Exception as e:
        print(f"Error loading trip data with trip_id: {trip_id}: {e}")
        return None

def extract_search_trip_data_str(trip_data) -> str:
    if not trip_data:
        print(f"Can't extract trip data string from None trip data.")
        return None
    
    trip_data_string = "Trip data:\n"
    
    # Extract relevant fields for search.
    trip_title = trip_data.get('name', '')
    trip_data_string = f"Trip Name: {trip_title}\n"

    destination = trip_data.get('destination', "")
    destination_city = destination.get('city', '')
    destination_state = destination.get('state', '')
    destination_country = destination.get('country', 'United States')
    
    trip_data_string += f"- destinationCity: {destination_city}\n"
    trip_data_string += f"- destinationState: {destination_state}\n"
    trip_data_string += f"- destinationCountry: {destination_country}\n"
    
    start_date = trip_data.get('startDate', 'N/A')
    end_date = trip_data.get('endDate', 'N/A')
    
    # Format dates to remove time portion (if they're valid dates)
    if start_date != 'N/A' and isinstance(start_date, str) and 'T' in start_date:
        start_date = start_date.split('T')[0]  # Keep only the date part before 'T'
    if end_date != 'N/A' and isinstance(end_date, str) and 'T' in end_date:
        end_date = end_date.split('T')[0]  # Keep only the date part before 'T'
        
    trip_data_string += f"- startDate: {start_date}\n"
    trip_data_string += f"- endDate: {end_date}\n"
    
    # Debug other key fields
    total_budget = trip_data.get('totalBudget', '')
    trip_data_string += f"- totalBudget: {total_budget}\n"
    
    notes = trip_data.get('notes', '')
    trip_data_string += f"- notes: {notes}\n"
    
    # Get purpose field (if available)
    purpose = trip_data.get('purpose', '')
    trip_data_string += f"- purpose: {purpose}"

    return trip_data_string

def extract_generic_trip_search_keywords_no_llm(trip_data) -> str:

    def extract_keywords(text: str) -> list[str]:
        # Extract meaningful words from purpose
        words = [word.lower() for word in re.findall(r'\b[a-zA-Z]+\b', str(text))]
        
        # Filter out stop words and short words (less than 3 characters)
        meaningful_words = [word for word in words if word not in stop_words and len(word) > 2]
        return meaningful_words

    # Extract relevant keywords from trip data
    search_keywords = []
    
    # Add keywords from title
    title = trip_data.get('name', '')
    if title:
        search_keywords.extend(extract_keywords(title))
    
    # Add keywords from purpose
    purpose = trip_data.get('purpose', '')
    if purpose:
        search_keywords.extend(extract_keywords(purpose))
    
    # Add keywords from notes
    notes = trip_data.get('notes', '')
    if notes:
        search_keywords.extend(extract_keywords(notes))
    
    return set(search_keywords)

def generate_trip_hotel_search_keywords_with_llm(trip_data_string, openai_api_key) -> str:
    """
    Generate hotel listing keywords to search trip advisor hotel listings stores in monfo with bm25.
    """

    if not openai_api_key:
        print("Warning: OPENAI_API_KEY environment variable not set. Skipping LLM keyword extraction.")
        return None
    
    try:        
        llm_model = "gpt-4o-mini"
        
        # Initialize the LLM with the API key explicitly
        llm = ChatOpenAI(model=llm_model, openai_api_key=openai_api_key)
        
        # Define a prompt template for hotel characteristics
        template = """
        Based on the following trip information, generate keywords for ideal hotel characteristics that would best match this trip:
        
        {trip_data_string}
        
        Please provide a list of keywords from the following categories to use in a bm25 hotel search:
        1. Ideal detailed hotel description
        2. 10-15 amenity keywords that would be important for this trip
        3. 3-5 trip type keywords that match this traveler (e.g., "family", "business", "couples", "solo travel", etc.)
        4. 2-3 hotel style keywords that would be appropriate (e.g., "Luxury", "Modern", "Boutique", "Budget", etc.)
        5. 2-3 hotel brand keywords that would be appropriate (e.g., "Relais & Châteaux", "St. Regis", "W Hotels", etc.)
        6. 2-3 hotel award keywords that would be appropriate (e.g., "Travelers Choice", etc.)
        
        Format your response as a simple list of lowercase keywords separated by spaces.
        
        Return only the list of keywords, no bullets, no numbers, no other text.
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        
        # Generate the response
        chain = prompt | llm
        response = chain.invoke({"trip_data_string": trip_data_string})

        # Extract keywords from the response
        response_content = response.content
        if not response_content or len(response.content.split()) == 0:
            print(f"LLM did not return a response to generate hotel search keywords")
            return None
        else:
            generated_keywords = set([word.lower() for word in response.content.split()])
            
        return generated_keywords
    except ImportError:
        print("Warning: LangChain or OpenAI packages not installed. Skipping keyword generation.")
        print("To install required packages: pip install langchain langchain-openai")

def generate_trip_restaurant_search_keywords_with_llm(trip_data_string, openai_api_key) -> str:
    """
    Generate restaurant listing keywords to search trip advisor restaurant listings stores in monfo with bm25.
    """

    if not openai_api_key:
        print("Warning: OPENAI_API_KEY environment variable not set. Skipping LLM keyword extraction.")
        return None
    
    try:        
        llm_model = "gpt-4o-mini"
        
        # Initialize the LLM with the API key explicitly
        llm = ChatOpenAI(model=llm_model, openai_api_key=openai_api_key)
        
        # Define a prompt template for hotel characteristics
        template = """
        Based on the following trip information, generate keywords for ideal restaurant characteristics that would best match this trip:
        
        {trip_data_string}
        
        Please provide a list of keywords from the following categories to use in a bm25 restaurant search:
        1. Ideal detailed restaurant description
        2. 10-15 features keywords that would be important for this trip (e.g., "Outdoor Seating", "Full Bar", "Parking Available")
        3. 3-5 trip type keywords that match this traveler (e.g., "family", "business", "couples", "solo travel")
        4. 2-3 restaurant cuisine keywords that would be appropriate (e.g., "French", "Italian", "Chinese", "Seafood")
        5. 2-3 restaurant award keywords that would be appropriate (e.g., "Michelin", "Gault Millau")
        
        Format your response as a simple list of lowercase keywords separated by spaces.
        
        Return only the list of keywords, no bullets, no numbers, no other text.
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        
        # Generate the response
        chain = prompt | llm
        response = chain.invoke({"trip_data_string": trip_data_string})

        # Extract keywords from the response
        response_content = response.content
        if not response_content or len(response.content.split()) == 0:
            print(f"LLM did not return a response to generate restaurant search keywords")
            return None
        else:
            generated_keywords = set([word.lower() for word in response.content.split()])
            
        return generated_keywords
    except ImportError:
        print("Warning: LangChain or OpenAI packages not installed. Skipping keyword generation.")
        print("To install required packages: pip install langchain langchain-openai")
    
def create_filters(trip_data) -> str:
    """
    Creates following basic mongo filters:
    1. geo filters based on trip destination
    2. budget filter based on trip budget
    3. only records with a non empty description fields (otherwise generally bad result and hard to sell to userx)
    """
    if not trip_data:
        print(f"Can't extract trip data string from None trip data.")
        return None
    
    query_conditions = []

    # Ensure only hotels and restaurants with descriptions are returned.
    query_conditions.append({"description": {"$exists": True, "$ne": ""}})
    
    # Extract relevant fields for search filters.
    destination = trip_data.get('destination', "")
    if destination:

        destination_city = destination.get('city', '')
        if destination_city:
            city_condition = {"address_obj.city": destination_city}
            query_conditions.append(city_condition)

        destination_state = destination.get('state', '')
        # Handle state matching with abbreviations and full names
        if destination_state:
            state_value = destination_state.strip()
            state_conditions = []
            
            # Case 1: Input is a 2-letter state code (e.g., "CO")
            if len(state_value) == 2 and state_value.upper() in US_STATES:
                state_abbrev = state_value.upper()
                full_state_name = US_STATES[state_abbrev]
                
                # Match both abbreviation and full name
                state_conditions.append({"address_obj.state": state_abbrev})
                state_conditions.append({"address_obj.state": full_state_name})
                
            # Case 2: Input is a full state name (e.g., "Colorado")
            elif state_value.title() in US_STATE_ABBREVS:
                full_state_name = state_value.title()
                state_abbrev = US_STATE_ABBREVS[full_state_name]
                
                # Match both abbreviation and full name
                state_conditions.append({"address_obj.state": state_abbrev})
                state_conditions.append({"address_obj.state": full_state_name})
                
            # Case 3: Input doesn't match known states, use as-is
            else:
                state_conditions.append({"address_obj.state": state_value})
            
            # Add OR condition to match any state format
            if len(state_conditions) > 1:
                query_conditions.append({"$or": state_conditions})
            else:
                query_conditions.append(state_conditions[0])

        destination_country = destination.get('country', 'United States')
        if destination_country:
            country_value = destination_country.strip()
            country_conditions = []
            
            # Handle common variations of United States
            if country_value.upper() in ["USA", "U.S.A.", "U.S.", "UNITED STATES", "UNITED STATES OF AMERICA"]:
                country_conditions.append({"address_obj.country": "United States"})
                country_conditions.append({"address_obj.country": "USA"})
                country_conditions.append({"address_obj.country": "U.S.A."})
                country_conditions.append({"address_obj.country": "U.S."})
            else:
                # Use as-is for other countries
                country_conditions.append({"address_obj.country": country_value})
            
            # Add OR condition to match any country format
            if len(country_conditions) > 1:
                query_conditions.append({"$or": country_conditions})
            else:
                query_conditions.append(country_conditions[0])
    else:
        print(f"Can't filter on destination because destination is None.")
    
    # Add price level filter if available
    price_level = trip_data.get('totalBudget', "")
    if price_level:
        #TODO: generalize to activities where cheaper is ok too, e.g. visiting
        # the Louvre in Paris isn't expensive but still worth it.

        # Create an OR query for price levels including one $ below and one $ above
        price_conditions = []
        
        # Add the exact price level
        price_conditions.append({"price_level": price_level})
        
        # Determine price level by counting $ symbols
        if price_level == "$":
            # Only add one level above for $ (can't go below $)
            price_conditions.append({"price_level": "$$"})
        elif price_level == "$$":
            # Add one level below and one level above
            price_conditions.append({"price_level": "$"})
            price_conditions.append({"price_level": "$$$"})
        elif price_level == "$$$":
            # Add one level below and one level above
            price_conditions.append({"price_level": "$$"})
            price_conditions.append({"price_level": "$$$$"})
        elif price_level == "$$$$":
            # Only add one level below for $$$$ (can't go above $$$$)
            price_conditions.append({"price_level": "$$$"})
        
        # Add OR condition to match any price level in the range
        if len(price_conditions) > 1:
            query_conditions.append({"$or": price_conditions})
        else:
            query_conditions.append(price_conditions[0])
    
    return query_conditions

def create_trip_advisor_hotel_search_index(hotels_collection):
    # Check if the collection has a text index
    indexes = hotels_collection.list_indexes()
    text_index_exists = False
    for index in indexes:
        if index.get('name') == 'text_search_index':
            text_index_exists = True
            break
            
    if not text_index_exists:
        # Create text index for full-text search
        hotels_collection.create_index([
            ("name", "text"), 
            ("description", "text"),
            ("styles", "text"),
            ("trip_types.name", "text"),
            ("awards.display_name", "text"),
            ("amenities", "text"),
            ("brand", "text"),
        ], name="text_search_index")

def create_trip_advisor_restaurant_search_index(restaurants_collection):
    # Check if the collection has a text index
    indexes = restaurants_collection.list_indexes()
    text_index_exists = False
    for index in indexes:
        if index.get('name') == 'text_search_index':
            text_index_exists = True
            break
            
    if not text_index_exists:
        # Create text index for full-text search
        restaurants_collection.create_index([
            ("name", "text"), 
            ("description", "text"),
            ("trip_types.name", "text"),
            ("awards.display_name", "text"),
            ("features", "text"),
            ("cuisine.name", "text")
        ], name="text_search_index")

def convert_mongo_trip_advisor_advisor_results_to_cal_item(parsed_results, trip_obj_id, start_date, end_date, cal_el_type):
    # Create formatted results
    formatted_results = []
    for i, hit in enumerate(parsed_results):
        hit_id = hit.get('location_id', 'N/A')
        name = hit.get('name', 'Unnamed')
        rating = hit.get('rating', 'N/A')
        budget = hit.get('price_level', 'N/A')
        
        # Get main photo URL if available
        main_photo_url = None
        if 'photos' in hit and len(hit['photos']) > 0:
            first_photo = hit['photos'][0]
            if 'images' in first_photo and 'original' in first_photo['images']:
                main_photo_url = first_photo['images']['original'].get('url', None)
        
        # Get address data
        address_obj = hit.get('address_obj', {})
        address_string = address_obj.get('address_string', '') if address_obj else ''
        
        # Get coordinates
        latitude = hit.get('latitude', None)
        longitude = hit.get('longitude', None)
        
        # Get description
        description = hit.get('description', '')
        
        # Create formatted hotel object
        today_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        # Get LLM generated notes field if present
        notes = hit.get("llm_explanation", None)
        
        if cal_el_type == "accommodation":
            name = f"Stay at {name}"
        elif cal_el_type == "restaurant":
            name = f"Eat at {name}"
        else:
            name = name
        
        formatted_hotel = {
            "trip_id": str(trip_obj_id),
            "type": cal_el_type,
            "name": name,
            "date": start_date,
            "endDate": end_date,
            "location": {
                "name": name,
                "address": address_string or "",
                "coordinates": {
                    "lat": float(latitude) if latitude else 0,
                    "lng": float(longitude) if longitude else 0
                }
            },
            "notes": notes,
            "status": "draft",
            "createdAt": today_date,
            "updatedAt": today_date,
            "description": description,
            "main_media": main_photo_url or "",
            "budget": budget
        }
        
        formatted_results.append(formatted_hotel)
    
    return formatted_results

def search_mongo(collection, query_conditions, search_keywords, limit=10):
    # Build combined search including full-text search
    if search_keywords:
        # Full-text search with $text (uses BM25 for ranking)
        # Join keywords into a single space-separated string for $text operator
        text_search_string = " ".join(search_keywords)
        
        # Create a text search query (uses BM25 TF-IDF scoring)
        text_query = {
            "$text": {
                "$search": text_search_string,
                "$caseSensitive": False,
                "$diacriticSensitive": False
            }
        }
        query_conditions.append(text_query)
        
        # Project the text score in results
        projection = {"score": {"$meta": "textScore"}}
        
        # Sort by the text score (higher score = better relevancy)
        text_sort = [("score", {"$meta": "textScore"})]
    
    # Combine with AND logic for required conditions
    final_query = {"$and": query_conditions} if len(query_conditions) > 1 else query_conditions[0] if query_conditions else {}
    
    # Find matched hotels
    mongo_search_limit = max(10, limit) # Get min 10 results to make sure reranking has enough results.
    # If using full-text search, use the textScore for sorting
    if search_keywords and text_search_string:
        # Get the limited results with proper sorting
        search_results = list(collection.find(final_query, projection).sort(text_sort).limit(mongo_search_limit))
    else:
        # Just sort by rating if no text search
        search_results = list(collection.find(final_query).sort([("rating", -1)]).limit(mongo_search_limit))
    
    # Process results
    if not search_results:
        print("\nNo results found from MongoDB")
        return None
    
    # Convert MongoDB documents to displayable JSON
    parsed_results = json.loads(dumps(search_results))

    return parsed_results

def rerank_hotel_mongo_results(parsed_results, trip_data_str, openai_api_key):
    # Rerank results using OpenAI if API key is available

    if not openai_api_key:
        print("No OpenAI API key provided. Skipping LLM reranking.")
        return parsed_results

    try:
        llm_model = "gpt-4o-mini"
        llm = ChatOpenAI(model=llm_model, openai_api_key=openai_api_key)
        print(f"Successfully initialized LLM model: {llm_model}")
        
        # Create a prompt template for hotel characteristics
        rerank_template = """
        Based on the following trip information and list of hotels, select the single best hotel that matches the trip requirements.
        Take into account all of the trip information below and how the hotel matches the trip requirements. Please make sure to
        only provide a hotel with a different price level if there are no other hotels with the desired price level available.
        
        Trip Information:
        {trip_data_str}
        
        Hotels:
        {hotels_data}
        
        Return your response as a JSON object with two fields:
        1. "hotel_name": The exact name of the best matching hotel
        2. "explanation": A short max 7 word quirky explanation of why this hotel was selected for this trip
        
        Format your response as valid JSON only. Do not include any explanations outside the JSON, do not include ```json or ```.
        Example: {{"hotel_name": "Example Hotel", "explanation": "This hotel offers valet ski-in/ski-out access."}}
        """
        
        prompt = ChatPromptTemplate.from_template(rerank_template)
        
        # Prepare all hotel data for the prompt
        hotels_data = []
        hotel_names = []  # Keep track of hotel names for debugging
        for i, hotel in enumerate(parsed_results, 1):
            hotel_name = hotel.get('name', 'Unknown')
            hotel_names.append(hotel_name)
            hotel_info = f"""
            Hotel {i}:
            Name: {hotel_name}
            Rating: {hotel.get('rating', 'N/A')}/5
            Price Level: {hotel.get('price_level', 'N/A')}
            Styles: {', '.join(hotel.get('styles', []))}
            Trip Types: {', '.join([t.get('name', t) if isinstance(t, dict) else t for t in hotel.get('trip_types', [])])}
            Amenities: {', '.join([a.get('name', a) if isinstance(a, dict) else a for a in hotel.get('amenities', [])])}
            Brand: {hotel.get('brand', 'N/A')}
            Description: {hotel.get('description', '')[:200]}
            """
            hotels_data.append(hotel_info)

        print(f"Prepared {len(hotels_data)} hotels for llm reranking")
        
        # Get the best hotel from LLM
        chain = prompt | llm
        print("Calling LLM API for hotel ranking...")
        response = chain.invoke({
            "trip_data_str": trip_data_str,
            "hotels_data": "\n".join(hotels_data)
        })
        print("LLM API call completed")
        
        try:
            # Parse the JSON response
            response_content = response.content.strip()
            print(f"\nLLM Response: {response_content}")
            response_data = json.loads(response_content)
            best_hotel_name = response_data.get("hotel_name", "")
            explanation = response_data.get("explanation", "")
            print(f"Best hotel name: {best_hotel_name}")
            print(f"Explanation: {explanation}")
            
            # Find the selected hotel and move it to the top
            hotel_found = False
            for i, hotel in enumerate(parsed_results):
                if hotel.get('name') == best_hotel_name:
                    print(f"Found matching hotel at index {i}")
                    hotel_found = True
                    # Move the selected hotel to the top
                    selected_hotel = parsed_results.pop(i)
                    # Store the explanation at the top level where we can access it later
                    selected_hotel["llm_explanation"] = explanation  # Add the explanation
                    print(f"Added explanation to hotel: {explanation}")
                    parsed_results.insert(0, selected_hotel)
                    break
        
            if not hotel_found:
                print(f"WARNING: Could not find hotel with name '{best_hotel_name}' in results")
                print(f"Available hotel names: {hotel_names}")
            
            return parsed_results
    
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback to simpler parsing if JSON parsing fails
            print(f"Error parsing LLM response as JSON: {e}")
            response_content = response.content.strip()
            best_hotel_name = response_content
            explanation = ""
            
            # Find the selected hotel and move it to the top (without explanation)
            for i, hotel in enumerate(parsed_results):
                if hotel.get('name') == best_hotel_name:
                    selected_hotel = parsed_results.pop(i)
                    parsed_results.insert(0, selected_hotel)
                    break
    
    except Exception as e:
        # Catch and log all other exceptions
        print(f"ERROR in LLM reranking: {str(e)}")
        import traceback
        print(traceback.format_exc())


def rerank_restaurant_mongo_results(parsed_results, trip_data_str, openai_api_key, num_recs=4):
    # Rerank restaurant results using OpenAI if API key is available

    if not openai_api_key:
        print("No OpenAI API key provided. Skipping LLM reranking.")
        return parsed_results

    try:
        llm_model = "gpt-4o-mini"
        llm = ChatOpenAI(model=llm_model, openai_api_key=openai_api_key)
        print(f"Successfully initialized LLM model: {llm_model}")
        
        # Create a prompt template for restaurant characteristics
        rerank_template = """
        Based on the following trip information and list of restaurants, select the {num_recs} best restaurants that match the trip requirements.
        Take into account all of the trip information below and how the restaurant matches the trip requirements. Please make sure to
        only provide a restaurant with a different price level if there are no other restaurants with the desired price level available.
        
        Trip Information:
        {trip_data_str}
        
        Restaurants:
        {restaurants_data}
        
        Return your response as a JSON list of objects where each object has two fields:
        1. "restaurant_name": The exact name of the best matching restaurant
        2. "explanation": A short max 7 word quirky explanation of why this restaurant was selected for this trip
        
        Format your response as valid JSON only. Do not include any explanations outside the JSON, do not include ```json or ```.
        Example: [[
            {{"restaurant_name": "Quick Bite", "explanation": "Close to the charlifts."}},
            {{"restaurant_name": "Shushirimi", "explanation": "Offers sushi."}},
            {{"restaurant_name": "Diamonds on the Mountain", "explanation": "Blacktie meals in the mountains."}},
            {{"restaurant_name": "Fondue High", "explanation": "Hearty meals in the mountains."}}
        ]]
        """
        
        prompt = ChatPromptTemplate.from_template(rerank_template)
        
        # Prepare all restaurant data for the prompt
        restaurants_data = []
        restaurant_names = []  # Keep track of restaurant names for debugging
        for i, restaurant in enumerate(parsed_results, 1):
            restaurant_name = restaurant.get('name', 'Unknown')
            restaurant_names.append(restaurant_name)
            restaurant_info = f"""
            Restaurant {i}:
            Name: {restaurant_name}
            Rating: {restaurant.get('rating', 'N/A')}/5
            Price Level: {restaurant.get('price_level', 'N/A')}
            Cuisine: {', '.join([c.get('name', c) if isinstance(c, dict) else c for c in restaurant.get('cuisine', [])])}
            Trip Types: {', '.join([t.get('name', t) if isinstance(t, dict) else t for t in restaurant.get('trip_types', [])])}
            Features: {', '.join([a.get('name', a) if isinstance(a, dict) else a for a in restaurant.get('features', [])])}
            Description: {restaurant.get('description', '')[:200]}
            """
            restaurants_data.append(restaurant_info)

        print(f"Prepared {len(restaurants_data)} restaurants for llm reranking")
        
        # Get the best hotel from LLM
        chain = prompt | llm
        print("Calling LLM API for hotel ranking...")
        response = chain.invoke({
            "num_recs": num_recs,
            "trip_data_str": trip_data_str,
            "restaurants_data": "\n".join(restaurants_data)
        })
        print("LLM API call completed")
        
        try:
            # Parse the JSON response
            response_content = response.content.strip()
            print(f"\nLLM Response: {response_content}")
            response_data = json.loads(response_content)
            best_restaurants = {
                r.get("restaurant_name", ""): r.get("explanation", "")
                for r in response_data
            }
            print(f"Best restaurants: {best_restaurants}")
            
            # Find the selected restaurant and move it to the top.
            restaurants_found = 0
            for i, restaurant in enumerate(parsed_results):
                if restaurant.get('name') in best_restaurants:
                    print(f"Found matching restaurant at index {i}")
                    restaurants_found += 1
                    # Move the selected restaurant to the top
                    selected_restaurant = parsed_results.pop(i)
                    # Store the explanation at the top level where we can access it later
                    selected_restaurant["llm_explanation"] = best_restaurants[restaurant.get('name', '')]  # Add the explanation
                    print(f"Added llm explanation to restaurant: {selected_restaurant['llm_explanation']}")
                    parsed_results.insert(0, selected_restaurant)
                if restaurants_found >= num_recs:
                    break
        
            if restaurants_found < num_recs:
                print(f"WARNING: Could not find all recommended restaurants {best_restaurants}")
            
            return parsed_results
    
        except (json.JSONDecodeError, KeyError) as e:
            # Fallback to simpler parsing if JSON parsing fails
            print(f"Error parsing LLM response as JSON: {e}")
            response_content = response.content.strip()
            best_restaurant_name = response_content
            explanation = ""
            
            # Find the selected restaurant and move it to the top (without explanation)
            for i, restaurant in enumerate(parsed_results):
                if restaurant.get('name') == best_restaurant_name:
                    selected_restaurant = parsed_results.pop(i)
                    parsed_results.insert(0, selected_restaurant)
                    break
    
    except Exception as e:
        # Catch and log all other exceptions
        print(f"ERROR in LLM reranking: {str(e)}")
        import traceback
        print(traceback.format_exc())
    

def main():

    load_dotenv()

    # MongoDB connection details - no default values
    username = os.getenv("MONGODB_USERNAME")
    password = os.getenv("MONGODB_PASSWORD")
    cluster = os.getenv("MONGODB_CLUSTER")
    database_name = os.getenv("MONGODB_DATABASE")

    # Construct MongoDB URI
    uri = f"mongodb+srv://{username}:{password}@{cluster}/?retryWrites=true&w=majority&appName=Viammo-Cluster-alpha"

    # Create MongoDB client
    client = MongoClient(uri)
    db = client[database_name]

    parser = argparse.ArgumentParser(description='Search Tester')
    parser.add_argument('--type', type=str, help='method to call', required=True)
    parser.add_argument('--trip_id', type=str, help='Trip ID to load')
    args = parser.parse_args()

    if args.type == 'load_trip':
        trip_data = load_trip(args.trip_id, db)
        print(dumps(trip_data, indent=2))

    elif args.type == 'extract_search_trip_data_str':
        trip_data = load_trip(args.trip_id, db)
        print(extract_search_trip_data_str(trip_data))

    elif args.type == 'extract_generic_trip_search_keywords_no_llm':
        trip_data = load_trip(args.trip_id, db)
        print(extract_generic_trip_search_keywords_no_llm(trip_data))

    elif args.type == 'generate_trip_hotel_search_keywords_with_llm':
        trip_data = load_trip(args.trip_id, db)
        trip_data_str = extract_search_trip_data_str(trip_data)
        openai_api_key = os.getenv("OPENAI_API_KEY")
        print(generate_trip_hotel_search_keywords_with_llm(trip_data_str, openai_api_key))

    elif args.type == 'create_filters':
        trip_data = load_trip(args.trip_id, db)
        print(create_filters(trip_data))
    
    elif args.type == 'create_hotel_search_index':
        hotels_collection = db["tripadvisor-hotel_review"]
        create_trip_advisor_hotel_search_index(hotels_collection)

    elif args.type == 'create_restaurant_search_index':
        restaurants_collection = db["tripadvisor-restaurant_review"]
        create_trip_advisor_restaurant_search_index(restaurants_collection)

    elif args.type == 'search_mongo_hotels':
        trip_data = load_trip(args.trip_id, db)
        hotels_collection = db["tripadvisor-hotel_review"]
        query_conditions = create_filters(trip_data)
        print(f"Query conditions: {query_conditions}\n")
        trip_data_str = extract_search_trip_data_str(trip_data)
        print(f"Trip data string: {trip_data_str}\n")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        # generic_search_keywords = extract_generic_trip_search_keywords_no_llm(trip_data)
        # print(f"Generic search keywords: {generic_search_keywords}\n")
        llm_search_keywords = generate_trip_hotel_search_keywords_with_llm(trip_data_str, openai_api_key)
        print(f"LLM search keywords: {llm_search_keywords}\n")
        search_keywords = llm_search_keywords # (generic_search_keywords | llm_search_keywords)
        print(f"Search keywords: {search_keywords}\n")
        parsed_results = search_mongo(hotels_collection, query_conditions, search_keywords, limit=5)
        print(f"Parsed results:")
        for r in parsed_results:
            print(f"{r['score']}: {r['name']}")
        reranked_results = rerank_hotel_mongo_results(parsed_results, trip_data_str, openai_api_key)
        print(f"\nReranked results:")
        for r in reranked_results:
            print(f"{r['score']}: {r['name']}")
        print()
        for r in reranked_results:
            print(f"name: {r['name']}")
            print(f"brand: {r.get('brand', None)}")
            print(f"price_level: {r['price_level']}")
            print(f"awards: {r.get('awards', None)}")
            print(f"description: {r['description']}")
            print(f"styles: {r['styles']}")
            print(f"trip_types: {r['trip_types']}")
            print(f"amenities: {r['amenities']}")
            print(f"rating: {r['rating']}")
        
        # print(f"Top raw: {json.dumps(parsed_results[0], indent=2)}")
        # print(f"Top reranked: {json.dumps(reranked_results[0], indent=2)}")
        start_date = trip_data.get('startDate', None)
        end_date = trip_data.get('endDate', None)
        cleaned_cal_els = convert_mongo_trip_advisor_advisor_results_to_cal_item(
            parsed_results,
            args.trip_id,
            start_date,
            end_date,
            cal_el_type = 'accomodation'
        )
        print()
        print(json.dumps(cleaned_cal_els, indent=2))
    
    elif args.type == 'search_mongo_restaurants':
        trip_data = load_trip(args.trip_id, db)
        restaurants_collection = db["tripadvisor-restaurant_review"]
        query_conditions = create_filters(trip_data)
        print(f"Query conditions: {query_conditions}\n")
        trip_data_str = extract_search_trip_data_str(trip_data)
        print(f"Trip data string: {trip_data_str}\n")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        # generic_search_keywords = extract_generic_trip_search_keywords_no_llm(trip_data)
        # print(f"Generic search keywords: {generic_search_keywords}\n")
        llm_search_keywords = generate_trip_restaurant_search_keywords_with_llm(trip_data_str, openai_api_key)
        print(f"LLM search keywords: {llm_search_keywords}\n")
        search_keywords = llm_search_keywords # (generic_search_keywords | llm_search_keywords)
        print(f"Search keywords: {search_keywords}\n")
        parsed_results = search_mongo(restaurants_collection, query_conditions, search_keywords, limit=5)
        print(f"Parsed results:")
        for r in parsed_results:
            print(f"{r['score']}: {r['name']}")
        reranked_results = rerank_restaurant_mongo_results(parsed_results, trip_data_str, openai_api_key)
        print(f"\nReranked results:")
        for r in reranked_results:
            print(f"{r['score']}: {r['name']}")
        print()
        for r in reranked_results:
            print(f"name: {r['name']}")
            print(f"price_level: {r['price_level']}")
            print(f"awards: {r.get('awards', None)}")
            print(f"description: {r['description']}")
            print(f"trip_types: {r['trip_types']}")
            print(f"features: {r['features']}")
            print(f"cuisine: {r['cuisine']}")
            print(f"rating: {r['rating']}")
        
        # print(f"Top raw: {json.dumps(parsed_results[0], indent=2)}")
        # print(f"Top reranked: {json.dumps(reranked_results[0], indent=2)}")
        start_date = trip_data.get('startDate', None)
        end_date = trip_data.get('endDate', None)
        cleaned_cal_els = convert_mongo_trip_advisor_advisor_results_to_cal_item(
            parsed_results,
            args.trip_id,
            start_date,
            end_date,
            cal_el_type = 'restaurant'
        )
        print()
        print(json.dumps(cleaned_cal_els, indent=2))
    
    else:
        print(f"Invalid type: {args.type}")

if __name__ == "__main__":
    main()
