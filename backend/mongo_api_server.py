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
from dotenv import load_dotenv
import uuid
from flask import Flask, jsonify, request, Response, session, redirect, stream_with_context
from flask_executor import Executor
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.json_util import dumps, loads
import json 
import traceback

# from flask_cors import CORS

from search_utils import (
    extract_search_trip_data_str, extract_generic_trip_search_keywords_no_llm,
    generate_trip_hotel_search_keywords_with_llm, create_filters, search_mongo,
    convert_mongo_trip_advisor_advisor_results_to_cal_item, rerank_hotel_mongo_results,
    DEFAULT_MIN_UNDERLYING_MONGO_RESULTS, generate_trip_restaurant_search_keywords_with_llm,
    rerank_restaurant_mongo_results, generate_trip_activity_search_keywords_with_llm,
    rerank_activity_mongo_results, convert_mongo_viator_product_results_to_cal_item
)

import scan_email_utils

# Load environment variables from .env file
load_dotenv()

FLASK_KEY = os.getenv('FLASK_KEY')
CLIENT_ID = os.getenv('GOOGLE_CLOUD_GMAIL_CLIENT_ID')
LOGGED_IN_REDIRECT_URI = os.getenv('LOGGED_IN_REDIRECT_URI')

# Check required environment variables
required_env_vars = [
    "MONGODB_USERNAME",
    "MONGODB_PASSWORD",
    "MONGODB_CLUSTER",
    "MONGODB_DATABASE"
]

# Global variable for mock_data flag
mock_data = False

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
#setting app secret key
app.secret_key = FLASK_KEY
# CORS(app)  # Enable CORS for all routes
executor = Executor(app)
tasks = {}

# Setting OAUTHLIB insecure transport to 1 (needed for development with self-signed certificates)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Construct MongoDB URI
uri = f"mongodb+srv://{username}:{password}@{cluster}/?retryWrites=true&w=majority&appName=Viammo-Cluster-alpha"

# Create MongoDB client
client = MongoClient(uri)
db = client[database_name]

# Helper function to convert MongoDB cursor to JSON
def json_response(data):
    """Convert MongoDB cursor to JSON response"""
    return Response(dumps(data), mimetype='application/json')

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
            "totalBudget": "$$$$",
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
            "totalBudget": "$$$$",
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
            "budget": '$$$$',
            "notes": "Stayed at by 5 friends",
            "location": {
                "name": "Hotel Crillion",
                "address": "10 Place de la Concorde, 75008 Paris, France",
                "coordinates": {
                    "lat": 48.8656,
                    "lng": 2.3212
                }
            },
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
            "budget": '$$$',
            "notes": "4.7 Stars on google",
            "location": {
                "name": "Cafe Marmaton",
                "address": "8 Rue de Marmaton, 75002 Paris, France",
                "coordinates": {
                    "lat": 48.8656,
                    "lng": 2.3212
                }
            },
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
            "budget": '$',
            "notes": "Optimal this time of year",
            "location": {
                "name": "The Louvre",
                "address": "Rue de Rivoli, 75001 Paris, France",
                "coordinates": {
                    "lat": 48.8656,
                    "lng": 2.3212
                }
            },
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
            "budget": '$$$',
            "notes": "Saved by you on 9/23/24",
            "location": {
                "name": "The Broken Arm",
                "address": "12 Rue Perrée, 75003 Paris, France",
                "coordinates": {
                    "lat": 48.8656,
                    "lng": 2.3212
                }
            },
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
            "budget": '$',
            "notes": "Recommended by 7 friends",
            "location": {
                "name": "The Broken Arm",
                "address": "25 Rue des Gravilliers, 75003 Paris, France",
                "coordinates": {
                    "lat": 48.8656,
                    "lng": 2.3212
                }
            },
            "start_date": "2024-10-05",
            "end_date": "2024-10-05",
            "start_time": "15:30",
            "end_time": "17:00"
        }
    ]

@app.route("/api/google_login")
def google_login():
    try:
        authorization_url = scan_email_utils.google_login()
        return jsonify({"authorization_url": authorization_url}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e), "stack_trace": traceback.format_exc()}), 500

@app.route("/api/google_login/oauth2callback")
def google_login_oauth2callback():
    try:
        logged_in_redirect_response = scan_email_utils.google_login_oauth2callback(session, request)
        return redirect(logged_in_redirect_response)
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e), "stack_trace": traceback.format_exc()}), 500

@app.route("/api/google_login/logged_in_scan_email")
def google_logged_in_scan_email():

    task_id = uuid.uuid4().hex
    _google_logged_in_scan_email_status(task_id) # Check user logged in.

    def progress_callback(message, progress, status="in_progress", recommendations=None, trip_insights=None, emails=None):
        print(message)
        if task_id not in tasks:
            tasks[task_id] = {}
        tasks[task_id]["status"] = status
        tasks[task_id]["message"] = message
        tasks[task_id]["progress"] = progress
        if emails is not None:
            tasks[task_id]["emails"] = emails
        if trip_insights is not None:
            tasks[task_id]["trip_insights"] = trip_insights
        if recommendations is not None:
            tasks[task_id]["recommendations"] = recommendations

    executor.submit(scan_email_utils.scan_email, session['credentials'], session["id_info"], progress_callback)

    task_progress_str_url = LOGGED_IN_REDIRECT_URI.replace('logged_in_scan_email', f'logged_in_scan_email_status_str/{task_id}')

    return redirect(task_progress_str_url)
    # return jsonify({'task_id': task_id})

def _google_logged_in_scan_email_status(task_id):
    # Verify user token still loged into gmail.
    service = scan_email_utils.get_gmail_service_from_session(session['credentials'])
    profile = service.users().getProfile(userId='me').execute()
    email = profile["emailAddress"]
    if email is None or len(email) == 0:
        raise Exception("User not logged into gmail.")
    
    # return task.
    return tasks.get(task_id, None)

@app.route("/api/google_login/logged_in_scan_email_status/<task_id>")
def google_logged_in_scan_email_status(task_id):
    try:
        task = _google_logged_in_scan_email_status(task_id)
        if task is None or len(task) == 0:
            return jsonify({"error": "Invalid task ID"}), 404
        
        # Strip out large objects for json response.
        task = {
            "status": task.get("status", None),
            "message": task.get("message", None),
            "progress": task.get("progress", None),
        }
            
        return jsonify(task)
    except Exception as e:
        stacktrace = traceback.format_exc()
        print(f"Stacktrace: {stacktrace}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/google_login/logged_in_scan_email_status_str/<task_id>")
def google_logged_in_scan_email_status_str(task_id):
    try:
        task = _google_logged_in_scan_email_status(task_id)
        if task is None or len(task) == 0:
            return "Invalid task ID", 404
        
        out = ""
        out += "<br>REFRESH PAGE TO GET LATEST STATUS<br>"
        out += "<br>=== Status =======<br>"
        out += task.get("status", "unknown")
        out += "<br>===================<br>"

        out += "<br>=== Progress =======<br>" 
        out += f'{str(task.get("progress", "unknown"))}%'
        out += "<br>===================<br>"

        out += "<br>=== Message =======<br>"
        out += task.get("message", "unknown")
        out += "<br>===================<br>"

        out += "<br>=== Generated Trip Insights ===<br>"
        trip_insights = task.get("trip_insights", None)
        if trip_insights:
            out += trip_insights.replace('\n', '<br>')
            out += "<br>===============================<br>"
        else:
            out += "generation in progress...<br>"
        
        recommendations = task.get("recommendations", None)
        out += "<br>=== Generated Recommendations ===<br>"
        if recommendations:
            out += json.dumps(recommendations, indent=4).replace('\n', '<br>')
            out += "<br>=================================<br>"
        else:
            out += "generation in progress...<br>"
        
        emails = task.get("emails", None)
        out += "<br>=== Emails ===<br>"
        if emails:
            out += f"{len(emails)} hotel reservation emails found.<br><br>"
            for email_data in emails.values():
                out += f"Email Subject: {email_data['subject']}<br>"
                out += f"   From: {email_data['sender']}<br>"
                out += f"   Date: {email_data['date']}<br>"
                out += f"   To: {email_data['recipient']}<br>"
                out += f"   Reply-To: {email_data['reply_to']}<br>"
                out += f"   CC: {email_data['cc']}<br>"
                out += f"   BCC: {email_data['bcc']}<br>"
                out += f"   In-Reply-To: {email_data['in_reply_to']}<br>"
                out += f"   Id: {email_data['id']}<br>"
                out += f"   Stay Length: {email_data.get('stay_length', '')}<br>"
                out += f"   Stay Year: {email_data.get('stay_year', '')}<br>"
                key_insights = email_data.get('key_insights', 'generation in progress...').replace('\n', '<br>')
                out += f"   Key Insights: {key_insights}<br>"
                out += "-" * 80
                out += "<br>"
            out += "<br>=============================<br>"
        else:
            out += "collection in progress...<br>"
        
        return out
    except Exception as e:
        stacktrace = traceback.format_exc()
        print(f"Stacktrace: {stacktrace}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/trips', methods=['GET'])
def get_trips():
    """Get all trips from MongoDB"""
    try:
        if mock_data:
            return json_response(get_mock_trips())
            
        trips = db.trips.find()
        return json_response(trips)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/trips/<trip_id>', methods=['GET'])
def get_trip(trip_id):
    """Get a specific trip by ID from MongoDB"""
    try:
        if mock_data:
            mock_trips = get_mock_trips()
            for trip in mock_trips:
                if trip["_id"]["$oid"] == trip_id:
                    return json_response(trip)
            return jsonify({"error": "Trip not found"}), 404
            
        # First try to parse as ObjectId
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
        return jsonify({"error": str(e)}), 500

@app.route('/api/trips/<trip_id>', methods=['DELETE'])
def delete_trip(trip_id):
    """Delete a trip and its associated calendar items from MongoDB"""
    try:
        # Validate trip_id
        try:
            mongo_trip_id = ObjectId(trip_id)
        except Exception as e:
            print(f"Invalid trip ID format: {trip_id}")
            return json_response({"success": False, "error": "Invalid trip ID format"}), 400

        # Connect to MongoDB
        try:
            client = MongoClient(uri)
            db = client[database_name]
            
            # First, delete any calendar items associated with this trip
            print(f"Deleting trip calendar items for trip ID: {trip_id}")
            
            # When trip_id is stored as an ObjectId
            calendar_result_obj = db.trip_calendar.delete_many({"trip_id": mongo_trip_id})
            print(f"Deleted {calendar_result_obj.deleted_count} calendar items with ObjectId trip_id")
            
            total_calendar_items_deleted = calendar_result_obj.deleted_count
            print(f"Total calendar items deleted: {total_calendar_items_deleted}")
            
            # Then delete the trip itself
            trip_result = db.trips.delete_one({"_id": mongo_trip_id})
            print(f"Trip deletion result: {trip_result.deleted_count} trips deleted")
            
            if trip_result.deleted_count == 0:
                return json_response({
                    "success": False, 
                    "error": "Trip not found"
                }), 404
            
            return json_response({
                "success": True,
                "message": f"Trip deleted successfully. Also removed {total_calendar_items_deleted} calendar items."
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
        if mock_data:
            mock_calendar = get_mock_calendar()
            filtered_calendar = [item for item in mock_calendar if item["trip_id"] == trip_id]
            return json_response(filtered_calendar)
            
        # Convert trip_id to ObjectId
        trip_obj_id = ObjectId(trip_id)
        print(f"Successfully converted trip_id to ObjectId: {trip_id}")
        
        # Try to find calendar items by ObjectId
        calendar_items = list(db.trip_calendar.find({"trip_id": trip_obj_id}))
        print(f"Query with trip_id as ObjectId found {len(calendar_items)} items")
        return json_response(calendar_items)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        return jsonify({"error": str(e)}), 500

@app.route('/api/debug/trip_calendar_raw', methods=['GET'])
def get_trip_calendar_raw():
    """Get all raw trip_calendar items for debugging."""
    try:
        calendar_items = list(db.trip_calendar.find())
        return json_response(calendar_items)
    except Exception as e:
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
    print(f"\nsearch_hotels_for_trip with trip ID: {trip_id}\n\n")
    try:
        # Get query parameters
        limit = request.args.get('limit', default=1, type=int)
        
        # Convert trip_id to ObjectId
        trip_obj_id = ObjectId(trip_id)
        print(f"Successfully converted trip_id to ObjectId: {trip_id}")
        
        # Get trip data from MongoDB
        try:
            trip_data = db.trips.find_one({"_id": trip_obj_id})
            
            if not trip_data:
                return json_response({"error": f"No trip found with ID: {trip_id}"}), 404

            trip_data_str = extract_search_trip_data_str(trip_data)
            print(f"trip_data_str: {trip_data_str}")
            
            # Extract relevant keywords from trip data
            openai_api_key = os.getenv("OPENAI_API_KEY")
            search_keywords = generate_trip_hotel_search_keywords_with_llm(trip_data_str, openai_api_key)
            trip_price_level = trip_data.get('totalBudget', None)
            print(f"trip_price_level: {trip_price_level}\n")
            search_keywords = search_keywords | set([trip_price_level]) if trip_price_level else search_keywords
            print(f"search_keywords: {search_keywords}")

            # Build search query with available fields
            query_conditions = create_filters(trip_data)
            print(f"query_conditions: {query_conditions}")
            
            # Search for hotels
            hotels_collection = db["tripadvisor-hotel_review"]

            # Build combined search including full-text search
            mongo_search_limit = max(DEFAULT_MIN_UNDERLYING_MONGO_RESULTS, limit) # Get min 20 results to make sure reranking has enough results.
            search_results = search_mongo(hotels_collection, query_conditions, search_keywords, limit=mongo_search_limit)
            
            # Process results
            if search_results:
                # Debug: Print how many results were found
                print(f"\nFound {len(search_results)} initial results from MongoDB")
                
                # Convert MongoDB documents to displayable JSON
                parsed_results = json.loads(dumps(search_results))
                
                # Rerank results with llm
                reranked_results = rerank_hotel_mongo_results(parsed_results, trip_data_str, openai_api_key)
                
                # Create formatted results
                start_date = trip_data.get('startDate', None)
                end_date = trip_data.get('endDate', None)
                cal_el_type = 'accommodation'
                formatted_results = convert_mongo_trip_advisor_advisor_results_to_cal_item(reranked_results, trip_obj_id, start_date, end_date, cal_el_type)
                
                # Return the results limited to the requested count
                return json_response(formatted_results[:limit])
            else:
                return json_response([])
                
        except Exception as e:
            return json_response({"error": f"Error processing trip data: {str(e)}"}), 500
    except Exception as e:
        return json_response({"error": f"Error searching hotels: {str(e)}"}), 500

@app.route('/api/restaurants/<trip_id>', methods=['GET'])
def search_restaurants_for_trip(trip_id):
    """Search for restaurants based on a trip ID"""
    print(f"\nsearch_restaurants_for_trip with trip ID: {trip_id}\n\n")
    try:
        # Get query parameters
        limit = request.args.get('limit', default=4, type=int)
        
        # Convert trip_id to ObjectId
        trip_obj_id = ObjectId(trip_id)
        print(f"Successfully converted trip_id to ObjectId: {trip_id}")
        
        # Get trip data from MongoDB
        try:
            trip_data = db.trips.find_one({"_id": trip_obj_id})
            
            if not trip_data:
                return json_response({"error": f"No trip found with ID: {trip_id}"}), 404

            trip_data_str = extract_search_trip_data_str(trip_data)
            print(f"trip_data_str: {trip_data_str}")
            
            # Extract relevant keywords from trip data
            openai_api_key = os.getenv("OPENAI_API_KEY")
            search_keywords = generate_trip_restaurant_search_keywords_with_llm(trip_data_str, openai_api_key)
            trip_price_level = trip_data.get('totalBudget', None)
            print(f"trip_price_level: {trip_price_level}\n")
            search_keywords = search_keywords | set([trip_price_level]) if trip_price_level else search_keywords
            print(f"search_keywords: {search_keywords}")

            # Build search query with available fields
            query_conditions = create_filters(trip_data)
            print(f"query_conditions: {query_conditions}")
            
            # Search for restaurants
            restaurants_collection = db["tripadvisor-restaurant_review"]

            # Build combined search including full-text search
            mongo_search_limit = max(DEFAULT_MIN_UNDERLYING_MONGO_RESULTS, limit) # Get min 20 results to make sure reranking has enough results.
            search_results = search_mongo(restaurants_collection, query_conditions, search_keywords, limit=mongo_search_limit)
            
            # Process results
            if search_results:
                # Debug: Print how many results were found
                print(f"\nFound {len(search_results)} initial results from MongoDB")
                
                # Convert MongoDB documents to displayable JSON
                parsed_results = json.loads(dumps(search_results))
                
                # Rerank results with llm
                reranked_results = rerank_restaurant_mongo_results(parsed_results, trip_data_str, openai_api_key)
                
                # Create formatted results
                start_date = trip_data.get('startDate', None)
                end_date = trip_data.get('endDate', None)
                cal_el_type = 'restaurant'
                formatted_results = convert_mongo_trip_advisor_advisor_results_to_cal_item(reranked_results, trip_obj_id, start_date, end_date, cal_el_type)
                
                # Return the results limited to the requested count
                return json_response(formatted_results[:limit])
            else:
                return json_response([])
                
        except Exception as e:
            return json_response({"error": f"Error processing trip data: {str(e)}"}), 500
    except Exception as e:
        return json_response({"error": f"Error searching hotels: {str(e)}"}), 500

@app.route('/api/activities/<trip_id>', methods=['GET'])
def search_activities_for_trip(trip_id):
    """Search for activities from viator products based on a trip ID"""
    print(f"\nsearch_activities_for_trip with trip ID: {trip_id}\n\n")
    try:
        # Get query parameters
        limit = request.args.get('limit', default=4, type=int)
        
        # Convert trip_id to ObjectId
        trip_obj_id = ObjectId(trip_id)
        print(f"Successfully converted trip_id to ObjectId: {trip_id}")
        
        # Get trip data from MongoDB
        try:
            trip_data = db.trips.find_one({"_id": trip_obj_id})
            
            if not trip_data:
                return json_response({"error": f"No trip found with ID: {trip_id}"}), 404

            trip_data_str = extract_search_trip_data_str(trip_data)
            print(f"trip_data_str: {trip_data_str}")
            
            # Extract relevant keywords from trip data
            openai_api_key = os.getenv("OPENAI_API_KEY")
            search_keywords = generate_trip_activity_search_keywords_with_llm(trip_data_str, openai_api_key)
            trip_price_level = trip_data.get('totalBudget', None)
            print(f"trip_price_level: {trip_price_level}\n")
            search_keywords = search_keywords | set([trip_price_level]) if trip_price_level else search_keywords
            print(f"search_keywords: {search_keywords}")
            #TODO: Add $$ to price point search logic.

            # Build search query with available fields
            trip_data_for_filter = trip_data.copy()
            trip_data_for_filter.pop('destination', None)
            query_conditions = create_filters(trip_data_for_filter)
            print(f"query_conditions: {query_conditions}")
            
            # Search for restaurants
            activities_collection = db["viator-products"]

            # Build combined search including full-text search
            mongo_search_limit = max(DEFAULT_MIN_UNDERLYING_MONGO_RESULTS, limit) # Get min 20 results to make sure reranking has enough results.
            search_results = search_mongo(activities_collection, query_conditions, search_keywords, limit=mongo_search_limit)
            
            # Process results
            if search_results:
                # Debug: Print how many results were found
                print(f"\nFound {len(search_results)} initial results from MongoDB")
                
                # Convert MongoDB documents to displayable JSON
                parsed_results = json.loads(dumps(search_results))
                
                # Rerank results with llm
                reranked_results = rerank_activity_mongo_results(parsed_results, trip_data_str, openai_api_key)
                
                # Create formatted results
                start_date = trip_data.get('startDate', None)
                end_date = trip_data.get('endDate', None)
                cal_el_type = 'activity'
                formatted_results = convert_mongo_viator_product_results_to_cal_item(reranked_results, trip_obj_id, start_date, end_date, cal_el_type)
                
                # Return the results limited to the requested count
                return json_response(formatted_results[:limit])
            else:
                return json_response([])
                
        except Exception as e:
            return json_response({"error": f"Error processing trip data: {str(e)}"}), 500
    except Exception as e:
        return json_response({"error": f"Error searching hotels: {str(e)}"}), 500

@app.route('/api/draft_plan/<trip_id>/save', methods=['POST'])
def search_and_save_trip_elements(trip_id):
    """Search for a hotel, restaurants, etc based on a trip ID and save it to the trip_calendar collection"""
    try:
        print(f"Searching for a hotel and restaurants and saving to trip calendar for trip ID: {trip_id}")
        
        # First, make sure the trip exists
        trip_id_obj = ObjectId(trip_id)
        trip_data = db.trips.find_one({"_id": trip_id_obj})
        
        if not trip_data:
            return json_response({"error": f"No trip found with ID: {trip_id}"}), 404
        
        # Call the hotel search function directly
        try:
            # Get hotel data by calling the search function directly
            hotels_data = search_hotels_for_trip(trip_id).get_json()
            
            # Check if we have results
            if not hotels_data or len(hotels_data) == 0:
                return json_response({"error": "No hotels found for this trip"}), 404
            
            # Get the first hotel (we want limit=1)
            hotel = hotels_data[0]
            
            # Make sure we have a hotel to save
            if hotel:
                print(f"Saving hotel to trip calendar: {hotel['name']}")
                
                # Add trip_id to the hotel data as an ObjectId
                hotel['trip_id'] = ObjectId(trip_id)
                
                # Insert into trip_calendar collection
                result = db.trip_calendar.insert_one(hotel)
            else:
                return json_response({"error": "No hotels found for this trip"}), 404
            
            # Call the restaurant search function directly
            n = 4  # Number of restaurants to get
            restaurants_data = search_restaurants_for_trip(trip_id).get_json()
            
            # Check if we have results
            if not restaurants_data or len(restaurants_data) == 0:
                return json_response({"error": "No restaurants found for this trip"}), 404
            
            # Get the first n restaurants
            restaurants = restaurants_data[:n]
            
            # Make sure we have a restaurant to save
            if restaurants:
                print(f"Saving restaurants to trip calendar: {', '.join([r['name'] for r in restaurants])}")
                
                # Add trip_id to the restaurant data as an ObjectId
                for restaurant in restaurants:
                    restaurant['trip_id'] = ObjectId(trip_id)
                
                # Insert into trip_calendar collection
                result = db.trip_calendar.insert_many(restaurants)
            else:
                return json_response({"error": "No restaurants found for this trip"}), 404
            
            # Call the restaurant search function directly
            n = 4  # Number of activities to get
            activities_data = search_activities_for_trip(trip_id).get_json()
            
            # Check if we have results
            if not activities_data or len(activities_data) == 0:
                return json_response({"error": "No activities found for this trip"}), 404
            
            # Get the first n activities
            activities = activities_data[:n]
            
            # Make sure we have an activity to save
            if activities:
                print(f"Saving activities to trip calendar: {', '.join([r['name'] for r in activities])}")
                
                # Add trip_id to the activity data as an ObjectId
                for activity in activities:
                    activity['trip_id'] = ObjectId(trip_id)
                
                # Insert into trip_calendar collection
                result = db.trip_calendar.insert_many(activities)
            else:
                return json_response({"error": "No activities found for this trip"}), 404
            
            return json_response(True), 200
                
        except Exception as e:
            import traceback
            print(f"Error planning trip: {e}")
            print(traceback.format_exc())
            return json_response({"error": f"Error planning trip: {str(e)}"}), 500
                
    except Exception as e:
        import traceback
        print(f"Error planning trip: {e}")
        print(traceback.format_exc())
        return json_response({"error": f"Error planning trip: {str(e)}"}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """API health check endpoint"""
    return jsonify({"status": "ok", "message": "MongoDB API Server is running"})

if __name__ == '__main__':
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='MongoDB API Server')
    parser.add_argument('--port', type=int, default=5001, help='Port to run the server on (default: 5001)')
    parser.add_argument('--mock-data', action='store_true', help='Use mock data instead of MongoDB connection')
    args = parser.parse_args()
    
    # Set global mock_data flag
    mock_data = args.mock_data
    
    # Get port from command-line argument
    port = args.port
    
    if mock_data:
        print("Running with mock data - no MongoDB connection required")
        print(f"\n====== Starting MongoDB API Server on port {port} ======")
        print("Database: viammo-alpha")
        print(f"\n====== Starting API Server on port {port} ======")
        app.run(host='0.0.0.0', port=port)
    else:
        # Only attempt MongoDB connection if not using mock data
        
        # Test MongoDB connection
        try:
            client.admin.command('ping')
            print("Successfully connected to MongoDB!")
        except Exception as e:
            print(f"MongoDB connection error: {e}")
            sys.exit(1)
            
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
            app.run(
                host='0.0.0.0',
                port=port,
                # debug=True
            )
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            exit(1)

