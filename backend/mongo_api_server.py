#!/usr/bin/env python3
"""
MongoDB API Server

This script creates a simple Flask-based API server that securely connects to MongoDB
and provides endpoints for the frontend to interact with the database without exposing
credentials in the client-side code.

Usage:
    python mongo_api_server.py

Endpoints:
    GET /api/trips - Get all trips
    GET /api/trips/:id - Get a specific trip
    GET /api/calendar/:tripId - Get calendar items for a specific trip
    GET /api/hotels/:tripId - Get hotel recommendations for a specific trip
"""

import os
import sys
import argparse
import re
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.json_util import dumps, loads
from datetime import datetime
import json  # Move json import here
import requests  # Import requests for API calls

# Load environment variables from .env file
load_dotenv()

# Check required environment variables
required_env_vars = [
    "MONGODB_USERNAME",
    "MONGODB_PASSWORD",
    "MONGODB_CLUSTER",
    "MONGODB_DATABASE"
]

# Verify all required environment variables are set
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
    print("Please ensure these are set in your .env file")
    sys.exit(1)

# MongoDB connection details - no default values
username = os.getenv("MONGODB_USERNAME")
password = os.getenv("MONGODB_PASSWORD")
cluster = os.getenv("MONGODB_CLUSTER")
database_name = os.getenv("MONGODB_DATABASE")

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Construct MongoDB URI
uri = f"mongodb+srv://{username}:{password}@{cluster}/?retryWrites=true&w=majority&appName=Viammo-Cluster-alpha"

# Create MongoDB client
client = MongoClient(uri)
db = client[database_name]

# Helper function to convert MongoDB cursor to JSON
def json_response(data):
    """Convert MongoDB cursor to JSON response"""
    return Response(dumps(data), mimetype='application/json')

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

def get_mock_trips():
    """Generate mock trips for testing"""
    return [
        {
            "_id": {"$oid": "67d8a1e36efdc1eb41168f34"},
            "name": "Paris Trip",
            "startDate": "2024-10-02",
            "endDate": "2024-10-06",
            "destination": "Paris",
            "numberOfGuests": 2,
            "createdAt": "2024-01-15T08:00:00.000Z",
            "updatedAt": "2024-03-15T08:00:00.000Z",
            "status": "draft",
            "totalBudget": 20000,
            "notes": "Authentic charm"
        },
        {
            "_id": {"$oid": "67d8a1e36efdc1eb41168f35"},
            "name": "Tokyo Adventure",
            "startDate": "2024-11-10",
            "endDate": "2024-11-20",
            "destination": "Tokyo",
            "numberOfGuests": 4,
            "createdAt": "2024-01-20T08:00:00.000Z",
            "updatedAt": "2024-03-18T08:00:00.000Z",
            "status": "draft",
            "totalBudget": 25000,
            "notes": "Explore Japanese culture"
        }
    ]

def get_mock_calendar():
    """Generate mock calendar items for testing"""
    return [
        {
            "_id": {"$oid": "67df3aebf5513a0a9f76fd1d"},
            "trip_id": "67d8a1e36efdc1eb41168f34",
            "name": "Stay at the Hotel Crillion",
            "type": "accommodation",
            "min_cost": 2000,
            "max_cost": 2000,
            "notes": "Stayed at by 5 friends",
            "location": "10 Place de la Concorde, 75008 Paris, France",
            "start_date": "2024-10-02",
            "end_date": "2024-10-06",
            "start_time": "15:00",
            "end_time": "12:00"
        },
        {
            "_id": {"$oid": "67df3b3ff5513a0a9f76fd1e"},
            "trip_id": "67d8a1e36efdc1eb41168f34",
            "name": "Eat at Cafe Marmaton",
            "type": "restaurant",
            "min_cost": 100,
            "max_cost": 200,
            "notes": "4.7 Stars on google",
            "location": "8 Rue de Marmaton, 75002 Paris, France",
            "start_date": "2024-10-03",
            "end_date": "2024-10-03",
            "start_time": "19:30",
            "end_time": "21:30"
        },
        {
            "_id": {"$oid": "67df3b7cf5513a0a9f76fd1f"},
            "trip_id": "67d8a1e36efdc1eb41168f34",
            "name": "Visit The Louvre",
            "type": "attraction",
            "min_cost": 40,
            "max_cost": 40,
            "notes": "Optimal this time of year",
            "location": "Rue de Rivoli, 75001 Paris, France",
            "start_date": "2024-10-04",
            "end_date": "2024-10-04",
            "start_time": "10:00",
            "end_time": "16:00"
        },
        {
            "_id": {"$oid": "67df3bc4f5513a0a9f76fd20"},
            "trip_id": "67d8a1e36efdc1eb41168f34",
            "name": "Shop at The Broken Arm",
            "type": "shopping",
            "min_cost": 100,
            "max_cost": 1000,
            "notes": "Saved by you on 9/23/24",
            "location": "12 Rue Perrée, 75003 Paris, France",
            "start_date": "2024-10-05",
            "end_date": "2024-10-05",
            "start_time": "11:00",
            "end_time": "14:00"
        },
        {
            "_id": {"$oid": "67df3c0cf5513a0a9f76fd21"},
            "trip_id": "67d8a1e36efdc1eb41168f34",
            "name": "Coffee and Snacks at Tazi",
            "type": "cafe",
            "min_cost": 20,
            "max_cost": 60,
            "notes": "Recommended by 7 friends",
            "location": "25 Rue des Gravilliers, 75003 Paris, France",
            "start_date": "2024-10-05",
            "end_date": "2024-10-05",
            "start_time": "15:30",
            "end_time": "17:00"
        }
    ]

@app.route('/api/trips', methods=['GET'])
def get_trips():
    """Get all trips from MongoDB"""
    try:
        # Try to find trips in MongoDB
        trips = list(db.trips.find())
        print(f"Found {len(trips)} trips in database")
        
        # If no trips in database, return mock data
        if not trips:
            print("No trips found in database. Returning mock data as fallback")
            trips = get_mock_trips()
        
        return json_response(trips)
    except Exception as e:
        print(f"Error fetching trips: {e}")
        return json_response({"error": str(e)}), 500

@app.route('/api/trips/<trip_id>', methods=['GET'])
def get_trip(trip_id):
    """Get a specific trip by ID from MongoDB"""
    try:
        # Try to convert to MongoDB ObjectId
        try:
            # Try to convert string to ObjectId
            object_id = ObjectId(trip_id)
            print(f"Successfully converted trip_id to ObjectId: {trip_id}")
            
            # Try to find trip by ObjectId
            trip = db.trips.find_one({"_id": object_id})
            
            if trip:
                print(f"Found trip with _id as ObjectId: {trip.get('name', 'Unknown')}")
                return json_response(trip)
        except Exception as e:
            print(f"Error finding trip by ObjectId: {e}")
        
        # If not found with ObjectId, try with string ID
        trip = db.trips.find_one({"_id": trip_id})
        
        if trip:
            print(f"Found trip with _id as string: {trip.get('name', 'Unknown')}")
            return json_response(trip)
            
        # If still not found, find in mock data
        mock_trips = get_mock_trips()
        for mock_trip in mock_trips:
            mock_id = mock_trip["_id"]["$oid"]
            if mock_id == trip_id:
                print(f"Found trip in mock data: {mock_trip.get('name', 'Unknown')}")
                return json_response(mock_trip)
        
        # No trip found
        print(f"Trip not found with ID: {trip_id}")
        return json_response({"error": f"Trip not found with ID: {trip_id}"}), 404
    
    except Exception as e:
        print(f"Error fetching trip: {e}")
        return json_response({"error": str(e)}), 500

@app.route('/api/trips/<trip_id>', methods=['DELETE'])
def delete_trip(trip_id):
    """Delete a trip and its associated calendar items from MongoDB"""
    try:
        # Validate trip_id
        try:
            # If it's a valid ObjectId, use it directly
            if ObjectId.is_valid(trip_id):
                mongo_trip_id = ObjectId(trip_id)
            else:
                # Otherwise treat it as a string ID
                mongo_trip_id = trip_id
        except Exception as e:
            print(f"Invalid trip ID format: {trip_id}")
            return json_response({"success": False, "error": "Invalid trip ID format"}), 400

        # Connect to MongoDB
        try:
            client = MongoClient(uri)
            db = client[database_name]
            
            # First, delete any calendar items associated with this trip
            calendar_result = db.trip_calendar.delete_many({"trip_id": mongo_trip_id})
            
            # Then delete the trip itself
            trip_result = db.trips.delete_one({"_id": mongo_trip_id})
            
            if trip_result.deleted_count == 0:
                return json_response({
                    "success": False, 
                    "error": "Trip not found"
                }), 404
            
            return json_response({
                "success": True,
                "message": "Trip and associated calendar items deleted successfully",
                "trip_deleted": trip_result.deleted_count > 0,
                "calendar_items_deleted": calendar_result.deleted_count
            })
            
        except Exception as mongo_error:
            print(f"MongoDB operation error: {mongo_error}")
            return json_response({"success": False, "error": f"Database error: {str(mongo_error)}"}), 500
    except Exception as e:
        import traceback
        print(f"Unhandled error deleting trip: {e}")
        print(traceback.format_exc())
        return json_response({"success": False, "error": str(e)}), 500

@app.route('/api/calendar/<trip_id>', methods=['GET'])
def get_calendar(trip_id):
    """Get calendar items for a trip from MongoDB"""
    try:
        print(f"Fetching calendar items for trip ID: {trip_id}")
        
        # Clean the trip_id (remove quotes, etc.)
        clean_trip_id = trip_id.strip('"\'').strip()
        print(f"Cleaned trip ID: {clean_trip_id}")
        
        # Try to convert to ObjectId for MongoDB
        try:
            from bson.objectid import ObjectId
            object_id = ObjectId(clean_trip_id)
            print(f"Successfully converted trip_id to ObjectId: {object_id}")
            
            # Try to find calendar items by ObjectId
            calendar_items = list(db.trip_calendar.find({"trip_id": object_id}))
            
            if calendar_items:
                print(f"Query with trip_id as ObjectId found {len(calendar_items)} items")
                return json_response(calendar_items)
        except Exception as e:
            print(f"Error finding calendar items by ObjectId: {e}")
        
        # If not found with ObjectId, try with string trip_id
        calendar_items = list(db.trip_calendar.find({"trip_id": clean_trip_id}))
        
        if calendar_items:
            print(f"Query with trip_id as string found {len(calendar_items)} items")
            return json_response(calendar_items)
            
        # Try with different field name (tripId vs trip_id)
        calendar_items = list(db.trip_calendar.find({"tripId": clean_trip_id}))
        
        if calendar_items:
            print(f"Query with tripId as string found {len(calendar_items)} items")
            return json_response(calendar_items)
            
        # Return empty array for newly created trips with no elements yet
        print(f"No calendar items found for trip ID {clean_trip_id}. Returning empty array.")
        return json_response([])
        
    except Exception as e:
        print(f"Error getting calendar items: {e}")
        return json_response({"error": str(e)}), 500

@app.route('/api/debug/collections', methods=['GET'])
def list_collections():
    """List all collections in the database for debugging purposes."""
    try:
        collections = db.list_collection_names()
        result = {
            "collections": collections,
            "count": len(collections)
        }
        
        # For each collection, add some stats
        for coll_name in collections:
            try:
                collection = db[coll_name]
                doc_count = collection.count_documents({})
                sample = list(collection.find().limit(1))
                
                result[coll_name] = {
                    "count": doc_count,
                    "sample_fields": list(sample[0].keys()) if sample else []
                }
            except Exception as e:
                result[coll_name] = {"error": str(e)}
        
        return json_response(result)
    except Exception as e:
        print(f"Error listing collections: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug/trip_calendar_raw', methods=['GET'])
def get_trip_calendar_raw():
    """Get all raw trip_calendar items for debugging."""
    try:
        calendar_items = list(db.trip_calendar.find())
        return json_response(calendar_items)
    except Exception as e:
        print(f"Error getting raw trip_calendar: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/create_trip', methods=['POST'])
def create_trip():
    """Create a new trip in MongoDB"""
    try:
        # Get trip data from request
        trip_data = request.json
        print(f"Creating new trip with data: {json.dumps(trip_data, indent=2)}")
        
        # Validate required fields
        required_fields = ['name', 'startDate', 'endDate', 'destination', 'numberOfGuests']
        missing_fields = [field for field in required_fields if field not in trip_data]
        
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            print(f"Error: {error_msg}")
            return json_response({"success": False, "error": error_msg}), 400
        
        # Add timestamps if not provided
        if 'createdAt' not in trip_data:
            from datetime import datetime
            trip_data['createdAt'] = datetime.utcnow().isoformat()
            trip_data['updatedAt'] = trip_data['createdAt']
        
        # Make sure numberOfGuests is an integer
        if 'numberOfGuests' in trip_data and not isinstance(trip_data['numberOfGuests'], int):
            try:
                trip_data['numberOfGuests'] = int(trip_data['numberOfGuests'])
                print(f"Converted numberOfGuests to integer: {trip_data['numberOfGuests']}")
            except (ValueError, TypeError):
                print(f"Could not convert numberOfGuests to integer: {trip_data['numberOfGuests']}")
                trip_data['numberOfGuests'] = 1  # Default to 1 guest
        
        print(f"Connecting to MongoDB collection: {db.name}.trips")
        
        # Insert into MongoDB
        try:
            result = db.trips.insert_one(trip_data)
            
            # Get the new trip ID
            trip_id = str(result.inserted_id)
            print(f"Successfully created new trip with ID: {trip_id}")
            
            # Get the complete trip data to verify
            new_trip = db.trips.find_one({"_id": result.inserted_id})
            print(f"Verified new trip in database: {dumps(new_trip)}")
            
            # Return the new trip ID
            return json_response({"success": True, "trip_id": trip_id})
        except Exception as mongo_error:
            print(f"MongoDB error while inserting trip: {mongo_error}")
            
            # Try to diagnose MongoDB connection issues
            try:
                # Check if we can list collections as a connection test
                collections = db.list_collection_names()
                print(f"Connection seems OK. Available collections: {collections}")
                return json_response({"success": False, "error": f"Database insertion error: {str(mongo_error)}"}), 500
            except Exception as conn_error:
                print(f"MongoDB connection error: {conn_error}")
                return json_response({"success": False, "error": "MongoDB connection error"}), 500
    except Exception as e:
        import traceback
        print(f"Unhandled error creating trip: {e}")
        print(traceback.format_exc())
        return json_response({"success": False, "error": str(e)}), 500

@app.route('/api/hotels/<trip_id>', methods=['GET'])
def search_hotels_for_trip(trip_id):
    """Search for hotels based on a trip ID"""
    try:
        # Parse the limit parameter (default to 10)
        limit = request.args.get('limit', 10, type=int)
        
        # Get trip data from MongoDB
        try:
            # Convert trip_id string to ObjectId
            trip_id_obj = ObjectId(trip_id)
            trip_data = db.trips.find_one({"_id": trip_id_obj})
            
            if not trip_data:
                return json_response({"error": f"No trip found with ID: {trip_id}"}), 404
                
            # Get trip title from either 'title' or 'name' field
            trip_title = trip_data.get('name', '')
            
            # Create a variable to store trip data information for later use
            trip_data_string = f"Found trip: {trip_title}\n"
            
            # Extract relevant fields for search
            destination = trip_data.get('destination', {})
            # Add destination to trip data string
            trip_data_string += f"\nTrip data:\n"
            trip_data_string += f"- destination: {destination}\n"
            
            # Get date information from trip
            start_date = trip_data.get('startDate', 'N/A')
            end_date = trip_data.get('endDate', 'N/A')
            
            # Format dates to remove time portion (if they're valid dates)
            if start_date != 'N/A' and isinstance(start_date, str) and 'T' in start_date:
                start_date = start_date.split('T')[0]  # Keep only the date part before 'T'
            if end_date != 'N/A' and isinstance(end_date, str) and 'T' in end_date:
                end_date = end_date.split('T')[0]  # Keep only the date part before 'T'
                
            trip_data_string += f"- startDate: {start_date}\n"
            trip_data_string += f"- endDate: {end_date}\n"
            
            # Handle destination field that might be a string or an object
            if isinstance(destination, dict):
                destination_city = destination.get('city', '')
                destination_state = destination.get('state', '')
                destination_country = destination.get('country', 'United States')
            else:
                # If destination is a string, try to parse it
                # Format might be "City, State, Country" or variations
                destination_parts = str(destination).split(',')
                
                if len(destination_parts) >= 1:
                    # First part is likely the city
                    destination_city = destination_parts[0].strip()
                else:
                    destination_city = ''
                    
                if len(destination_parts) >= 2:
                    # Second part is likely the state/region
                    destination_state = destination_parts[1].strip()
                else:
                    destination_state = ''
                    
                if len(destination_parts) >= 3:
                    # Third part is likely the country
                    destination_country = destination_parts[2].strip()
                else:
                    destination_country = 'United States'
            
            # Debug other key fields
            total_budget = trip_data.get('totalBudget', None)
            trip_data_string += f"- totalBudget: {total_budget}\n"
            
            notes = trip_data.get('notes', '')
            trip_data_string += f"- notes: {notes[:50]}{'...' if len(str(notes)) > 50 else ''}\n"
            
            # Use either 'title' or 'name' field for title
            title = trip_data.get('name', '')
            trip_data_string += f"- title: {title}\n"
            
            # Get purpose field (if available)
            purpose = trip_data.get('purpose', '')
            trip_data_string += f"- purpose: {purpose[:50]}{'...' if len(str(purpose)) > 50 else ''}\n"
            
            # Extract relevant keywords from trip data
            search_keywords = []
            
            # Add keywords from title
            if title:
                # Extract meaningful words, ignore common words like "to", "in", etc.
                title_words = [word for word in re.findall(r'\b\w+\b', title.lower()) 
                              if len(word) > 2 and word not in stop_words]
                search_keywords.extend(title_words)
            
            # Add keywords from purpose
            if purpose:
                # Extract meaningful words from purpose
                purpose_words = [word.lower() for word in re.findall(r'\b[a-zA-Z]+\b', str(purpose))]
                
                # Filter out stop words and short words (less than 3 characters)
                meaningful_purpose_words = [word for word in purpose_words if word not in stop_words and len(word) > 2]
                
                # Add unique words from purpose
                for word in meaningful_purpose_words:
                    if word not in search_keywords:
                        search_keywords.append(word)
            
            # Add keywords from notes
            if notes:
                # Extract all meaningful words from notes
                notes_words = [word.lower() for word in re.findall(r'\b[a-zA-Z]+\b', notes)]
                
                # Filter out stop words and short words (less than 3 characters)
                meaningful_words = [word for word in notes_words if word not in stop_words and len(word) > 2]
                
                # Add unique words from notes
                for word in meaningful_words:
                    if word not in search_keywords:
                        search_keywords.append(word)
            
            # Process results with LLM if OpenAI API key is available
            # Check if OpenAI API key is set
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                print(f"Generate keywords for BM25 search...")
                try:
                    from langchain_openai import ChatOpenAI
                    from langchain.prompts import ChatPromptTemplate
                    
                    llm_model = "gpt-4o-mini"
                    
                    # Initialize the LLM with the API key explicitly
                    llm = ChatOpenAI(model=llm_model, openai_api_key=openai_api_key)
                    
                    # Define a prompt template for hotel characteristics
                    template = """
                    Based on the following trip information, generate keywords for ideal hotel characteristics that would best match this trip:
                    
                    {trip_data}
                    
                    Please provide a list of keywords from the following categories to use in a bm25 hotel search:
                    1. Ideal detailed hotel description
                    2. 10-15 amenity keywords that would be important for this trip
                    3. 3-5 trip type keywords that match this traveler (e.g., "family", "business", "couples", "solo travel")
                    4. 2-3 hotel style keywords that would be appropriate (e.g., "Luxury", "Modern", "Boutique", "Budget")
                    
                    Format your response as a simple list of lowercase keywords separated by spaces.
                    
                    Return only the list of keywords, no bullets, no numbers, no other text.
                    """
                    
                    prompt = ChatPromptTemplate.from_template(template)
                    
                    # Generate the response
                    chain = prompt | llm
                    response = chain.invoke({"trip_data": trip_data_string})

                    # Extract keywords from the response
                    response_content = response.content
                    print(f"Response content: {response_content}")
                    if not response_content or len(response.content.split()) == 0:
                        print(f"LLM did not return a response")
                    else:
                        generated_keywords = set([word.lower() for word in response.content.split()])
                    print(f"Extracted keywords: \n{generated_keywords}")
                        
                    # Add to search keywords if not already present.
                    for word in generated_keywords:
                        if word not in search_keywords:
                            search_keywords.append(word)
                    
                    print(f"\nAdded {len(generated_keywords)} generated keywords to search")
                except ImportError:
                    print("Warning: LangChain or OpenAI packages not installed. Skipping keyword generation.")
                    print("To install required packages: pip install langchain langchain-openai")
            
            # Use totalBudget directly as price_level (already in $ format)
            price_level = trip_data.get('totalBudget', "")
            
            # Search for hotels
            hotels_collection = db["tripadvisor-hotel_review"]
            
            # Build search query with available fields
            query_conditions = []
            
            # Add location filter based on address_obj
            if destination_city:
                city_condition = {"address_obj.city": destination_city}
                query_conditions.append(city_condition)
            
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
            
            # Country matching (United States vs USA)
            if destination_country:
                country_value = destination_country.strip()
                country_conditions = []
                
                # Handle common variations of United States
                if country_value.upper() in ["USA", "U.S.A.", "U.S.", "UNITED STATES", "UNITED STATES OF AMERICA"]:
                    country_conditions.append({"address_obj.country": "United States"})
                    country_conditions.append({"address_obj.country": "USA"})
                    country_conditions.append({"address_obj.country": "U.S.A."})
                    country_conditions.append({"address_obj.country": "U.S."})
                # Handle variations of United Kingdom
                elif country_value.upper() in ["UK", "U.K.", "UNITED KINGDOM", "GREAT BRITAIN"]:
                    country_conditions.append({"address_obj.country": "United Kingdom"})
                    country_conditions.append({"address_obj.country": "UK"})
                    country_conditions.append({"address_obj.country": "U.K."})
                    country_conditions.append({"address_obj.country": "Great Britain"})
                else:
                    # Use as-is for other countries
                    country_conditions.append({"address_obj.country": country_value})
                
                # Add OR condition to match any country format
                if len(country_conditions) > 1:
                    query_conditions.append({"$or": country_conditions})
                else:
                    query_conditions.append(country_conditions[0])
            
            # Add price level filter if available
            if price_level:
                query_conditions.append({"price_level": price_level})
            
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
                    ("amenities", "text"),
                    ("brand", "text")
                ], name="text_search_index")
            
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
            mongo_search_limit = max(10, limit)
            # If using full-text search, use the textScore for sorting
            if search_keywords and text_search_string:
                # Get the limited results with proper sorting
                search_results = list(hotels_collection.find(final_query, projection).sort(text_sort).limit(mongo_search_limit))
            else:
                # Just sort by rating if no text search
                search_results = list(hotels_collection.find(final_query).sort([("rating", -1)]).limit(mongo_search_limit))
            
            # Process results
            if search_results:
                # Convert MongoDB documents to displayable JSON
                parsed_results = json.loads(dumps(search_results))
                
                # Rerank results using OpenAI if API key is available
                if openai_api_key:
                    print(f"Starting LLM reranking with model gpt-4o-mini...")
                    try:
                        # Initialize the LLM if it wasn't already done
                        if 'llm' not in locals():
                            from langchain_openai import ChatOpenAI
                            from langchain.prompts import ChatPromptTemplate
                            
                            llm_model = "gpt-4o-mini"
                            llm = ChatOpenAI(model=llm_model, openai_api_key=openai_api_key)
                            print(f"Successfully initialized LLM model: {llm_model}")
                        
                        # Create a prompt template for hotel characteristics
                        rerank_template = """
                        Based on the following trip information and list of hotels, select the single best hotel that matches the trip requirements.
                        Take into account all of the trip information below and how the hotel matches the trip requirements.
                        
                        Trip Information:
                        {trip_data}
                        
                        Hotels:
                        {hotels_data}
                        
                        Return your response as a JSON object with two fields:
                        1. "hotel_name": The exact name of the best matching hotel
                        2. "explanation": A short max 7 word quirky explanation of why this hotel was selected for this trip
                        
                        Format your response as valid JSON only. Do not include any explanations outside the JSON, do not include ```json or ```.
                        Example: {{"hotel_name": "Example Hotel", "explanation": "This hotel offers valet ski-in/ski-out access."}}
                        """
                        
                        prompt = ChatPromptTemplate.from_template(rerank_template)
                        print("Created prompt template for hotel ranking")
                        
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
                            Description: {hotel.get('description', '')[:200]}
                            """
                            hotels_data.append(hotel_info)
                        
                        print(f"Prepared {len(hotels_data)} hotels for ranking")
                        print(f"Hotel names: {hotel_names}")
                        
                        # Get the best hotel from LLM
                        chain = prompt | llm
                        print("Calling LLM API for hotel ranking...")
                        response = chain.invoke({
                            "trip_data": trip_data_string,
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
                
                # Create formatted results
                formatted_results = []
                for i, hotel in enumerate(parsed_results):
                    hotel_id = hotel.get('location_id', 'N/A')
                    name = hotel.get('name', 'Unnamed Hotel')
                    rating = hotel.get('rating', 'N/A')
                    price = hotel.get('price_level', 'N/A')
                    
                    # Get main photo URL if available
                    main_photo_url = None
                    if 'photos' in hotel and len(hotel['photos']) > 0:
                        first_photo = hotel['photos'][0]
                        if 'images' in first_photo and 'original' in first_photo['images']:
                            main_photo_url = first_photo['images']['original'].get('url', None)
                    
                    # Get address data
                    address_obj = hotel.get('address_obj', {})
                    address_string = address_obj.get('address_string', '') if address_obj else ''
                    
                    # Get coordinates
                    latitude = hotel.get('latitude', None)
                    longitude = hotel.get('longitude', None)
                    
                    # Get description
                    description = hotel.get('description', '')
                    
                    # Create formatted hotel object
                    today_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    
                    # Determine the notes field content
                    # If this is the top hotel and it has an LLM explanation, use that
                    # Otherwise use the rating
                    if i == 0 and "llm_explanation" in hotel:
                        notes = hotel["llm_explanation"]
                        print(f"Using LLM explanation for notes: {notes}")
                    else:
                        notes = f"Rating: {rating}/5"
                        if i == 0:
                            print(f"Hotel at index 0 has no llm_explanation. Keys: {list(hotel.keys())}")
                    
                    formatted_hotel = {
                        "trip_id": str(trip_id_obj),
                        "type": "accommodation",
                        "name": f"Stay at {name}",
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
                        "budget": price
                    }
                    
                    formatted_results.append(formatted_hotel)
                
                # Return the results limited to the requested count
                return json_response(formatted_results[:limit])
            else:
                return json_response([])
                
        except Exception as e:
            return json_response({"error": f"Error processing trip data: {str(e)}"}), 500
    except Exception as e:
        return json_response({"error": f"Error searching hotels: {str(e)}"}), 500

@app.route('/api/hotels/<trip_id>/save', methods=['POST'])
def search_and_save_hotel(trip_id):
    """Search for a hotel based on a trip ID and save it to the trip_calendar collection"""
    try:
        print(f"Searching for a hotel and saving to trip calendar for trip ID: {trip_id}")
        
        # First, make a direct API call to the search endpoint instead of using test_request_context
        # This is more reliable and avoids issues with request context
        try:
            # Call the search_hotels_for_trip function directly with limit=1
            # Get trip data from MongoDB
            trip_id_obj = ObjectId(trip_id)
            trip_data = db.trips.find_one({"_id": trip_id_obj})
            
            if not trip_data:
                return json_response({"error": f"No trip found with ID: {trip_id}"}), 404
            
            # Call the existing endpoint directly with limit=1
            response = requests.get(f"http://localhost:5001/api/hotels/{trip_id}?limit=1")
            if response.status_code != 200:
                return json_response({"error": f"Error fetching hotel data: {response.text}"}), response.status_code
            
            # Parse the JSON response
            hotels_data = response.json()
            
            # Check if we have results
            if not hotels_data or len(hotels_data) == 0:
                return json_response({"error": "No hotels found for this trip"}), 404
            
            # Get the first hotel (we asked for limit=1)
            hotel = hotels_data[0]
            
            # Make sure we have a hotel to save
            if hotel:
                print(f"Saving hotel to trip calendar: {hotel['name']}")
                
                # Add trip_id to the hotel data
                hotel['trip_id'] = trip_id
                
                # Insert into trip_calendar collection
                result = db.trip_calendar.insert_one(hotel)
                
                # Add the MongoDB ID to the result
                hotel['_id'] = str(result.inserted_id)
                
                # Return the saved hotel
                return json_response(hotel)
            else:
                return json_response({"error": "No hotels found for this trip"}), 404
                
        except Exception as e:
            import traceback
            print(f"Error searching or saving hotel: {e}")
            print(traceback.format_exc())
            return json_response({"error": f"Error searching or saving hotel: {str(e)}"}), 500
                
    except Exception as e:
        import traceback
        print(f"Error searching or saving hotel: {e}")
        print(traceback.format_exc())
        return json_response({"error": f"Error searching or saving hotel: {str(e)}"}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """API health check endpoint"""
    return jsonify({"status": "ok", "message": "MongoDB API Server is running"})

if __name__ == '__main__':
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='MongoDB API Server')
    parser.add_argument('--port', type=int, default=5001, help='Port to run the server on (default: 5001)')
    args = parser.parse_args()
    
    # Get port from command-line argument
    port = args.port
    
    print(f"\n====== Starting MongoDB API Server on port {port} ======")
    print(f"Database: {database_name}")
    
    try:
        # Verify connection to MongoDB
        client = MongoClient(uri)
        db = client[database_name]
        
        # Check and list collections
        collections = db.list_collection_names()
        print(f"\nAvailable MongoDB collections: {collections}")
        
        # Check for trips
        trips = list(db.trips.find())
        print(f"Found {len(trips)} trips in the database")
        
        # Check for trip calendar collections
        if 'trip_calendar' in collections:
            cal_items = list(db.trip_calendar.find())
            print(f"Found {len(cal_items)} items in trip_calendar collection")
            
            if cal_items:
                print(f"Sample trip_calendar item fields: {list(cal_items[0].keys())}")
                print("\nTrip calendar items:")
                for item in cal_items:
                    trip_id_val = item.get('trip_id')
                    trip_id_type = type(trip_id_val).__name__
                    print(f"  - {item.get('type')}: {item.get('name')}, trip_id type: {trip_id_type}, value: {trip_id_val}")
        
        print(f"\n====== Starting API Server on port {port} ======")
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        exit(1)
