import axios from 'axios';
import { Trip, TripCalendarItem } from './types';
import { env } from '../env';

// API base URL - built from environment configuration
// Will default to 'http://localhost:5001/api' but can be overridden with environment variables
const API_BASE_URL = env.apiUrl;

// API functions for MongoDB operations
export const api = {
  // Fetch all trips from MongoDB
  getTrips: async (): Promise<Trip[]> => {
    try {
      console.log('Fetching trips from API server...');
      
      // Try to fetch from API server
      const response = await axios.get(`${API_BASE_URL}/trips`);
      console.log('API response:', response.data);
      
      if (response.data && Array.isArray(response.data)) {
        return response.data;
      }
      
      throw new Error('Invalid response from API server');
    } catch (error) {
      console.error('Error fetching trips from API server:', error);
      // Return empty array with error
      throw new Error('Failed to fetch trips. Please ensure the API server is running and connected to MongoDB.');
    }
  },
  
  // Check API server health
  checkApiHealth: async (): Promise<{ status: string; message: string }> => {
    try {
      // Try the API health endpoint to see if server is running
      const response = await axios.get(`${API_BASE_URL}/health`);
      console.log('API server health check:', response.data);
      return { 
        status: 'ok', 
        message: 'API server is running correctly' 
      };
    } catch (error) {
      console.error('API server health check failed:', error);
      throw new Error('API server is not running or not accessible. Please start the API server using "python scripts/mongo_api_server.py --port 5001"');
    }
  },
  
  // Fetch a single trip by ID
  getTrip: async (id: string): Promise<Trip> => {
    try {
      if (!id || typeof id !== 'string') {
        throw new Error(`Invalid trip ID: ${id}. Expected a non-empty string.`);
      }
      
      // Clean the ID - remove any quotes or extra spaces
      const cleanId = id.trim().replace(/^["'](.*)["']$/, '$1');
      
      console.log(`Fetching trip ${cleanId} from API server...`);
      console.log('Original ID:', id);
      console.log('Cleaned ID:', cleanId);
      
      // Try to fetch from API server
      const response = await axios.get(`${API_BASE_URL}/trips/${cleanId}`);
      console.log('API response:', response.data);
      
      if (response.data) {
        return response.data;
      }
      
      throw new Error('Invalid response from API server');
    } catch (error) {
      console.error(`Error fetching trip ${id} from API server:`, error);
      
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        throw new Error(`Trip with ID ${id} not found. Please check the ID and try again.`);
      }
      
      throw new Error(`Failed to fetch trip ${id}. Please ensure the API server is running and connected to MongoDB.`);
    }
  },
  
  // Fetch trip calendar items by trip ID
  getTripCalendar: async (tripId: string): Promise<TripCalendarItem[]> => {
    try {
      if (!tripId || typeof tripId !== 'string') {
        console.error('Invalid trip ID type:', typeof tripId, tripId);
        throw new Error(`Invalid trip ID: ${String(tripId)}. Expected a non-empty string.`);
      }
      
      // Clean the ID - remove any quotes or extra spaces
      const cleanId = tripId.trim().replace(/^["'](.*)["']$/, '$1');
      
      console.log(`Fetching calendar for trip ${cleanId} from API server...`);
      console.log('Original ID:', tripId);
      console.log('Cleaned ID:', cleanId);
      
      // Try to fetch from API server - fix the URL by removing the extra /api prefix
      const response = await axios.get(`${API_BASE_URL}/calendar/${cleanId}`);
      console.log('API response:', response.data);
      
      if (response.data && Array.isArray(response.data)) {
        return response.data;
      }
      
      throw new Error('Invalid response from API server');
    } catch (error) {
      console.error(`Error fetching calendar for trip ${tripId} from API server:`, error);
      
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        throw new Error(`Calendar items for trip ${tripId} not found. Please check the trip ID and try again.`);
      }
      
      throw new Error(`Failed to fetch calendar items for trip ${tripId}. Please ensure the API server is running and MongoDB is accessible.`);
    }
  },

  // Delete a trip and its calendar items by trip ID
  deleteTrip: async (tripId: string): Promise<{ success: boolean; message: string }> => {
    try {
      console.log(`Deleting trip with ID: ${tripId}`);
      
      // Call API server to delete the trip
      const response = await axios.delete(`${API_BASE_URL}/trips/${tripId}`);
      console.log('Delete response:', response.data);
      
      return { 
        success: true, 
        message: 'Trip and associated calendar items deleted successfully' 
      };
    } catch (error) {
      console.error('Error deleting trip:', error);
      
      // Handle specific error cases
      if (axios.isAxiosError(error) && error.response) {
        return { 
          success: false, 
          message: error.response.data.error || 'Failed to delete trip' 
        };
      }
      
      return { 
        success: false, 
        message: 'Network error while deleting trip' 
      };
    }
  },
};
