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
"""

import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.json_util import dumps, loads

# Determine base directory (project root)
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path)

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

@app.route('/api/health', methods=['GET'])
def health_check():
    """API health check endpoint"""
    return jsonify({"status": "ok", "message": "MongoDB API Server is running"})

if __name__ == '__main__':
    print("\n====== Starting MongoDB API Server on port 5004 ======")
    print(f"MongoDB URI: {uri[:uri.index('@') + 1]}****{uri[uri.index('@'):]}")
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
        
        print("\n====== Starting API Server ======")
        app.run(host='0.0.0.0', port=5004)
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        exit(1)
